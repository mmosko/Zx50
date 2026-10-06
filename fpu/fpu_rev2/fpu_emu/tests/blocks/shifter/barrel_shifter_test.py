"""Unit tests for the BarrelShifter hardware module."""

import pytest
from fpu_emu.blocks.shifter.barrel_shifter import BarrelShifter
from fpu_emu.blocks.shifter.shifter_adder import ShifterAdder


@pytest.fixture
def sub_adder() -> ShifterAdder:
    return ShifterAdder("test_sub_adder")


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


def test_lsl_64(sub_adder: ShifterAdder):
    # Shift 64-bit word across 32-bit boundary
    val = 0x0000000000000001
    res = BarrelShifter.lsl_64(val, 32, sub_adder)
    assert res.res == 0x0000000100000000
    assert not res.cf
    assert not res.zf
    assert not res.sf

    # Bit 63 shifted out
    val_hi_bit = 0x8000000000000000
    res = BarrelShifter.lsl_64(val_hi_bit, 1, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf
    assert not res.sf

    # Sign bit set on 64-bit result
    val_bit_62 = 0x4000000000000000
    res = BarrelShifter.lsl_64(val_bit_62, 1, sub_adder)
    assert res.res == 0x8000000000000000
    assert not res.cf
    assert not res.zf
    assert res.sf

    # Shift count 64
    res = BarrelShifter.lsl_64(0x0000000000000001, 64, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf


def test_lsr_64(sub_adder: ShifterAdder):
    # Shift 64-bit word right across 32-bit boundary
    val = 0x0000000100000000
    res = BarrelShifter.lsr_64(val, 32, sub_adder)
    assert res.res == 0x0000000000000001
    assert not res.cf
    assert not res.zf
    assert not res.sf

    # Bit 0 shifted out
    res = BarrelShifter.lsr_64(0x0000000000000001, 1, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf

    # Shift count 64
    res = BarrelShifter.lsr_64(0x8000000000000000, 64, sub_adder)
    assert res.res == 0
    assert res.cf
    assert res.zf

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
