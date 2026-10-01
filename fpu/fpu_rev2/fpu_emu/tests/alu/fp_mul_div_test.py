"""Unit tests for fp_mul_div.py (IEEE-754 single and double precision multiplication and division)."""

import pytest
from fpu_emu.alu import fp_mul_div
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag
from fpu_emu.tests.testharness import RegTestHarness


@pytest.fixture
def hw():
    return Hardware()


# =============================================================================
# MUL_F32 Tests
# =============================================================================
@pytest.mark.parametrize(
    "a, b, expected_res, expected_sign, expected_zero",
    [
        (2.5, 4.0, 10.0, False, False),
        (-2.5, 4.0, -10.0, True, False),
        (2.5, -4.0, -10.0, True, False),
        (-2.5, -4.0, 10.0, False, False),
        (0.0, 5.0, 0.0, False, True),
        (5.0, 0.0, 0.0, False, True),
        (-0.0, 5.0, 0.0, True, True),
        (1.5, 1.5, 2.25, False, False),
    ],
)
def test_mul_f32_standard(hw, a, b, expected_res, expected_sign, expected_zero):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(a))
    reg.set(Reg.BL, Registers.from_f32(b))

    prev_cycles = hw.clock.cycles
    fp_mul_div.mul_f32(hw, dst=Reg.AL, src=Reg.BL)

    assert hw.clock.cycles - prev_cycles == 16
    res = Registers.to_f32(reg.peek(Reg.AL))
    assert pytest.approx(res, rel=1e-6) == expected_res
    assert hw.reg.get_flag(StatusFlag.SIGN) == expected_sign
    assert hw.reg.get_flag(StatusFlag.ZERO) == expected_zero
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_mul_f32_overflow(hw):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(1e30))
    reg.set(Reg.BL, Registers.from_f32(1e30))

    fp_mul_div.mul_f32(hw, dst=Reg.AL, src=Reg.BL)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


# =============================================================================
# DIV_F32 Tests
# =============================================================================
@pytest.mark.parametrize(
    "a, b, expected_res, expected_sign, expected_zero",
    [
        (10.0, 2.0, 5.0, False, False),
        (-10.0, 2.0, -5.0, True, False),
        (10.0, -2.0, -5.0, True, False),
        (-10.0, -2.0, 5.0, False, False),
        (0.0, 5.0, 0.0, False, True),
        (1.0, 4.0, 0.25, False, False),
    ],
)
def test_div_f32_standard(hw, a, b, expected_res, expected_sign, expected_zero):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(a))
    reg.set(Reg.BL, Registers.from_f32(b))

    prev_cycles = hw.clock.cycles
    fp_mul_div.div_f32(hw, dst=Reg.AL, src=Reg.BL)

    assert hw.clock.cycles - prev_cycles == 16
    res = Registers.to_f32(reg.peek(Reg.AL))
    assert pytest.approx(res, rel=1e-6) == expected_res
    assert hw.reg.get_flag(StatusFlag.SIGN) == expected_sign
    assert hw.reg.get_flag(StatusFlag.ZERO) == expected_zero
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_div_f32_divide_by_zero(hw):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(42.0))
    reg.set(Reg.BL, Registers.from_f32(0.0))

    fp_mul_div.div_f32(hw, dst=Reg.AL, src=Reg.BL)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_div_f32_overflow(hw):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(1e38))
    reg.set(Reg.BL, Registers.from_f32(1e-10))

    fp_mul_div.div_f32(hw, dst=Reg.AL, src=Reg.BL)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


# =============================================================================
# MUL_F64 Tests
# =============================================================================
@pytest.mark.parametrize(
    "a, b, expected_res, expected_sign, expected_zero",
    [
        (123456.789, 2.0, 246913.578, False, False),
        (-123456.789, 2.0, -246913.578, True, False),
        (123456.789, -2.0, -246913.578, True, False),
        (-123456.789, -2.0, 246913.578, False, False),
        (0.0, 999.9, 0.0, False, True),
    ],
)
def test_mul_f64_standard(hw, a, b, expected_res, expected_sign, expected_zero):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(a))
    reg.set(Reg.BX, Registers.from_f64(b))

    prev_cycles = hw.clock.cycles
    fp_mul_div.mul_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.clock.cycles - prev_cycles == 32
    res = Registers.to_f64(reg.peek(Reg.AX))
    assert pytest.approx(res, rel=1e-12) == expected_res
    assert hw.reg.get_flag(StatusFlag.SIGN) == expected_sign
    assert hw.reg.get_flag(StatusFlag.ZERO) == expected_zero
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_mul_f64_overflow(hw):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(1e308))
    reg.set(Reg.BX, Registers.from_f64(2.0))

    fp_mul_div.mul_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


