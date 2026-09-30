"""Unit tests for SysMEM hardware stack operations."""

import pytest
from fpu_emu.hardware import Hardware
from fpu_emu.memory import stack
from fpu_emu.memory.registers import Reg, StatusFlag, Registers
from fpu_emu.tests.testharness import RegTestHarness


def test_push_pop_32():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(0x12345678, 4))

    assert hw.reg.sp == 0
    assert hw.clock.cycles == 0

    stack.push32(hw, Reg.AL)
    assert hw.reg.sp == 4
    assert hw.clock.cycles == 1  # 1 memory cycle

    stack.pop32(hw, Reg.BL)
    assert hw.reg.sp == 0
    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.BL)) == 0x12345678


def test_push_pop_64():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(0x1122334455667788, 8))

    stack.push64(hw, Reg.AX)
    assert hw.reg.sp == 8
    assert hw.clock.cycles == 2  # 2 memory cycles

    stack.pop64(hw, Reg.BX)
    assert hw.reg.sp == 0
    assert hw.clock.cycles == 4
    assert Registers.to_int(reg.peek(Reg.BX)) == 0x1122334455667788


def test_stack_underflow():
    hw = Hardware()
    assert hw.reg.sp == 0

    stack.pop32(hw, Reg.AL)
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW) is True
    assert hw.reg.get_flag(StatusFlag.ERR) is True

    hw.reset()
    stack.pop64(hw, Reg.AX)
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW) is True
    assert hw.reg.get_flag(StatusFlag.ERR) is True


def test_stack_overflow():
    hw = Hardware()
    # SP is an 8-bit register (0..255). 254 + 4 = 258 > 256 bytes
    hw.reg.sp = 254

    stack.push32(hw, Reg.AL)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW) is True
    assert hw.reg.get_flag(StatusFlag.ERR) is True

    hw.reset()
    # 250 + 8 = 258 > 256 bytes
    hw.reg.sp = 250
    stack.push64(hw, Reg.AX)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW) is True
    assert hw.reg.get_flag(StatusFlag.ERR) is True
