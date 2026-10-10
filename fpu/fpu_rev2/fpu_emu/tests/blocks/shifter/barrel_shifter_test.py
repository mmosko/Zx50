"""Unit tests for the BarrelShifter hardware module."""

import pytest
from fpu_emu.blocks.shifter.barrel_shifter import BarrelShifter
from fpu_emu.blocks.shifter.shifter_adder import ShifterAdder
from fpu_emu.hardware.clock import Clock


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def sub_adder(clock: Clock) -> ShifterAdder:
    return ShifterAdder("test_sub_adder", clock)


@pytest.fixture
def cmp_adder(clock: Clock) -> ShifterAdder:
    return ShifterAdder("test_cmp_adder", clock)


def test_lsl_32_zero_count(sub_adder: ShifterAdder):
    res = BarrelShifter.lsl_32(0x12345678, 0, sub_adder)
    assert res.res == 0x12345678
    assert not res.cf
    assert not res.zf
    assert not res.sf


def test_lsl_32_single_bit_shift(sub_adder: ShifterAdder):
    # Bit 31 is 1 -> shifts into CF, MSB becomes 0
    res = BarrelShifter.lsl_32(0x80000001, 1, sub_adder)
    assert res.res == 0x00000002
    assert res.cf
    assert not res.zf
    assert not res.sf


def test_lsl_32_sign_flag(sub_adder: ShifterAdder):
    # Bit 30 is 1 -> shifts into bit 31 -> sets SF
    res = BarrelShifter.lsl_32(0x40000000, 1, sub_adder)
    assert res.res == 0x80000000
    assert not res.cf
    assert not res.zf
    assert res.sf


