"""Unit tests for register-to-register move (mov.py) operations."""

import pytest
from fpu_emu.hardware import Hardware
from fpu_emu.memory import mov
from fpu_emu.memory.registers import Reg, Registers, StatusFlag
from fpu_emu.tests.testharness import RegTestHarness


class TestMov:
    """Test suite for mov32, mov64, and mov dispatch."""

    def setup_method(self):
        self.hw = Hardware()
        self.reg = RegTestHarness(self.hw.reg)

    def test_mov32_general_registers(self):
        # AL -> BL
        self.reg.set(Reg.AL, Registers.from_int(0x12345678, 4))
        start_cycles = self.hw.clock.cycles
        mov.mov32(self.hw, Reg.BL, Reg.AL)
        assert self.hw.clock.cycles == start_cycles + 1
        assert self.reg.peek(Reg.BL) == bytearray(b"\x78\x56\x34\x12")
        assert self.reg.peek(Reg.AL) == bytearray(b"\x78\x56\x34\x12")

        # BL -> DL
        mov.mov32(self.hw, Reg.DL, Reg.BL)
        assert self.reg.peek(Reg.DL) == bytearray(b"\x78\x56\x34\x12")

        # DL -> FL
        mov.mov32(self.hw, Reg.FL, Reg.DL)
        assert self.reg.peek(Reg.FL) == bytearray(b"\x78\x56\x34\x12")

    def test_mov32_high_half_registers(self):
        # AH -> BH
        self.reg.set(Reg.AH, Registers.from_int(0xAABBCCDD, 4))
        start_cycles = self.hw.clock.cycles
        mov.mov32(self.hw, Reg.BH, Reg.AH)
        assert self.hw.clock.cycles == start_cycles + 1
        assert self.reg.peek(Reg.BH) == bytearray(b"\xdd\xcc\xbb\xaa")

        # BH -> DH -> FH
        mov.mov32(self.hw, Reg.DH, Reg.BH)
        assert self.reg.peek(Reg.DH) == bytearray(b"\xdd\xcc\xbb\xaa")
        mov.mov32(self.hw, Reg.FH, Reg.DH)
        assert self.reg.peek(Reg.FH) == bytearray(b"\xdd\xcc\xbb\xaa")

        # AH -> BL (cross half)
        mov.mov32(self.hw, Reg.BL, Reg.AH)
        assert self.reg.peek(Reg.BL) == bytearray(b"\xdd\xcc\xbb\xaa")

    def test_mov32_control_and_exponent_registers(self):
        # EA -> EB
        self.hw.reg.ea = 0x0123
        mov.mov32(self.hw, Reg.EB, Reg.EA)
        assert self.hw.reg.eb == 0x0123

        # EB -> EA
        self.hw.reg.eb = 0x0456
        mov.mov32(self.hw, Reg.EA, Reg.EB)
        assert self.hw.reg.ea == 0x0456

        # C -> AL
        self.hw.reg.c = 42
        mov.mov32(self.hw, Reg.AL, Reg.C)
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 42

        # AL -> C
        self.reg.set(Reg.AL, Registers.from_int(37, 4))
        mov.mov32(self.hw, Reg.C, Reg.AL)
        assert self.hw.reg.c == 37

    def test_mov64_compound_registers(self):
        # AX -> BX
        val = 0x0123456789ABCDEF
        self.reg.set(Reg.AX, Registers.from_int(val, 8))
        start_cycles = self.hw.clock.cycles
        mov.mov64(self.hw, Reg.BX, Reg.AX)
        assert self.hw.clock.cycles == start_cycles + 2
        assert Registers.to_int(self.reg.peek(Reg.BX)) == val
        assert Registers.to_int(self.reg.peek(Reg.AX)) == val

        # BX -> DX
        mov.mov64(self.hw, Reg.DX, Reg.BX)
        assert Registers.to_int(self.reg.peek(Reg.DX)) == val

        # DX -> FX
        mov.mov64(self.hw, Reg.FX, Reg.DX)
        assert Registers.to_int(self.reg.peek(Reg.FX)) == val

    def test_mov_generic_dispatch(self):
        # 32-bit dispatch
        self.reg.set(Reg.AL, Registers.from_int(0xDEADBEEF, 4))
        mov.mov(self.hw, Reg.BL, Reg.AL)
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 0xDEADBEEF

        # 64-bit dispatch
        self.reg.set(Reg.AX, Registers.from_int(0xCAFEBABE11223344, 8))
        mov.mov(self.hw, Reg.BX, Reg.AX)
        assert Registers.to_int(self.reg.peek(Reg.BX)) == 0xCAFEBABE11223344

        # String register names
        self.reg.set(Reg.AL, Registers.from_int(0x12344321, 4))
        mov.mov32(self.hw, "BL", "AL")
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 0x12344321

        self.reg.set(Reg.BX, Registers.from_int(0x1122334455667788, 8))
        mov.mov64(self.hw, "DX", "BX")
        assert Registers.to_int(self.reg.peek(Reg.DX)) == 0x1122334455667788

        mov.mov(self.hw, "FL", "BL")
        assert Registers.to_int(self.reg.peek(Reg.FL)) == 0x55667788
        mov.mov(self.hw, "FX", "DX")
        assert Registers.to_int(self.reg.peek(Reg.FX)) == 0x1122334455667788

    def test_flags_unaffected(self):
        self.hw.reg.set_flag(StatusFlag.ZERO, True)
        self.hw.reg.set_flag(StatusFlag.SIGN, True)
        self.hw.reg.set_flag(StatusFlag.CARRY, True)
        self.hw.reg.set_flag(StatusFlag.OVERFLOW, True)

        self.reg.set(Reg.AL, Registers.from_int(0, 4))
        mov.mov32(self.hw, Reg.BL, Reg.AL)

        assert self.hw.reg.get_flag(StatusFlag.ZERO)
        assert self.hw.reg.get_flag(StatusFlag.SIGN)
        assert self.hw.reg.get_flag(StatusFlag.CARRY)
        assert self.hw.reg.get_flag(StatusFlag.OVERFLOW)

    def test_invalid_mov_combinations(self):
        with pytest.raises(ValueError, match="mov32 called with 64-bit register"):
            mov.mov32(self.hw, Reg.AX, Reg.BL)

        with pytest.raises(ValueError, match="mov32 called with 64-bit register"):
            mov.mov32(self.hw, Reg.AL, Reg.BX)

        with pytest.raises(ValueError, match="mov64 requires 64-bit compound registers"):
            mov.mov64(self.hw, Reg.AL, Reg.BL)

        with pytest.raises(ValueError, match="Mismatched register widths for MOV"):
            mov.mov(self.hw, Reg.AX, Reg.BL)

        with pytest.raises(ValueError, match="Mismatched register widths for MOV"):
            mov.mov(self.hw, Reg.AL, Reg.BX)
