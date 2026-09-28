"""Unit tests for fp_mul_div.py (IEEE-754 single and double precision multiplication and division)."""

import math
import pytest
from fpu_emu.alu import fp_mul_div
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag


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
    hw.reg.set(Reg.AL, Registers.from_f32(a))
    hw.reg.set(Reg.BL, Registers.from_f32(b))

    prev_cycles = hw.clock.cycles
    fp_mul_div.mul_f32(hw, dst=Reg.AL, src=Reg.BL)

    assert hw.clock.cycles - prev_cycles == 16
    res = Registers.to_f32(hw.reg.get(Reg.AL))
    assert pytest.approx(res, rel=1e-6) == expected_res
    assert hw.reg.get_flag(StatusFlag.SIGN) == expected_sign
    assert hw.reg.get_flag(StatusFlag.ZERO) == expected_zero
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_mul_f32_overflow(hw):
    # Large numbers that overflow float32
    hw.reg.set(Reg.AL, Registers.from_f32(1e30))
    hw.reg.set(Reg.BL, Registers.from_f32(1e30))

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
    hw.reg.set(Reg.AL, Registers.from_f32(a))
    hw.reg.set(Reg.BL, Registers.from_f32(b))

    prev_cycles = hw.clock.cycles
    fp_mul_div.div_f32(hw, dst=Reg.AL, src=Reg.BL)

    assert hw.clock.cycles - prev_cycles == 16
    res = Registers.to_f32(hw.reg.get(Reg.AL))
    assert pytest.approx(res, rel=1e-6) == expected_res
    assert hw.reg.get_flag(StatusFlag.SIGN) == expected_sign
    assert hw.reg.get_flag(StatusFlag.ZERO) == expected_zero
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_div_f32_divide_by_zero(hw):
    hw.reg.set(Reg.AL, Registers.from_f32(42.0))
    hw.reg.set(Reg.BL, Registers.from_f32(0.0))

    fp_mul_div.div_f32(hw, dst=Reg.AL, src=Reg.BL)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_div_f32_overflow(hw):
    hw.reg.set(Reg.AL, Registers.from_f32(1e38))
    hw.reg.set(Reg.BL, Registers.from_f32(1e-10))

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
    hw.reg.set(Reg.AX, Registers.from_f64(a))
    hw.reg.set(Reg.BX, Registers.from_f64(b))

    prev_cycles = hw.clock.cycles
    fp_mul_div.mul_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.clock.cycles - prev_cycles == 32
    res = Registers.to_f64(hw.reg.get(Reg.AX))
    assert pytest.approx(res, rel=1e-12) == expected_res
    assert hw.reg.get_flag(StatusFlag.SIGN) == expected_sign
    assert hw.reg.get_flag(StatusFlag.ZERO) == expected_zero
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_mul_f64_overflow(hw):
    hw.reg.set(Reg.AX, Registers.from_f64(1e308))
    hw.reg.set(Reg.BX, Registers.from_f64(2.0))

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
    hw.reg.set(Reg.AX, Registers.from_f64(a))
    hw.reg.set(Reg.BX, Registers.from_f64(b))

    prev_cycles = hw.clock.cycles
    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.clock.cycles - prev_cycles == 32
    res = Registers.to_f64(hw.reg.get(Reg.AX))
    assert pytest.approx(res, rel=1e-12) == expected_res
    assert hw.reg.get_flag(StatusFlag.SIGN) == expected_sign
    assert hw.reg.get_flag(StatusFlag.ZERO) == expected_zero
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_div_f64_divide_by_zero(hw):
    hw.reg.set(Reg.AX, Registers.from_f64(100.0))
    hw.reg.set(Reg.BX, Registers.from_f64(0.0))

    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_div_f64_overflow(hw):
    hw.reg.set(Reg.AX, Registers.from_f64(1e308))
    hw.reg.set(Reg.BX, Registers.from_f64(1e-10))

    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)

    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_nan_and_inf_handling(hw):
    # mul_f32 inf
    hw.reg.set(Reg.AL, Registers.from_f32(float("inf")))
    hw.reg.set(Reg.BL, Registers.from_f32(2.0))
    fp_mul_div.mul_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # div_f32 inf
    hw.reg.set(Reg.AL, Registers.from_f32(float("inf")))
    hw.reg.set(Reg.BL, Registers.from_f32(2.0))
    fp_mul_div.div_f32(hw, dst=Reg.AL, src=Reg.BL)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # mul_f64 inf
    hw.reg.set(Reg.AX, Registers.from_f64(float("inf")))
    hw.reg.set(Reg.BX, Registers.from_f64(2.0))
    fp_mul_div.mul_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # div_f64 inf
    hw.reg.set(Reg.AX, Registers.from_f64(float("inf")))
    hw.reg.set(Reg.BX, Registers.from_f64(2.0))
    fp_mul_div.div_f64(hw, dst=Reg.AX, src=Reg.BX)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)
