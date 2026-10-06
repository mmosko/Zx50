"""Unit tests for the ShifterAdder hardware module."""

import pytest
from fpu_emu.blocks.shifter.shifter_adder import ShifterAdder


def test_shifter_adder_init():
    adder = ShifterAdder()
    assert adder.val == 0
    assert adder.read_int() == 0
    assert adder.read() == b"\x00"


def test_shifter_adder_add():
    adder = ShifterAdder()
    assert adder.add(0, 0) == 0
    assert adder.add(32, 12) == 44
    assert adder.add(32, 31) == 63
    assert adder.add(64, 32) == 96
    assert adder.add(127, 1) == 0  # Wraps at 7 bits (128)
    assert adder.val == 0
    assert adder.read_int() == 0


def test_shifter_adder_sub():
    adder = ShifterAdder()
    # 5-bit LZC subtraction cases (31 - bit_pos)
    assert adder.sub(31, 31) == 0
    assert adder.sub(31, 19) == 12
    assert adder.sub(31, 0) == 31
    # 32-bit and 64-bit barrel shifter carry bit position calculations
    assert adder.sub(32, 1) == 31
    assert adder.sub(32, 32) == 0
    assert adder.sub(64, 1) == 63
    assert adder.sub(64, 64) == 0
    assert adder.sub(1, 1) == 0
    assert adder.sub(32, 1) == 31
    # 7-bit wrap
    assert adder.sub(0, 1) == 127  # 7-bit two's complement wrap
    assert adder.val == 127
    assert adder.read_int() == 127


def test_shifter_adder_out_of_range():
    adder = ShifterAdder()
    with pytest.raises(AssertionError):
        adder.add(128, 0)
    with pytest.raises(AssertionError):
        adder.add(0, 128)
    with pytest.raises(AssertionError):
        adder.sub(128, 0)
    with pytest.raises(AssertionError):
        adder.sub(0, 128)