# =============================================================================
# DIV_F64 Tests
# =============================================================================
@pytest.mark.parametrize(
    "a, b, expected_res, expected_sign, expected_zero",
    [
        (100.0, 8.0, 12.5, False, False),
        (-100.0, 8.0, -12.5, True, False),
        (100.0, -8.0, -12.5, True, False),
        (-100.0, -8.0, 12.5, False, False),
        (0.0, 50.0, 0.0, False, True),
    ],
)
def test_div_f64_standard(hw, a, b, expected_res, expected_sign, expected_zero):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(a))
    reg.set(Reg.BX, Registers.from_f64(b))

    prev_cycles = hw.clock.cycles
    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.clock.cycles - prev_cycles == 32
    res = Registers.to_f64(reg.peek(Reg.AX))
    assert pytest.approx(res, rel=1e-12) == expected_res
    assert hw.reg.get_flag(StatusFlag.SIGN) == expected_sign
    assert hw.reg.get_flag(StatusFlag.ZERO) == expected_zero
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_div_f64_divide_by_zero(hw):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(100.0))
    reg.set(Reg.BX, Registers.from_f64(0.0))

    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_div_f64_overflow(hw):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(1e308))
    reg.set(Reg.BX, Registers.from_f64(1e-10))

    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_nan_and_inf_handling(hw):
    reg = RegTestHarness(hw.reg)
    # mul_f32 inf
    reg.set(Reg.AL, Registers.from_f32(float("inf")))
    reg.set(Reg.BL, Registers.from_f32(2.0))
    fp_mul_div.mul_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # div_f32 inf
    reg.set(Reg.AL, Registers.from_f32(float("inf")))
    reg.set(Reg.BL, Registers.from_f32(2.0))
    fp_mul_div.div_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # mul_f64 inf
    reg.set(Reg.AX, Registers.from_f64(float("inf")))
    reg.set(Reg.BX, Registers.from_f64(2.0))
    fp_mul_div.mul_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # div_f64 inf
    reg.set(Reg.AX, Registers.from_f64(float("inf")))
    reg.set(Reg.BX, Registers.from_f64(2.0))
    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_underflow_handling(hw):
    reg = RegTestHarness(hw.reg)
    # mul_f32 underflow
    reg.set(Reg.AL, Registers.from_f32(1e-30))
    reg.set(Reg.BL, Registers.from_f32(1e-30))
    fp_mul_div.mul_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert hw.reg.get_flag(StatusFlag.ZERO)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)

    # div_f32 underflow
    reg.set(Reg.AL, Registers.from_f32(1e-30))
    reg.set(Reg.BL, Registers.from_f32(1e30))
    fp_mul_div.div_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert hw.reg.get_flag(StatusFlag.ZERO)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)

    # mul_f64 underflow
    reg.set(Reg.AX, Registers.from_f64(1e-200))
    reg.set(Reg.BX, Registers.from_f64(1e-200))
    fp_mul_div.mul_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert hw.reg.get_flag(StatusFlag.ZERO)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)

    # div_f64 underflow
    reg.set(Reg.AX, Registers.from_f64(1e-200))
    reg.set(Reg.BX, Registers.from_f64(1e200))
    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert hw.reg.get_flag(StatusFlag.ZERO)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)


# =============================================================================
# ADD / SUB F32 & F64 Tests
# =============================================================================
def test_add_sub_f32(hw):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(1.5))
    reg.set(Reg.BL, Registers.from_f32(2.25))
    fp_mul_div.add_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert pytest.approx(Registers.to_f32(reg.peek(Reg.AL)), rel=1e-6) == 3.75

    reg.set(Reg.AL, Registers.from_f32(3.75))
    reg.set(Reg.BL, Registers.from_f32(1.5))
    fp_mul_div.sub_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert pytest.approx(Registers.to_f32(reg.peek(Reg.AL)), rel=1e-6) == 2.25

    # Equal cancellation
    reg.set(Reg.AL, Registers.from_f32(2.5))
    reg.set(Reg.BL, Registers.from_f32(2.5))
    fp_mul_div.sub_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert hw.reg.get_flag(StatusFlag.ZERO)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 0.0

    # Add zero
    reg.set(Reg.AL, Registers.from_f32(0.0))
    reg.set(Reg.BL, Registers.from_f32(4.5))
    fp_mul_div.add_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert pytest.approx(Registers.to_f32(reg.peek(Reg.AL)), rel=1e-6) == 4.5

    reg.set(Reg.AL, Registers.from_f32(4.5))
    reg.set(Reg.BL, Registers.from_f32(0.0))
    fp_mul_div.add_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert pytest.approx(Registers.to_f32(reg.peek(Reg.AL)), rel=1e-6) == 4.5


def test_add_sub_f64(hw):
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(10.125))
    reg.set(Reg.BX, Registers.from_f64(20.375))
    fp_mul_div.add_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert pytest.approx(Registers.to_f64(reg.peek(Reg.AX)), rel=1e-12) == 30.5

    reg.set(Reg.AX, Registers.from_f64(30.5))
    reg.set(Reg.BX, Registers.from_f64(10.125))
    fp_mul_div.sub_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert pytest.approx(Registers.to_f64(reg.peek(Reg.AX)), rel=1e-12) == 20.375

    # Equal cancellation
    reg.set(Reg.AX, Registers.from_f64(7.5))
    reg.set(Reg.BX, Registers.from_f64(7.5))
    fp_mul_div.sub_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert hw.reg.get_flag(StatusFlag.ZERO)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 0.0

    # Add zero
    reg.set(Reg.AX, Registers.from_f64(0.0))
    reg.set(Reg.BX, Registers.from_f64(8.25))
    fp_mul_div.add_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert pytest.approx(Registers.to_f64(reg.peek(Reg.AX)), rel=1e-12) == 8.25

    reg.set(Reg.AX, Registers.from_f64(8.25))
    reg.set(Reg.BX, Registers.from_f64(0.0))
    fp_mul_div.add_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert pytest.approx(Registers.to_f64(reg.peek(Reg.AX)), rel=1e-12) == 8.25
