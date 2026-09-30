"""Unit tests for floating-point natural logarithm (fp_ln.py / ln(x))."""

import math
import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.alu.fp_ln import ln_f32, ln_f64, ln_mantissa_core
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag
from fpu_emu.tests.testharness import RegTestHarness


@pytest.mark.parametrize(
    "x,expected,tol",
    [
        (1.0, 0.0, 1e-6),
        (math.e, 1.0, 1e-5),
        (2.0, math.log(2.0), 1e-5),
        (0.5, math.log(0.5), 1e-5),
        (10.0, math.log(10.0), 1e-5),
        (100.0, math.log(100.0), 1e-5),
        (0.1, math.log(0.1), 1e-5),
        (1.5, math.log(1.5), 1e-5),
    ],
)
def test_ln_f32_normal_values(x, expected, tol):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(x))
    ln_f32(hw)

    res = Registers.to_f32(reg.peek(Reg.AL))
    assert math.isclose(res, expected, rel_tol=tol, abs_tol=tol)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert hw.clock.cycles >= 2


@pytest.mark.parametrize(
    "x,expected,tol",
    [
        (1.0, 0.0, 1e-12),
        (math.e, 1.0, 1e-10),
        (2.0, math.log(2.0), 1e-10),
        (0.5, math.log(0.5), 1e-10),
        (10.0, math.log(10.0), 1e-10),
        (100.0, math.log(100.0), 1e-10),
        (0.001, math.log(0.001), 1e-10),
        (12345.6789, math.log(12345.6789), 1e-10),
    ],
)
def test_ln_f64_normal_values(x, expected, tol):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(x))
    ln_f64(hw)

    res = Registers.to_f64(reg.peek(Reg.AX))
    assert math.isclose(res, expected, rel_tol=tol, abs_tol=tol)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert hw.clock.cycles >= 3


def test_ln_f32_domain_errors():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # ln(0) -> -inf, ERR=True
    reg.set(Reg.AL, Registers.from_f32(0.0))
    ln_f32(hw)
    res = Registers.to_f32(reg.peek(Reg.AL))
    assert math.isinf(res) and res < 0
    assert hw.reg.get_flag(StatusFlag.ERR)

    # ln(-1.0) -> NaN, ERR=True
    reg.set(Reg.AL, Registers.from_f32(-1.0))
    ln_f32(hw)
    res = Registers.to_f32(reg.peek(Reg.AL))
    assert math.isnan(res)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_ln_f64_domain_errors():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # ln(0) -> -inf, ERR=True
    reg.set(Reg.AX, Registers.from_f64(0.0))
    ln_f64(hw)
    res = Registers.to_f64(reg.peek(Reg.AX))
    assert math.isinf(res) and res < 0
    assert hw.reg.get_flag(StatusFlag.ERR)

    # ln(-5.0) -> NaN, ERR=True
    reg.set(Reg.AX, Registers.from_f64(-5.0))
    ln_f64(hw)
    res = Registers.to_f64(reg.peek(Reg.AX))
    assert math.isnan(res)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_alu_ln_delegation():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)

    reg.set(Reg.AL, Registers.from_f32(math.e))
    alu.ln_f32()
    assert math.isclose(Registers.to_f32(reg.peek(Reg.AL)), 1.0, rel_tol=1e-5)

    reg.set(Reg.AX, Registers.from_f64(math.e))
    alu.ln_f64()
    assert math.isclose(Registers.to_f64(reg.peek(Reg.AX)), 1.0, rel_tol=1e-10)


def test_ln_mantissa_core():
    res32 = ln_mantissa_core(1.5, is_64=False)
    assert math.isclose(res32, math.log(1.5), rel_tol=1e-5)

    res64 = ln_mantissa_core(1.5, is_64=True)
    assert math.isclose(res64, math.log(1.5), rel_tol=1e-10)

