"""Unit tests for register swap (swap.py) operations."""

import pytest
from fpu_emu.hardware import Hardware
from fpu_emu.memory import swap
from fpu_emu.memory.registers import (
    Reg,
    Registers,
    StatusFlag,
)
from fpu_emu.tests.testharness import RegTestHarness


class TestSwap:
    """Test suite for swap32, swap64, swap_exp, and swap dispatch via microcode moves."""

    def setup_method(self):
        self.hw = Hardware()
        self.reg = RegTestHarness(self.hw.reg)

    def test_swap32_al_bl_and_signs(self):
        self.reg.set(Reg.AL, 0x11111111)
        self.reg.set(Reg.BL, 0x22222222)
        self.hw.reg.sign_a = 1
        self.hw.reg.sign_b = 0

        start_cycles = self.hw.clock.cycles
        # Option B: 3 cycles (FL <- BL, BL <- AL, AL <- FL)
        swap.swap32(self.hw, Reg.AL, Reg.BL)

        assert self.hw.clock.cycles == start_cycles + 3
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 0x22222222
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 0x11111111
        assert self.hw.reg.sign_a == 0
        assert self.hw.reg.sign_b == 1

        # Swap back with reversed order
        swap.swap32(self.hw, Reg.BL, Reg.AL)
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 0x11111111
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 0x22222222
        assert self.hw.reg.sign_a == 1
        assert self.hw.reg.sign_b == 0

    def test_swap32_other_registers(self):
        self.reg.set(Reg.AH, 0xAAAAAAAA)
        self.reg.set(Reg.BH, 0xBBBBBBBB)
        swap.swap32(self.hw, Reg.AH, Reg.BH)
        assert Registers.to_int(self.reg.peek(Reg.AH)) == 0xBBBBBBBB
        assert Registers.to_int(self.reg.peek(Reg.BH)) == 0xAAAAAAAA

        self.reg.set(Reg.DL, 0xDDDDDDDD)
        self.reg.set(Reg.DH, 0x12345678)
        swap.swap32(self.hw, Reg.DL, Reg.DH)
        assert Registers.to_int(self.reg.peek(Reg.DL)) == 0x12345678
        assert Registers.to_int(self.reg.peek(Reg.DH)) == 0xDDDDDDDD

    def test_swap32_same_register_noop(self):
        self.reg.set(Reg.AL, 0x12345678)
        start_cycles = self.hw.clock.cycles
        swap.swap32(self.hw, Reg.AL, Reg.AL)
        assert self.hw.clock.cycles == start_cycles
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 0x12345678

    def test_swap64_ax_bx(self):
        val_a = 0x0123456789ABCDEF
        val_b = 0xFEDCBA9876543210
        self.reg.set(Reg.AX, val_a)
        self.reg.set(Reg.BX, val_b)
        self.hw.reg.sign_a = 0
        self.hw.reg.sign_b = 1

        start_cycles = self.hw.clock.cycles
        # Option B: 6 cycles total (3 for low halves, 3 for high halves)
        swap.swap64(self.hw, Reg.AX, Reg.BX)

        assert self.hw.clock.cycles == start_cycles + 6
        assert Registers.to_int(self.reg.peek(Reg.AX)) == val_b
        assert Registers.to_int(self.reg.peek(Reg.BX)) == val_a
        assert self.hw.reg.sign_a == 1
        assert self.hw.reg.sign_b == 0

    def test_swap64_ax_dx(self):
        val_a = 0x0123456789ABCDEF
        val_d = 0x1122334455667788
        self.reg.set(Reg.AX, val_a)
        self.reg.set(Reg.DX, val_d)

        swap.swap64(self.hw, Reg.AX, Reg.DX)
        assert Registers.to_int(self.reg.peek(Reg.AX)) == val_d
        assert Registers.to_int(self.reg.peek(Reg.DX)) == val_a

    def test_swap64_same_register_noop(self):
        self.reg.set(Reg.AX, 0x1234567890ABCDEF)
        start_cycles = self.hw.clock.cycles
        swap.swap64(self.hw, Reg.AX, Reg.AX)
        assert self.hw.clock.cycles == start_cycles
        assert Registers.to_int(self.reg.peek(Reg.AX)) == 0x1234567890ABCDEF

    def test_swap_exp(self):
        self.hw.reg.ea = 127
        self.hw.reg.eb = 1023

        start_cycles = self.hw.clock.cycles
        swap.swap_exp(self.hw)

        assert self.hw.clock.cycles == start_cycles + 3
        assert self.hw.reg.ea == 1023
        assert self.hw.reg.eb == 127

    def test_swap_generic_dispatch(self):
        # Exponents
        self.hw.reg.ea = 10
        self.hw.reg.eb = 20
        swap.swap(self.hw, Reg.EA, Reg.EB)
        assert self.hw.reg.ea == 20
        assert self.hw.reg.eb == 10

        # 64-bit
        self.reg.set(Reg.AX, 1)
        self.reg.set(Reg.BX, 2)
        swap.swap(self.hw, Reg.AX, Reg.BX)
        assert Registers.to_int(self.reg.peek(Reg.AX)) == 2
        assert Registers.to_int(self.reg.peek(Reg.BX)) == 1

        # 32-bit
        self.reg.set(Reg.AL, 100)
        self.reg.set(Reg.BL, 200)
        swap.swap(self.hw, Reg.AL, Reg.BL)
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 200
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 100

        # String register names
        swap.swap32(self.hw, "AL", "BL")
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 100
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 200

        swap.swap(self.hw, "AL", "BL")
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 200
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 100

        self.reg.set(Reg.AX, 10)
        self.reg.set(Reg.BX, 20)
        swap.swap64(self.hw, "AX", "BX")
        assert Registers.to_int(self.reg.peek(Reg.AX)) == 20
        assert Registers.to_int(self.reg.peek(Reg.BX)) == 10

        swap.swap(self.hw, "AX", "BX")
        assert Registers.to_int(self.reg.peek(Reg.AX)) == 10
        assert Registers.to_int(self.reg.peek(Reg.BX)) == 20

        swap.swap(self.hw, "EA", "EB")
        assert self.hw.reg.ea == 10
        assert self.hw.reg.eb == 20

    def test_flags_unaffected(self):
        self.hw.reg.set_flag(StatusFlag.ZERO, True)
        self.hw.reg.set_flag(StatusFlag.SIGN, True)
        self.hw.reg.set_flag(StatusFlag.CARRY, True)
        self.hw.reg.set_flag(StatusFlag.OVERFLOW, True)

        self.reg.set(Reg.AL, 1)
        self.reg.set(Reg.BL, 2)
        swap.swap32(self.hw, Reg.AL, Reg.BL)
        swap.swap64(self.hw, Reg.AX, Reg.BX)
        swap.swap_exp(self.hw)

        assert self.hw.reg.get_flag(StatusFlag.ZERO)
        assert self.hw.reg.get_flag(StatusFlag.SIGN)
        assert self.hw.reg.get_flag(StatusFlag.CARRY)
        assert self.hw.reg.get_flag(StatusFlag.OVERFLOW)

    def test_errors_and_conflicts(self):
        # Incompatible registers
        with pytest.raises(ValueError, match="swap32 cannot be used with 64-bit registers"):
            swap.swap32(self.hw, Reg.AX, Reg.BL)

        with pytest.raises(ValueError, match="Unsupported registers for swap32"):
            swap.swap32(self.hw, Reg.SP, Reg.BL)

        with pytest.raises(ValueError, match="swap64 requires 64-bit compound registers"):
            swap.swap64(self.hw, Reg.AL, Reg.BL)

        with pytest.raises(ValueError, match="Mismatched or unsupported registers for SWAP"):
            swap.swap(self.hw, Reg.AL, Reg.AX)

        # Volatile scratch register FL/FH/FX cannot be swapped
        with pytest.raises(ValueError, match="Cannot swap volatile scratch register FL/FH"):
            swap.swap32(self.hw, Reg.AL, Reg.FL)

        with pytest.raises(ValueError, match="Cannot swap volatile scratch register FL/FH"):
            swap.swap32(self.hw, Reg.FH, Reg.BL)

        with pytest.raises(ValueError, match="Cannot swap volatile scratch register FX"):
            swap.swap64(self.hw, Reg.AX, Reg.FX)
