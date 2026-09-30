from typing import Union

from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Registers, Reg, StatusFlag, HalfSelect


class RegTestHarness:
    def __init__(self, reg: Registers):
        self._reg = reg

    @property
    def current_tick(self) -> int:
        return self._reg.current_tick

    # -------------------------------------------------------------------------
    # Shared Bus Interface & Timing Collision Protection
    # -------------------------------------------------------------------------
    def set_ha_bus_mux(self, half: Union[HalfSelect, str, int]) -> None:
        self._reg.set_ha_bus_mux(half)

    def set_hb_bus_mux(
        self,
        half: Union[HalfSelect, str, int],
        src: Union[Reg, str],
    ) -> None:
        self._reg.set_hb_bus_mux(half, src)

    def read_ha_bus(self) -> bytearray:
        return self._reg.read_ha_bus()


    def read_hb_bus(self) -> bytearray:
        return self._reg.read_hb_bus()

    def set_res_bus(
        self,
        dst: Union[Reg, str],
        data: Union[bytes, bytearray, int],
    ) -> None:
        self._reg.set_res_bus(dst, data)

    # -------------------------------------------------------------------------
    # Allowed Control & Status Getters / Setters
    # -------------------------------------------------------------------------
    @property
    def status(self) -> int:
        return self._reg.status

    @status.setter
    def status(self, val: int):
        self._reg.status = val

    @property
    def sp(self) -> int:
        return self._reg.sp

    @sp.setter
    def sp(self, val: int):
        self._reg.sp = val

    @property
    def osp(self) -> int:
        return self._reg.osp

    @osp.setter
    def osp(self, val: int):
        self._reg.osp = val

    @property
    def c(self) -> int:
        return self._reg.c

    @c.setter
    def c(self, val: int):
        self._reg.c = val

    @property
    def upc(self) -> int:
        return self._reg.upc

    @upc.setter
    def upc(self, val: int):
        self._reg.upc = val

    @property
    def ea(self) -> int:
        return self._reg.ea

    @ea.setter
    def ea(self, val: int):
        self._reg.ea = val

    @property
    def eb(self) -> int:
        return self._reg.eb

    @eb.setter
    def eb(self, val: int):
        self._reg.eb = val

    # -------------------------------------------------------------------------
    # Status Flag Manipulation
    # -------------------------------------------------------------------------
    def get_flag(self, flag: Union[StatusFlag, int]) -> bool:
        return self._reg.get_flag(flag)

    def set_flag(self, flag: Union[StatusFlag, int], val: bool = True):
        self._reg.set_flag(flag, val)

    def clr_flag(self, flag: Union[StatusFlag, int]):
        self._reg.set_flag(flag, False)

    def clear_flags(self):
        self._reg.clear_flags()

    # -------------------------------------------------------------------------
    # Public Access & Test Bench Backdoors
    # -------------------------------------------------------------------------

    def set(
        self,
        reg: Union[Reg, str],
        val: Union[bytes, bytearray, int],
    ) -> None:
        """Sets register contents (delegates to load_test_vector)."""
        self.load_test_vector(reg, val)

    # -------------------------------------------------------------------------
    # Test Fixture Backdoors (Explicitly labeled for non-hardware test code)
    # -------------------------------------------------------------------------
    def peek(self, reg: Union[Reg, str]) -> bytearray:
        """Test fixture backdoor: inspects raw register bytes bypassing bus muxes."""
        if isinstance(reg, str):
            reg = Reg[reg.upper()]

        if reg == Reg.AL:
            return bytearray(self._reg._al)
        elif reg == Reg.AH:
            return bytearray(self._reg._ah)
        elif reg == Reg.BL:
            return bytearray(self._reg._bl)
        elif reg == Reg.BH:
            return bytearray(self._reg._bh)
        elif reg == Reg.DL:
            return bytearray(self._reg._dl)
        elif reg == Reg.DH:
            return bytearray(self._reg._dh)
        elif reg == Reg.FL:
            return bytearray(self._reg._fl)
        elif reg == Reg.FH:
            return bytearray(self._reg._fh)
        elif reg == Reg.AX:
            return bytearray(self._reg._al + self._reg._ah)
        elif reg == Reg.BX:
            return bytearray(self._reg._bl + self._reg._bh)
        elif reg == Reg.DX:
            return bytearray(self._reg._dl + self._reg._dh)
        elif reg == Reg.FX:
            return bytearray(self._reg._fl + self._reg._fh)
        elif reg == Reg.EA:
            return bytearray(self._reg._ea)
        elif reg == Reg.EB:
            return bytearray(self._reg._eb)
        elif reg == Reg.C:
            return bytearray(self._reg._c)
        elif reg == Reg.STATUS:
            return bytearray(self._reg._status)
        elif reg == Reg.SP:
            return bytearray(self._reg._sp)
        elif reg == Reg.OSP:
            return bytearray(self._reg._osp)
        elif reg == Reg.UPC:
            return bytearray(self._reg._upc)
        else:
            raise ValueError(f"Unsupported register: {reg}")

    def load_test_vector(
        self,
        reg: Union[Reg, str],
        val: Union[bytes, bytearray, int],
    ) -> None:
        """Test fixture backdoor: sets register state directly bypassing bus timing."""
        if isinstance(reg, str):
            reg = Reg[reg.upper()]

        if isinstance(val, int):
            length = reg.byte_length
            val = val.to_bytes(length, byteorder="little", signed=(val < 0))

        if not isinstance(val, (bytes, bytearray)):
            raise TypeError(f"val must be bytes, bytearray, or int, got {type(val).__name__}")

        expected_len = reg.byte_length
        if len(val) != expected_len:
            raise ValueError(
                f"Expected {expected_len} bytes for register {reg.name}, got {len(val)}"
            )

        if reg == Reg.AL:
            self._reg._al[:] = val
        elif reg == Reg.AH:
            self._reg._ah[:] = val
        elif reg == Reg.BL:
            self._reg._bl[:] = val
        elif reg == Reg.BH:
            self._reg._bh[:] = val
        elif reg == Reg.DL:
            self._reg._dl[:] = val
        elif reg == Reg.DH:
            self._reg._dh[:] = val
        elif reg == Reg.FL:
            self._reg._fl[:] = val
        elif reg == Reg.FH:
            self._reg._fh[:] = val
        elif reg == Reg.AX:
            self._reg._al[:] = val[0:4]
            self._reg._ah[:] = val[4:8]
        elif reg == Reg.BX:
            self._reg._bl[:] = val[0:4]
            self._reg._bh[:] = val[4:8]
        elif reg == Reg.DX:
            self._reg._dl[:] = val[0:4]
            self._reg._dh[:] = val[4:8]
        elif reg == Reg.FX:
            self._reg._fl[:] = val[0:4]
            self._reg._fh[:] = val[4:8]
        elif reg == Reg.EA:
            self._reg._ea[:] = val
        elif reg == Reg.EB:
            self._reg._eb[:] = val
        elif reg == Reg.C:
            self._reg._c[0] = val[0] & 0x3F
        elif reg == Reg.STATUS:
            self._reg._status[0] = val[0]
        elif reg == Reg.SP:
            self._reg._sp[0] = val[0]
        elif reg == Reg.OSP:
            self._reg._osp[0] = val[0]
        elif reg == Reg.UPC:
            self.upc = val[0] | (val[1] << 8)
        else:
            raise ValueError(f"Unsupported register: {reg}")

    # -------------------------------------------------------------------------
    # Hardware Reset
    # -------------------------------------------------------------------------
    def reset(self):
        self._reg.reset()

    # -------------------------------------------------------------------------
    # Pretty-Printing for Debugging
    # -------------------------------------------------------------------------
    def dump(self) -> str:
        return self._reg.dump()




class HardwareTestHarness:
    def __init__(self, hw: Hardware):
        self.reg = RegTestHarness(hw.reg)
        # todo: add them for clock and
