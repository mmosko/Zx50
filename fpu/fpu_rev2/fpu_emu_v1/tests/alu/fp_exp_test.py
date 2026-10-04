"""Unit tests for floating-point exponential (fp_exp.py / e^x)."""

import math
import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.alu.fp_exp import exp_f32, exp_f64, exp2_frac_core
from fpu_emu.hardware import Hardware
from fpu_emu.hardware.registers import Reg, Registers, StatusFlag
from fpu_emu.tests.testharness import RegTestHarness


@pytest.mark.parametrize(
    "x,expected,tol",
    [
        (0.0, 1.0, 1e-6),
        (1.0, math.e, 1e-5),
        (-1.0, 1.0 / math.e, 1e-5),
        (2.0, math.exp(2.0), 1e-4),
        (-2.0, math.exp(-2.0), 1e-5),
        (0.5, math.exp(0.5), 1e-5),
        (-0.5, math.exp(-0.5), 1e-5),
        (10.0, math.exp(10.0), 1.0),
    ],
)
def test_exp_f32_normal_values(x, expected, tol):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(x))
    exp_f32(hw)

    res = Registers.to_f32(reg.peek(Reg.AL))
    assert math.isclose(res, expected, rel_tol=tol, abs_tol=tol)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.UNDERFLOW)
    assert hw.clock.cycles >= 2


@pytest.mark.parametrize(
    "x,expected,tol",
    [
        (0.0, 1.0, 1e-12),
        (1.0, math.e, 1e-10),
        (-1.0, 1.0 / math.e, 1e-10),
        (2.0, math.exp(2.0), 1e-10),
        (-2.0, math.exp(-2.0), 1e-10),
        (0.5, math.exp(0.5), 1e-10),
        (10.0, math.exp(10.0), 1e-8),
        (50.0, math.exp(50.0), 1e-6),
    ],
)
def test_exp_f64_normal_values(x, expected, tol):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(x))
    exp_f64(hw)

    res = Registers.to_f64(reg.peek(Reg.AX))
    assert math.isclose(res, expected, rel_tol=tol, abs_tol=tol)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.UNDERFLOW)
    assert hw.clock.cycles >= 3


def test_exp_f32_overflow():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(100.0))  # e^100 overflows float32
    exp_f32(hw)

    res = Registers.to_f32(reg.peek(Reg.AL))
    assert math.isinf(res) and res > 0
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_exp_f64_overflow():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(1000.0))  # e^1000 overflows float64
    exp_f64(hw)

    res = Registers.to_f64(reg.peek(Reg.AX))
    assert math.isinf(res) and res > 0
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_exp_f32_underflow():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(-150.0))  # e^(-150) underflows float32
    exp_f32(hw)

    res = Registers.to_f32(reg.peek(Reg.AL))
    assert res == 0.0
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW)
    assert hw.reg.get_flag(StatusFlag.ZERO)


def test_exp_f64_underflow():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(-1100.0))  # e^(-1100) underflows float64
    exp_f64(hw)

    res = Registers.to_f64(reg.peek(Reg.AX))
    assert res == 0.0
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW)
    assert hw.reg.get_flag(StatusFlag.ZERO)


def test_exp_special_values_f32():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # NaN
    reg.set(Reg.AL, Registers.from_f32(float("nan")))
    exp_f32(hw)
    assert math.isnan(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.ERR)

    # +Inf
    reg.set(Reg.AL, Registers.from_f32(float("inf")))
    exp_f32(hw)
    assert math.isinf(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # -Inf
    reg.set(Reg.AL, Registers.from_f32(float("-inf")))
    exp_f32(hw)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 0.0
    assert hw.reg.get_flag(StatusFlag.ZERO)


def test_exp_special_values_f64():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # NaN
    reg.set(Reg.AX, Registers.from_f64(float("nan")))
    exp_f64(hw)
    assert math.isnan(Registers.to_f64(reg.peek(Reg.AX)))
    assert hw.reg.get_flag(StatusFlag.ERR)

    # +Inf
    reg.set(Reg.AX, Registers.from_f64(float("inf")))
    exp_f64(hw)
    assert math.isinf(Registers.to_f64(reg.peek(Reg.AX)))
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # -Inf
    reg.set(Reg.AX, Registers.from_f64(float("-inf")))
    exp_f64(hw)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 0.0
    assert hw.reg.get_flag(StatusFlag.ZERO)


def test_alu_exp_delegation():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)

    reg.set(Reg.AL, Registers.from_f32(1.0))
    alu.exp_f32()
    assert math.isclose(Registers.to_f32(reg.peek(Reg.AL)), math.e, rel_tol=1e-5)

    reg.set(Reg.AX, Registers.from_f64(1.0))
    alu.exp_f64()
    assert math.isclose(Registers.to_f64(reg.peek(Reg.AX)), math.e, rel_tol=1e-10)


def test_exp2_frac_core():
    res32 = exp2_frac_core(0.5, is_64=False)
    assert math.isclose(res32, math.sqrt(2.0), rel_tol=1e-5)

    res64 = exp2_frac_core(0.5, is_64=True)
    assert math.isclose(res64, math.sqrt(2.0), rel_tol=1e-10)
