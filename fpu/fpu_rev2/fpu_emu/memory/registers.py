"""Physical and logical register file implementation for Zx50 FPU.

All physical registers are stored internally as Little-Endian bytearrays.
Compound 64-bit registers (AX, BX, DX, FX) map directly to pairs of 32-bit registers.
Direct member variable manipulation is discouraged; callers must use the public API.
"""

from enum import Enum
import struct
from typing import Union


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
        if self in (Reg.AX, Reg.BX, Reg.DX, Reg.FX):
            return 8
        elif self in (Reg.AL, Reg.AH, Reg.BL, Reg.BH, Reg.DL, Reg.DH, Reg.FL, Reg.FH):
            return 4
        elif self in (Reg.EA, Reg.EB, Reg.UPC):
            return 2
        elif self in (Reg.C, Reg.STATUS, Reg.SP, Reg.OSP):
            return 1
        raise ValueError(f"Unknown byte length for register {self}")


class StatusFlag(Enum):
    """Status register flag bit allocations (SystemDesign.md Section 2.1)."""

    DIFF_SIGN = 0  # Bit 0: Effective subtraction / operand signs differ
    ERR = 1        # Bit 1: Error flag (Division by zero, domain errors, stack traps)
    UNDERFLOW = 2  # Bit 2: Stack or floating-point underflow
    OVERFLOW = 3   # Bit 3: Stack, integer, or floating-point overflow
    CARRY = 4      # Bit 4: Arithmetic carry or borrow
    SIGN = 5       # Bit 5: Sign flag (1 = Negative)
    ZERO = 6       # Bit 6: Zero flag (1 = Result is zero)
    BUSY = 7       # Bit 7: Hardware execution busy flag


