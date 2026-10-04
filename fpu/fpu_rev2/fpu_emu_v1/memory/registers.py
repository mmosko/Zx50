"""Physical and logical register file implementation for Zx50 FPU.

Enforces physical bus routing via HA_BUS and HB_BUS, single-tick multiplexer
timing rules, and clock-enabled writeback via RES_BUS. Direct access to math
and compound registers is strictly forbidden during execution.
"""

from enum import Enum
import struct
from typing import Any, Optional, Union
from fpu_emu.fpga_resource import fpga_resource


class HalfSelect(Enum):
    """32-bit Half selection for 64-bit buses and registers."""

    LO = 0
    HI = 1

    @classmethod
    def from_val(cls, val: Union["HalfSelect", str, int]) -> "HalfSelect":
        """Converts an enum, string ('HI'/'LO'), or integer (0/1) to HalfSelect."""
        if isinstance(val, HalfSelect):
            return val
        if isinstance(val, str):
            val_upper = val.upper().strip()
            if val_upper in ("LO", "LOW", "0", "L"):
                return cls.LO
            elif val_upper in ("HI", "HIGH", "1", "H"):
                return cls.HI
        elif isinstance(val, int):
            return cls.HI if val != 0 else cls.LO
        raise ValueError(f"Invalid HalfSelect value: {val}")


class HardwareTimingConflictError(Exception):
    """Raised when hardware timing rules are violated in a single clock cycle."""

    pass


class HardwareBusError(Exception):
    """Raised when an illegal bus access occurs."""

    pass


class HardwareAccessViolationError(Exception):
    """Raised when direct register access is attempted on bus-gated registers."""

    pass


class Reg(Enum):
    """Register enumeration."""

    # 32-bit General & Math Registers
    AL = 0
    AH = 1
    BL = 2
    BH = 3
    DL = 4
    DH = 5
    FL = 6
    FH = 7

    # 64-bit Compound Registers
    AX = 8
    BX = 9
    DX = 10
    FX = 11

    # Exponent Registers (12-bit / 2 bytes)
    EA = 12
    EB = 13

    # Counter (6-bit / 1 byte)
    C = 14

    # Control, Status, and Pointers
    STATUS = 15
    SP = 16
    OSP = 17
    UPC = 18

    @property
    def byte_length(self) -> int:
        """Expected byte length for the register."""
        if self.is_64():
            return 8
        elif self in (Reg.AL, Reg.AH, Reg.BL, Reg.BH, Reg.DL, Reg.DH, Reg.FL, Reg.FH):
            return 4
        elif self in (Reg.EA, Reg.EB, Reg.UPC):
            return 2
        elif self in (Reg.C, Reg.STATUS, Reg.SP, Reg.OSP):
            return 1
        raise ValueError(f"Unknown byte length for register {self}")

    def is_64(self) -> bool:
        return self in _REG_64

    def is_32(self) -> bool:
        return self in _REG_32

    def is_hi(self) -> bool:
        return self in _REG_32_HI

    def is_lo(self) -> bool:
        return self in _REG_32_LO

    def hi_half(self) -> "Reg":
        if self.is_32():
            raise ValueError(f"Tried getting hi half of a 32 bit reg: {self}")
        match self:
            case Reg.AX:
                return Reg.AH
            case Reg.BX:
                return Reg.BH
            case Reg.DX:
                return Reg.DH
            case Reg.FX:
                return Reg.FH
        raise ValueError(f"Unsupported 64-bit register: {self}")

    def lo_half(self) -> "Reg":
        if self.is_32():
            raise ValueError(f"Tried getting hi half of a 32 bit reg: {self}")
        match self:
            case Reg.AX:
                return Reg.AL
            case Reg.BX:
                return Reg.BL
            case Reg.DX:
                return Reg.DL
            case Reg.FX:
                return Reg.FL
        raise ValueError(f"Unsupported 64-bit register: {self}")


_REG_64 = (Reg.AX, Reg.BX, Reg.DX, Reg.FX)
_REG_32 = (
    Reg.AL,
    Reg.AH,
    Reg.BL,
    Reg.BH,
    Reg.DL,
    Reg.DH,
    Reg.FL,
    Reg.FH,
    Reg.EA,
    Reg.EB,
)

_REG_32_HI = (
    Reg.AH,
    Reg.BH,
    Reg.DH,
    Reg.FH,
)

_REG_32_LO = (
    Reg.AL,
    Reg.BL,
    Reg.DL,
    Reg.FL,
)


