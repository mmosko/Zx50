"""Comprehensive unit tests for 32/64-bit barrel shifter primitive."""

import pytest

from fpu_emu.alu.alu import Alu
from fpu_emu.alu.shifter import (
    shifter_core,
    ShiftOp,
    lsl32,
    lsr32,
    asr32,
    lsl64,
    lsr64,
    asr64,
    rrc32,
    rrc64,
)
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers
from fpu_emu.tests.testharness import RegTestHarness


# =============================================================================
# 1. 32-Bit Core Shift Tests
# =============================================================================
@pytest.mark.parametrize(
    "val,shift,op,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        # LSL 32-bit tests
        (0x12345678, 0, ShiftOp.LSL, 0x12345678, False, False, False, False, "LSL shift 0"),
        (0x12345678, 1, ShiftOp.LSL, 0x2468ACF0, False, False, False, False, "LSL shift 1 no carry"),
        (0x80000000, 1, ShiftOp.LSL, 0x00000000, True, True, False, False, "LSL shift 1 carry out MSB -> zero"),
        (0x40000000, 1, ShiftOp.LSL, 0x80000000, False, False, True, False, "LSL shift 1 into sign bit"),
        (0x00000001, 31, ShiftOp.LSL, 0x80000000, False, False, True, False, "LSL shift 31 bit 0 to sign bit"),
        (0x00000003, 31, ShiftOp.LSL, 0x80000000, True, False, True, False, "LSL shift 31 with carry out"),
        (0xFFFFFFFF, 4, ShiftOp.LSL, 0xFFFFFFF0, True, False, True, False, "LSL 0xFFFFFFFF by 4"),
        # LSR 32-bit tests
        (0x12345678, 0, ShiftOp.LSR, 0x12345678, False, False, False, False, "LSR shift 0"),
        (0x12345678, 1, ShiftOp.LSR, 0x091A2B3C, False, False, False, False, "LSR shift 1 even value"),
        (0x12345679, 1, ShiftOp.LSR, 0x091A2B3C, True, False, False, False, "LSR shift 1 odd value -> carry"),
        (0x00000001, 1, ShiftOp.LSR, 0x00000000, True, True, False, False, "LSR shift 1 -> zero with carry"),
        (0x80000000, 31, ShiftOp.LSR, 0x00000001, False, False, False, False, "LSR shift 31 MSB to LSB"),
        (0x80000001, 31, ShiftOp.LSR, 0x00000001, False, False, False, False, "LSR shift 31 bit 0 lost"),
        (0x80000002, 2, ShiftOp.LSR, 0x20000000, True, False, False, False, "LSR zeroes enter MSB"),
        # ASR 32-bit tests
        (0x12345678, 0, ShiftOp.ASR, 0x12345678, False, False, False, False, "ASR positive shift 0"),
        (0x80000000, 0, ShiftOp.ASR, 0x80000000, False, False, True, False, "ASR negative shift 0"),
        (0x12345679, 1, ShiftOp.ASR, 0x091A2B3C, True, False, False, False, "ASR positive shift 1 with carry"),
        (0x80000000, 1, ShiftOp.ASR, 0xC0000000, False, False, True, False, "ASR negative sign extension 1"),
        (0x80000000, 31, ShiftOp.ASR, 0xFFFFFFFF, False, False, True, False, "ASR min int32 shift 31 -> -1"),
        (0x80000001, 1, ShiftOp.ASR, 0xC0000000, True, False, True, False, "ASR negative shift 1 with carry"),
        (0xFFFFFFFF, 5, ShiftOp.ASR, 0xFFFFFFFF, True, False, True, False, "ASR -1 stays -1"),
    ],
)
def test_shifter_core_32(val, shift, op, expected_res, exp_cf, exp_zf, exp_sf, exp_vf, desc):
    val_bytes = Registers.from_int(val, 4)
    res_bytes, cf, zf, sf, vf = shifter_core(val_bytes, shift, op, width_bytes=4)

    assert Registers.to_int(res_bytes) == expected_res, f"Failed {desc}: result mismatch"
    assert cf == exp_cf, f"Failed {desc}: CF mismatch"
    assert zf == exp_zf, f"Failed {desc}: ZF mismatch"
    assert sf == exp_sf, f"Failed {desc}: SF mismatch"
    assert vf == exp_vf, f"Failed {desc}: VF mismatch"