class Registers:
    """Register file holding all physical FPU registers."""

    def __init__(self):
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

        # Operand Sign latches
        self.sign_a: int = 0
        self.sign_b: int = 0
        self.sign_res: int = 0

    # -------------------------------------------------------------------------
    # Properties for int-access convenience
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
    # Compound 64-bit register properties
    # -------------------------------------------------------------------------
    @property
    def ax(self) -> bytearray:
        """64-bit compound {AH, AL} (Little-Endian: AL is low, AH is high)."""
        return self.get(Reg.AX)

    @ax.setter
    def ax(self, val: Union[bytes, bytearray]):
        self.set(Reg.AX, val)

    @property
    def bx(self) -> bytearray:
        """64-bit compound {BH, BL}."""
        return self.get(Reg.BX)

    @bx.setter
    def bx(self, val: Union[bytes, bytearray]):
        self.set(Reg.BX, val)

    @property
    def dx(self) -> bytearray:
        """64-bit compound {DH, DL}."""
        return self.get(Reg.DX)

    @dx.setter
    def dx(self, val: Union[bytes, bytearray]):
        self.set(Reg.DX, val)

    @property
    def fx(self) -> bytearray:
        """64-bit compound {FH, FL}."""
        return self.get(Reg.FX)

    @fx.setter
    def fx(self, val: Union[bytes, bytearray]):
        self.set(Reg.FX, val)

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
            self._status[0] |= (1 << bit_idx)
        else:
            self._status[0] &= ~(1 << bit_idx)

    def clr_flag(self, flag: Union[StatusFlag, int]):
        """Explicitly clears an individual status flag."""
        self.set_flag(flag, False)

    def clear_flags(self):
        """Clears all status flags to zero."""
        self._status[0] = 0

    # -------------------------------------------------------------------------
    # Core get / set API
    # -------------------------------------------------------------------------
    def get(self, reg: Union[Reg, str]) -> bytearray:
        """Gets a copy of the specified register as a bytearray."""
        if isinstance(reg, str):
            reg = Reg[reg.upper()]

        if reg == Reg.AL:
            return bytearray(self._al)
        elif reg == Reg.AH:
            return bytearray(self._ah)
        elif reg == Reg.BL:
            return bytearray(self._bl)
        elif reg == Reg.BH:
            return bytearray(self._bh)
        elif reg == Reg.DL:
            return bytearray(self._dl)
        elif reg == Reg.DH:
            return bytearray(self._dh)
        elif reg == Reg.FL:
            return bytearray(self._fl)
        elif reg == Reg.FH:
            return bytearray(self._fh)
        elif reg == Reg.AX:
            return bytearray(self._al + self._ah)
        elif reg == Reg.BX:
            return bytearray(self._bl + self._bh)
        elif reg == Reg.DX:
            return bytearray(self._dl + self._dh)
        elif reg == Reg.FX:
            return bytearray(self._fl + self._fh)
        elif reg == Reg.EA:
            return bytearray(self._ea)
        elif reg == Reg.EB:
            return bytearray(self._eb)
        elif reg == Reg.C:
            return bytearray(self._c)
        elif reg == Reg.STATUS:
            return bytearray(self._status)
        elif reg == Reg.SP:
            return bytearray(self._sp)
        elif reg == Reg.OSP:
            return bytearray(self._osp)
        elif reg == Reg.UPC:
            return bytearray(self._upc)
        else:
            raise ValueError(f"Unsupported register: {reg}")

    def set(self, reg: Union[Reg, str], val: Union[bytes, bytearray]):
        """Sets the specified register from bytes or bytearray."""
        if isinstance(reg, str):
            reg = Reg[reg.upper()]

        if not isinstance(val, (bytes, bytearray)):
            raise TypeError(f"val must be bytes or bytearray, got {type(val).__name__}")

        expected_len = reg.byte_length
        if len(val) != expected_len:
            raise ValueError(
                f"Expected {expected_len} bytes for register {reg.name}, got {len(val)}"
            )

        if reg == Reg.AL:
            self._al[:] = val
        elif reg == Reg.AH:
            self._ah[:] = val
        elif reg == Reg.BL:
            self._bl[:] = val
        elif reg == Reg.BH:
            self._bh[:] = val
        elif reg == Reg.DL:
            self._dl[:] = val
        elif reg == Reg.DH:
            self._dh[:] = val
        elif reg == Reg.FL:
            self._fl[:] = val
        elif reg == Reg.FH:
            self._fh[:] = val
        elif reg == Reg.AX:
            self._al[:] = val[0:4]
            self._ah[:] = val[4:8]
        elif reg == Reg.BX:
            self._bl[:] = val[0:4]
            self._bh[:] = val[4:8]
        elif reg == Reg.DX:
            self._dl[:] = val[0:4]
            self._dh[:] = val[4:8]
        elif reg == Reg.FX:
            self._fl[:] = val[0:4]
            self._fh[:] = val[4:8]
        elif reg == Reg.EA:
            self._ea[:] = val
        elif reg == Reg.EB:
            self._eb[:] = val
        elif reg == Reg.C:
            self._c[0] = val[0] & 0x3F
        elif reg == Reg.STATUS:
            self._status[0] = val[0]
        elif reg == Reg.SP:
            self._sp[0] = val[0]
        elif reg == Reg.OSP:
            self._osp[0] = val[0]
        elif reg == Reg.UPC:
            self.upc = val[0] | (val[1] << 8)
        else:
            raise ValueError(f"Unsupported register: {reg}")

    # -------------------------------------------------------------------------
    # Hardware Reset
    # -------------------------------------------------------------------------
    def reset(self):
        """Performs a master soft reset matching FPGA RESET (0xFF).

        Zeroes general/math registers, exponents, counters, and pointers.
        Initializes STATUS to 0x40 (ZERO flag asserted).
        """
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
        flag_str = " ".join(flags) if flags else "-"

        # Little-Endian display: bytes displayed MSB-first for human reading
        def hex_rev(b: bytearray) -> str:
            return bytes(reversed(b)).hex().upper()

        lines = [
            f"AL: {hex_rev(self._al)}  AH: {hex_rev(self._ah)}  (AX: {hex_rev(self.ax)})",
            f"BL: {hex_rev(self._bl)}  BH: {hex_rev(self._bh)}  (BX: {hex_rev(self.bx)})",
            f"DL: {hex_rev(self._dl)}  DH: {hex_rev(self._dh)}  (DX: {hex_rev(self.dx)})",
            f"FL: {hex_rev(self._fl)}  FH: {hex_rev(self._fh)}  (FX: {hex_rev(self.fx)})",
            f"EA: {hex_rev(self._ea)}  EB: {hex_rev(self._eb)}  C: {self.c:02X}",
            f"SP: {self.sp:02X}        OSP: {self.osp:02X}       UPC: {self.upc:04X}",
            f"STATUS: 0x{self.status:02X} [{flag_str}]",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<Registers SP={self.sp:02X} STATUS={self.status:02X} UPC={self.upc:04X}>"