class StatusFlag(Enum):
    """Status register flag bit allocations (SystemDesign.md Section 2.1)."""

    DIFF_SIGN = 0  # Bit 0: Effective subtraction / operand signs differ
    ERR = 1  # Bit 1: Error flag (Division by zero, domain errors, stack traps)
    UNDERFLOW = 2  # Bit 2: Stack or floating-point underflow
    OVERFLOW = 3  # Bit 3: Stack, integer, or floating-point overflow
    CARRY = 4  # Bit 4: Arithmetic carry or borrow
    SIGN = 5  # Bit 5: Sign flag (1 = Negative)
    ZERO = 6  # Bit 6: Zero flag (1 = Result is zero)
    BUSY = 7  # Bit 7: Hardware execution busy flag


class Registers:
    """Register file holding all physical FPU registers and enforcing bus architecture."""

    @fpga_resource(
        approach="MachXO2 PFU Slice Flip-Flops for 17 Physical Hardware Registers",
        luts=0,
        ffs=379,
        delay_ns=1.5,
        cycles=1,
        shared_unit="register_file",
    )
    def __init__(self, clock: Optional[Any] = None):
        # 32-bit registers (Little-Endian: byte 0 = LSB, byte 3 = MSB)
        self._al = bytearray(4)
        self._ah = bytearray(4)
        self._bl = bytearray(4)
        self._bh = bytearray(4)
        self._dl = bytearray(4)
        self._dh = bytearray(4)
        self._fl = bytearray(4)
        self._fh = bytearray(4)

        # 12-bit Exponent registers (stored in 2 bytes, Little-Endian)
        self._ea = bytearray(2)
        self._eb = bytearray(2)

        # 6-bit Loop/Shift counter (stored in 1 byte)
        self._c = bytearray(1)

        # Control and Pointer registers
        self._status = bytearray(1)
        self._sp = bytearray(1)
        self._osp = bytearray(1)
        self._upc = bytearray(2)

        # Operand Sign and Trig Latches
        self.sign_a: int = 0
        self.sign_b: int = 0
        self.sign_res: int = 0
        self.quadrant: int = 0

        # Clock binding and bus cycle tracking
        self._clock: Optional[Any] = clock
        self._last_ha_tick: int = -1
        self._last_hb_tick: int = -1
        self._last_res_tick: int = -1

        # MUX State Latches
        self._ha_bus_half: Optional[HalfSelect] = None
        self._hb_bus_reg: Optional[Reg] = None
        self._hb_bus_half: Optional[HalfSelect] = None

    def bind_clock(self, clock: Any) -> None:
        """Binds master clock instance to monitor cycle transitions."""
        self._clock = clock

    @property
    def current_tick(self) -> int:
        """Returns the current clock cycle count."""
        return self._clock.cycles if self._clock is not None else 0

    # -------------------------------------------------------------------------
    # Shared Bus Interface & Timing Collision Protection
    # -------------------------------------------------------------------------
    @fpga_resource(
        approach="32-bit 2:1 PFU multiplexer (AL vs AH)",
        luts=16,
        delay_ns=1.2,
        cycles=1,
        shared_unit="bus_ha_mux",
    )
    def set_ha_bus_mux(self, half_sel: HalfSelect) -> None:
        """Selects AL (LO) or AH (HI) to drive HA_BUS[31:0].

        Throws HardwareTimingConflictError if called more than once in the same clock cycle.
        """
        tick = self.current_tick
        if self._last_ha_tick == tick:
            raise HardwareTimingConflictError(
                f"HA_BUS multiplexer timing violation: switched multiple times in clock cycle {tick}"
            )
        self._last_ha_tick = tick
        self._ha_bus_half = half_sel

    @fpga_resource(
        approach="32-bit 8:1 PFU multiplexer (BL,BH,DL,DH,FL,FH,AL,AH)",
        luts=64,
        delay_ns=2.4,
        cycles=1,
        shared_unit="bus_hb_mux",
    )
    def set_hb_bus_mux(
        self,
        half_sel: HalfSelect,
        src: Reg,
    ) -> None:
        """Selects a register half to drive HB_BUS[31:0].

        Throws HardwareTimingConflictError if called more than once in the same clock cycle.
        """
        if src not in _REG_64 and src not in _REG_32 and src not in (Reg.C, Reg.EA, Reg.EB):
            raise HardwareBusError(f"HB_BUS multiplexer invalid source: {src}")
        tick = self.current_tick
        if self._last_hb_tick == tick:
            raise HardwareTimingConflictError(
                f"HB_BUS multiplexer timing violation: switched multiple times in clock cycle {tick}"
            )
        self._last_hb_tick = tick
        self._hb_bus_half = half_sel
        self._hb_bus_reg = src

    def read_ha_bus(self) -> bytearray:
        """Reads the 32-bit (4-byte) value currently driven on HA_BUS."""
        if self._ha_bus_half is None:
            raise HardwareBusError("Attempted to read HA_BUS before set_ha_bus_mux was set.")
        if self._ha_bus_half == HalfSelect.LO:
            return bytearray(self._al)
        else:
            return bytearray(self._ah)

    def read_hb_bus(self) -> bytearray:
        """Reads the 32-bit (4-byte) value currently driven on HB_BUS."""
        if self._hb_bus_half is None or self._hb_bus_reg is None:
            raise HardwareBusError("Attempted to read HB_BUS before set_hb_mux was set.")

        src = self._hb_bus_reg
        half = self._hb_bus_half

        if src == Reg.AX:
            return bytearray(self._al if half == HalfSelect.LO else self._ah)
        elif src == Reg.BX:
            return bytearray(self._bl if half == HalfSelect.LO else self._bh)
        elif src == Reg.DX:
            return bytearray(self._dl if half == HalfSelect.LO else self._dh)
        elif src == Reg.FX:
            return bytearray(self._fl if half == HalfSelect.LO else self._fh)
        elif src == Reg.AL:
            return bytearray(self._al)
        elif src == Reg.AH:
            return bytearray(self._ah)
        elif src == Reg.BL:
            return bytearray(self._bl)
        elif src == Reg.BH:
            return bytearray(self._bh)
        elif src == Reg.DL:
            return bytearray(self._dl)
        elif src == Reg.DH:
            return bytearray(self._dh)
        elif src == Reg.FL:
            return bytearray(self._fl)
        elif src == Reg.FH:
            return bytearray(self._fh)
        elif src == Reg.EA:
            return bytearray(self.ea.to_bytes(4, byteorder="little"))
        elif src == Reg.EB:
            return bytearray(self.eb.to_bytes(4, byteorder="little"))
        elif src == Reg.C:
            return bytearray(self.c.to_bytes(4, byteorder="little"))
        else:
            raise HardwareBusError(f"Unsupported register source for HB_BUS: {src}")

    @property
    def ha_bus_half(self) -> Optional[HalfSelect]:
        return self._ha_bus_half

    @property
    def last_ha_tick(self) -> Optional[int]:
        return self._last_ha_tick

    @property
    def hb_bus_half(self) -> Optional[HalfSelect]:
        return self._hb_bus_half

    @property
    def hb_bus_reg(self) -> Optional[Reg]:
        return self._hb_bus_reg

    @property
    def last_hb_tick(self) -> Optional[int]:
        return self._last_hb_tick

    @property
    def last_res_tick(self) -> Optional[int]:
        return self._last_res_tick

    @fpga_resource(
        approach="32-bit 6:1 PFU multiplexer and 4-to-11 WE decoder",
        luts=70,
        delay_ns=2.6,
        cycles=1,
        shared_unit="bus_res_mux",
    )
    def set_res_bus(
        self,
        dst: Reg,
        data: Union[bytes, bytearray, int],
    ) -> None:
        """Drives RES_BUS[31:0] and asserts WE_<dst> to latch data on clock edge.

        Throws HardwareTimingConflictError if called more than once in the same clock cycle.
        """
        if isinstance(dst, str):
            dst = Reg[dst.upper()]
        tick = self.current_tick
        if self._last_res_tick == tick:
            raise HardwareTimingConflictError(f"RES_BUS collision: multiple writes attempted in clock cycle {tick}")
        self._last_res_tick = tick

        if isinstance(data, int):
            data_bytes = data.to_bytes(4, byteorder="little", signed=(data < 0))
        elif isinstance(data, (bytes, bytearray)):
            data_bytes = data
        else:
            raise TypeError(f"Invalid data type for set_res_bus: {type(data).__name__}")

        if dst == Reg.AL:
            self._al[:] = data_bytes[:4]
        elif dst == Reg.AH:
            self._ah[:] = data_bytes[:4]
        elif dst == Reg.BL:
            self._bl[:] = data_bytes[:4]
        elif dst == Reg.BH:
            self._bh[:] = data_bytes[:4]
        elif dst == Reg.DL:
            self._dl[:] = data_bytes[:4]
        elif dst == Reg.DH:
            self._dh[:] = data_bytes[:4]
        elif dst == Reg.FL:
            self._fl[:] = data_bytes[:4]
        elif dst == Reg.FH:
            self._fh[:] = data_bytes[:4]
        elif dst == Reg.EA:
            val = int.from_bytes(data_bytes[:2], byteorder="little") & 0x0FFF
            self.ea = val
        elif dst == Reg.EB:
            val = int.from_bytes(data_bytes[:2], byteorder="little") & 0x0FFF
            self.eb = val
        elif dst == Reg.C:
            self.c = data_bytes[0] & 0x3F
        else:
            raise HardwareBusError(f"Unsupported writeback destination for RES_BUS: {dst}")

    # -------------------------------------------------------------------------
    # Allowed Control & Status Getters / Setters
    # -------------------------------------------------------------------------
    @property
    def status(self) -> int:
        """Returns status register as an 8-bit integer."""
        return self._status[0]

    @status.setter
    def status(self, val: int):
        self._status[0] = val & 0xFF

    @property
    def sp(self) -> int:
        """Returns Operand Stack Pointer as an 8-bit integer."""
        return self._sp[0]

    @sp.setter
    def sp(self, val: int):
        self._sp[0] = val & 0xFF

    @property
    def osp(self) -> int:
        """Returns Operation Stack Pointer as an 8-bit integer."""
        return self._osp[0]

    @osp.setter
    def osp(self, val: int):
        self._osp[0] = val & 0xFF

    @property
    def c(self) -> int:
        """Returns 6-bit counter as an integer."""
        return self._c[0] & 0x3F

    @c.setter
    def c(self, val: int):
        self._c[0] = val & 0x3F

    @property
    def upc(self) -> int:
        """Returns Microcode Program Counter as a 10-bit integer."""
        return (self._upc[0] | (self._upc[1] << 8)) & 0x3FF

    @upc.setter
    def upc(self, val: int):
        masked = val & 0x3FF
        self._upc[0] = masked & 0xFF
        self._upc[1] = (masked >> 8) & 0xFF

    @property
    def ea(self) -> int:
        """Returns 12-bit primary exponent EA as an unsigned integer."""
        return (self._ea[0] | (self._ea[1] << 8)) & 0x0FFF

    @ea.setter
    def ea(self, val: int):
        masked = val & 0x0FFF
        self._ea[0] = masked & 0xFF
        self._ea[1] = (masked >> 8) & 0x0F

    @property
    def eb(self) -> int:
        """Returns 12-bit secondary exponent EB as an unsigned integer."""
        return (self._eb[0] | (self._eb[1] << 8)) & 0x0FFF

    @eb.setter
    def eb(self, val: int):
        masked = val & 0x0FFF
        self._eb[0] = masked & 0xFF
        self._eb[1] = (masked >> 8) & 0x0F

    # -------------------------------------------------------------------------
    # Status Flag Manipulation
    # -------------------------------------------------------------------------
    def get_flag(self, flag: Union[StatusFlag, int]) -> bool:
        """Checks if a status flag is asserted."""
        bit_idx = flag.value if isinstance(flag, StatusFlag) else flag
        return bool(self._status[0] & (1 << bit_idx))

    def set_flag(self, flag: Union[StatusFlag, int], val: bool = True):
        """Sets or clears an individual status flag."""
        bit_idx = flag.value if isinstance(flag, StatusFlag) else flag
        if val:
            self._status[0] |= 1 << bit_idx
        else:
            self._status[0] &= ~(1 << bit_idx)

    def clr_flag(self, flag: Union[StatusFlag, int]):
        """Explicitly clears an individual status flag."""
        self.set_flag(flag, False)

    def clear_flags(self):
        """Clears all status flags to zero."""
        self._status[0] = 0

    # -------------------------------------------------------------------------
    # Hardware Reset
    # -------------------------------------------------------------------------
    def reset(self):
        """Resets all physical registers and bus arbitration tracking to power-on state."""
        for r in (
            self._al,
            self._ah,
            self._bl,
            self._bh,
            self._dl,
            self._dh,
            self._fl,
            self._fh,
        ):
            r[:] = b"\x00\x00\x00\x00"
        self._ea[:] = b"\x00\x00"
        self._eb[:] = b"\x00\x00"
        self._c[0] = 0
        self._sp[0] = 0
        self._osp[0] = 0
        self._upc[:] = b"\x00\x00"
        self._status[0] = 0x40  # ZERO = 1
        self.sign_a = 0
        self.sign_b = 0
        self.sign_res = 0
        self.quadrant = 0

        self._last_ha_tick = -1
        self._last_hb_tick = -1
        self._last_res_tick = -1
        self._ha_bus_half = None
        self._hb_bus_reg = None
        self._hb_bus_half = None

    # -------------------------------------------------------------------------
    # Conversion Utilities (for testbenches & loaders)
    # -------------------------------------------------------------------------
    @staticmethod
    def from_int(val: int, length: int, signed: bool = False) -> bytearray:
        """Converts an integer to a Little-Endian bytearray."""
        return bytearray(val.to_bytes(length, byteorder="little", signed=signed))

    @staticmethod
    def to_int(data: Union[bytes, bytearray], signed: bool = False) -> int:
        """Converts a Little-Endian bytearray or bytes to an integer."""
        return int.from_bytes(data, byteorder="little", signed=signed)

    @staticmethod
    def from_f32(val: float) -> bytearray:
        """Converts a Python float to a 4-byte IEEE-754 single-precision Little-Endian bytearray."""
        return bytearray(struct.pack("<f", val))

    @staticmethod
    def to_f32(data: Union[bytes, bytearray]) -> float:
        """Converts a 4-byte Little-Endian IEEE-754 single-precision bytearray or bytes to a Python float."""
        if len(data) != 4:
            raise ValueError(f"Expected 4 bytes for f32 conversion, got {len(data)}")
        return struct.unpack("<f", data)[0]

    @staticmethod
    def from_f64(val: float) -> bytearray:
        """Converts a Python float to an 8-byte IEEE-754 double-precision Little-Endian bytearray."""
        return bytearray(struct.pack("<d", val))

    @staticmethod
    def to_f64(data: Union[bytes, bytearray]) -> float:
        """Converts an 8-byte Little-Endian IEEE-754 double-precision bytearray or bytes to a Python float."""
        if len(data) != 8:
            raise ValueError(f"Expected 8 bytes for f64 conversion, got {len(data)}")
        return struct.unpack("<d", data)[0]

    # -------------------------------------------------------------------------
    # Pretty-Printing for Debugging
    # -------------------------------------------------------------------------
    def dump(self) -> str:
        """Dumps current register state formatted for debugging."""
        flags = []
        if self.get_flag(StatusFlag.BUSY):
            flags.append("BSY")
        if self.get_flag(StatusFlag.ZERO):
            flags.append("Z")
        if self.get_flag(StatusFlag.SIGN):
            flags.append("S")
        if self.get_flag(StatusFlag.CARRY):
            flags.append("C")
        if self.get_flag(StatusFlag.OVERFLOW):
            flags.append("V")
        if self.get_flag(StatusFlag.UNDERFLOW):
            flags.append("U")
        if self.get_flag(StatusFlag.ERR):
            flags.append("ERR")
        if self.get_flag(StatusFlag.DIFF_SIGN):
            flags.append("DS")

        flg_str = " ".join(flags) if flags else "none"

        return (
            f"=== Register File Dump ===\n"
            f"AX: 0x{self.to_int(self._al + self._ah):016X}  (AH: 0x{self.to_int(self._ah):08X}, AL: 0x{self.to_int(self._al):08X})\n"
            f"BX: 0x{self.to_int(self._bl + self._bh):016X}  (BH: 0x{self.to_int(self._bh):08X}, BL: 0x{self.to_int(self._bl):08X})\n"
            f"DX: 0x{self.to_int(self._dl + self._dh):016X}  (DH: 0x{self.to_int(self._dh):08X}, DL: 0x{self.to_int(self._dl):08X})\n"
            f"FX: 0x{self.to_int(self._fl + self._fh):016X}  (FH: 0x{self.to_int(self._fh):08X}, FL: 0x{self.to_int(self._fl):08X})\n"
            f"EA: 0x{self.ea:03X}  EB: 0x{self.eb:03X}  C: 0x{self.c:02X}\n"
            f"SP: 0x{self.sp:02X}  OSP: 0x{self.osp:02X}  UPC: 0x{self.upc:03X}\n"
            f"STATUS: 0x{self.status:02X} [{flg_str}]\n"
            f"=========================="
        )