# =============================================================================
# 2. 64-Bit Core Shift Tests
# =============================================================================
@pytest.mark.parametrize(
    "val,shift,op,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        # LSL 64-bit
        (0x00000000FFFFFFFF, 32, ShiftOp.LSL, 0xFFFFFFFF00000000, False, False, True, False, "LSL 64 shift 32"),
        (0x8000000000000000, 1, ShiftOp.LSL, 0x0000000000000000, True, True, False, False, "LSL 64 MSB out -> 0"),
        (0x0000000000000001, 63, ShiftOp.LSL, 0x8000000000000000, False, False, True, False, "LSL 64 shift 63"),
        # LSR 64-bit
        (0xFFFFFFFF00000000, 32, ShiftOp.LSR, 0x00000000FFFFFFFF, False, False, False, False, "LSR 64 shift 32"),
        (0x0000000000000001, 1, ShiftOp.LSR, 0x0000000000000000, True, True, False, False, "LSR 64 bit 0 -> 0"),
        (0x8000000000000000, 63, ShiftOp.LSR, 0x0000000000000001, False, False, False, False, "LSR 64 shift 63"),
        # ASR 64-bit
        (0x8000000000000000, 1, ShiftOp.ASR, 0xC000000000000000, False, False, True, False, "ASR 64 sign-extend 1"),
        (0x8000000000000000, 32, ShiftOp.ASR, 0xFFFFFFFF80000000, False, False, True, False, "ASR 64 shift 32"),
        (0x8000000000000000, 63, ShiftOp.ASR, 0xFFFFFFFFFFFFFFFF, False, False, True, False, "ASR 64 shift 63 -> -1"),
        (0x0000000100000000, 32, ShiftOp.ASR, 0x0000000000000001, False, False, False, False, "ASR 64 pos shift 32"),
    ],
)
def test_shifter_core_64(val, shift, op, expected_res, exp_cf, exp_zf, exp_sf, exp_vf, desc):
    val_bytes = Registers.from_int(val, 8)
    res_bytes, cf, zf, sf, vf = shifter_core(val_bytes, shift, op, width_bytes=8)

    assert Registers.to_int(res_bytes) == expected_res, f"Failed {desc}: result mismatch"
    assert cf == exp_cf, f"Failed {desc}: CF mismatch"
    assert zf == exp_zf, f"Failed {desc}: ZF mismatch"
    assert sf == exp_sf, f"Failed {desc}: SF mismatch"
    assert vf == exp_vf, f"Failed {desc}: VF mismatch"


# =============================================================================
# 3. Hardware Integration & Cycle Timing Tests
# =============================================================================
def test_lsl32_with_counter_c():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(0x0000000F, 4))
    hw.reg.c = 4  # Shift by 4

    lsl32(hw)

    assert hw.clock.cycles == 1  # 1 cycle for 32-bit shift
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x000000F0
    assert not reg.get_flag(StatusFlag.CARRY)
    assert not reg.get_flag(StatusFlag.ZERO)
    assert not reg.get_flag(StatusFlag.SIGN)
    assert not reg.get_flag(StatusFlag.OVERFLOW)


def test_lsr32_with_counter_c():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(0x000000F1, 4))
    hw.reg.c = 1  # Shift by 1 -> bit 0 shifted out

    lsr32(hw)

    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x00000078
    assert reg.get_flag(StatusFlag.CARRY) is True


def test_asr32_negative():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(0x80000000, 4))
    hw.reg.c = 2

    asr32(hw)

    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AL)) == 0xE0000000
    assert reg.get_flag(StatusFlag.SIGN) is True


def test_64bit_shifts_take_2_cycles():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(0x0000000100000000, 8))
    hw.reg.c = 4

    lsl64(hw)
    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x0000001000000000

    lsr64(hw, shift=4)
    assert hw.clock.cycles == 4
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x0000000100000000

    asr64(hw, shift=4)
    assert hw.clock.cycles == 6
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x0000000010000000


def test_alu_class_shifter_delegation():
    hw = Hardware()
    alu = Alu(hw)
    reg = RegTestHarness(hw.reg)

    reg.set(Reg.AL, Registers.from_int(0x10, 4))
    alu.lsl32(shift=2)

    assert Registers.to_int(reg.peek(Reg.AL)) == 0x40
    assert hw.clock.cycles == 1


def test_rrc32():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set_flag(StatusFlag.CARRY, True)
    reg.set(Reg.AL, Registers.from_int(0x00000001, 4))

    rrc32(hw)

    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x80000000
    assert reg.get_flag(StatusFlag.CARRY) is True
    assert reg.get_flag(StatusFlag.SIGN) is True
    assert not reg.get_flag(StatusFlag.ZERO)


def test_rrc64():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    # In carry = 1, AX = 0x0000000000000001 (bit 0 is 1)
    reg.set_flag(StatusFlag.CARRY, True)
    reg.set(Reg.AX, Registers.from_int(0x0000000000000001, 8))

    rrc64(hw)

    assert hw.clock.cycles == 2
    # Result should have bit 63 set (from in_carry), bit 0 shifted out
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x8000000000000000
    assert reg.get_flag(StatusFlag.CARRY) is True  # Out carry is 1
    assert reg.get_flag(StatusFlag.SIGN) is True
    assert not reg.get_flag(StatusFlag.ZERO)

    # Next rotate with carry = 1, bit 0 is 0
    rrc64(hw)
    assert hw.clock.cycles == 4
    # Result should be 0xC000000000000000
    assert Registers.to_int(reg.peek(Reg.AX)) == 0xC000000000000000
    assert reg.get_flag(StatusFlag.CARRY) is False  # Out carry was 0