def test_lsl_32_count_32(sub_adder: ShifterAdder):
    # Shift count 32: bit 0 shifted out into CF, result becomes 0
    res = BarrelShifter.lsl_32(0x00000001, 32, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf
    assert not res.sf


def test_lsl_32_count_greater_than_32(sub_adder: ShifterAdder):
    res = BarrelShifter.lsl_32(0xFFFFFFFF, 33, sub_adder)
    assert res.res == 0
    assert not res.cf
    assert res.zf
    assert not res.sf


def test_lsr_32_zero_count(sub_adder: ShifterAdder):
    res = BarrelShifter.lsr_32(0x12345678, 0, sub_adder)
    assert res.res == 0x12345678
    assert not res.cf
    assert not res.zf
    assert not res.sf


def test_lsr_32_single_bit_shift(sub_adder: ShifterAdder):
    # Example from SystemReference.md: 0x00000005 >> 1 -> 0x00000002, CF=1
    res = BarrelShifter.lsr_32(0x00000005, 1, sub_adder)
    assert res.res == 0x00000002
    assert res.cf
    assert not res.zf
    assert not res.sf


def test_lsr_32_count_32(sub_adder: ShifterAdder):
    # Bit 31 shifted out into CF, result becomes 0
    res = BarrelShifter.lsr_32(0x80000000, 32, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf
    assert not res.sf


def test_lsr_32_count_greater_than_32(sub_adder: ShifterAdder):
    res = BarrelShifter.lsr_32(0xFFFFFFFF, 33, sub_adder)
    assert res.res == 0
    assert not res.cf
    assert res.zf
    assert not res.sf


def test_lsl_64(clock: Clock, sub_adder: ShifterAdder):
    # Shift 64-bit word across 32-bit boundary
    val = 0x0000000000000001
    res = BarrelShifter.lsl_64(val, 32, sub_adder)
    assert res.res == 0x0000000100000000
    assert not res.cf
    assert not res.zf
    assert not res.sf
    clock.tick()

    # Bit 63 shifted out
    val_hi_bit = 0x8000000000000000
    res = BarrelShifter.lsl_64(val_hi_bit, 1, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf
    assert not res.sf
    clock.tick()

    # Sign bit set on 64-bit result
    val_bit_62 = 0x4000000000000000
    res = BarrelShifter.lsl_64(val_bit_62, 1, sub_adder)
    assert res.res == 0x8000000000000000
    assert not res.cf
    assert not res.zf
    assert res.sf
    clock.tick()

    # Shift count 64
    res = BarrelShifter.lsl_64(0x0000000000000001, 64, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf


def test_lsr_64(clock: Clock, sub_adder: ShifterAdder):
    # Shift 64-bit word right across 32-bit boundary
    val = 0x0000000100000000
    res = BarrelShifter.lsr_64(val, 32, sub_adder)
    assert res.res == 0x0000000000000001
    assert not res.cf
    assert not res.zf
    assert not res.sf
    clock.tick()

    # Bit 0 shifted out
    res = BarrelShifter.lsr_64(0x0000000000000001, 1, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf
    clock.tick()

    # Shift count 64
    res = BarrelShifter.lsr_64(0x8000000000000000, 64, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf
    clock.tick()

    # Shift count > 64
    res = BarrelShifter.lsr_64(0xFFFFFFFFFFFFFFFF, 65, sub_adder)
    assert res.res == 0
    assert not res.cf
    assert res.zf


def test_lsl_64_count_greater_than_64(sub_adder: ShifterAdder):
    res = BarrelShifter.lsl_64(0xFFFFFFFFFFFFFFFF, 65, sub_adder)
    assert res.res == 0
    assert not res.cf
    assert res.zf


def test_asl_32(clock: Clock, sub_adder: ShifterAdder, cmp_adder: ShifterAdder):
    # Zero count
    res = BarrelShifter.asl_32(0x12345678, 0, sub_adder, cmp_adder)
    assert res.res == 0x12345678
    assert not res.cf
    assert not res.vf
    assert not res.sf
    assert not res.zf

    # Shift without overflow (sign bit unchanged: 0 -> 0)
    res = BarrelShifter.asl_32(0x20000000, 1, sub_adder, cmp_adder)
    assert res.res == 0x40000000
    assert not res.cf
    assert not res.vf
    assert not res.sf
    assert not res.zf
    clock.tick()

    # Shift with overflow (sign bit changed: 0 -> 1)
    res = BarrelShifter.asl_32(0x40000000, 1, sub_adder, cmp_adder)
    assert res.res == 0x80000000
    assert not res.cf
    assert res.vf
    assert res.sf
    assert not res.zf
    clock.tick()

    # Negative shift without overflow (sign bit unchanged: 1 -> 1)
    res = BarrelShifter.asl_32(0xC0000000, 1, sub_adder, cmp_adder)
    assert res.res == 0x80000000
    assert res.cf
    assert not res.vf
    assert res.sf
    assert not res.zf
    clock.tick()

    # Negative shift with overflow (sign bit changed: 1 -> 0)
    res = BarrelShifter.asl_32(0x80000000, 1, sub_adder, cmp_adder)
    assert res.res == 0x00000000
    assert res.cf
    assert res.vf
    assert not res.sf
    assert res.zf
    clock.tick()

    # Shift count 32
    res = BarrelShifter.asl_32(0x80000001, 32, sub_adder, cmp_adder)
    assert res.res == 0
    assert res.cf
    assert res.vf
    assert not res.sf
    assert res.zf
    clock.tick()

    # Shift count > 32
    res = BarrelShifter.asl_32(0x12345678, 35, sub_adder, cmp_adder)
    assert res.res == 0
    assert not res.cf
    assert res.vf
    assert not res.sf
    assert res.zf


def test_asr_32(clock: Clock, sub_adder: ShifterAdder):
    # Zero count
    res = BarrelShifter.asr_32(0x80000001, 0, sub_adder)
    assert res.res == 0x80000001
    assert not res.cf
    assert res.sf
    assert not res.zf

    # Positive right shift
    res = BarrelShifter.asr_32(0x00000005, 1, sub_adder)
    assert res.res == 0x00000002
    assert res.cf
    assert not res.sf
    assert not res.zf
    clock.tick()

    # Negative right shift with sign extension (-8 >> 1 = -4)
    res = BarrelShifter.asr_32(0xFFFFFFF8, 1, sub_adder)
    assert res.res == 0xFFFFFFFC
    assert not res.cf
    assert res.sf
    assert not res.zf
    clock.tick()

    # Negative right shift bit 0 shifted out (-7 >> 1 = -4, CF=1)
    res = BarrelShifter.asr_32(0xFFFFFFF9, 1, sub_adder)
    assert res.res == 0xFFFFFFFC
    assert res.cf
    assert res.sf
    assert not res.zf
    clock.tick()

    # Shift count 32 on negative value
    res = BarrelShifter.asr_32(0x80000000, 32, sub_adder)
    assert res.res == 0xFFFFFFFF
    assert res.cf
    assert res.sf
    assert not res.zf
    clock.tick()

    # Shift count 32 on positive value
    res = BarrelShifter.asr_32(0x7FFFFFFF, 32, sub_adder)
    assert res.res == 0
    assert not res.cf
    assert not res.sf
    assert res.zf
    clock.tick()

    # Shift count > 32 on negative value
    res = BarrelShifter.asr_32(0x80000000, 33, sub_adder)
    assert res.res == 0xFFFFFFFF
    assert res.cf
    assert res.sf
    assert not res.zf

    # Shift count > 32 on positive value
    res = BarrelShifter.asr_32(0x7FFFFFFF, 33, sub_adder)
    assert res.res == 0
    assert not res.cf
    assert not res.sf
    assert res.zf


def test_asl_64(clock: Clock, sub_adder: ShifterAdder, cmp_adder: ShifterAdder):
    # Shift without overflow
    val = 0x0000000040000000
    res = BarrelShifter.asl_64(val, 1, sub_adder, cmp_adder)
    assert res.res == 0x0000000080000000
    assert not res.cf
    assert not res.vf
    assert not res.sf
    assert not res.zf
    clock.tick()

    # Shift with overflow
    val = 0x4000000000000000
    res = BarrelShifter.asl_64(val, 1, sub_adder, cmp_adder)
    assert res.res == 0x8000000000000000
    assert not res.cf
    assert res.vf
    assert res.sf
    assert not res.zf
    clock.tick()

    # Negative shift with carry out
    val = 0x8000000000000000
    res = BarrelShifter.asl_64(val, 1, sub_adder, cmp_adder)
    assert res.res == 0
    assert res.cf
    assert res.vf
    assert not res.sf
    assert res.zf


def test_asr_64(clock: Clock, sub_adder: ShifterAdder):
    # Shift across 32-bit boundary with sign extension
    val = 0xFFFFFFFF00000000
    res = BarrelShifter.asr_64(val, 32, sub_adder)
    assert res.res == 0xFFFFFFFFFFFFFFFF
    assert not res.cf
    assert not res.zf
    assert res.sf
    clock.tick()

    # Bit 0 shifted out
    val = 0x8000000000000001
    res = BarrelShifter.asr_64(val, 1, sub_adder)
    assert res.res == 0xC000000000000000
    assert res.cf
    assert not res.zf
    assert res.sf

