"""Unit tests for floating-point power (fp_pow.py / x^y)."""

import math
import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.alu.fp_pow import pow_f32, pow_f64
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag
from fpu_emu.tests.testharness import RegTestHarness


@pytest.mark.parametrize(
    "base,exp,expected,tol",
    [
        (2.0, 3.0, 8.0, 1e-5),
        (3.0, 2.0, 9.0, 1e-5),
        (4.0, 0.5, 2.0, 1e-5),
        (2.0, 0.5, math.sqrt(2.0), 1e-5),
        (10.0, -2.0, 0.01, 1e-5),
        (5.0, 0.0, 1.0, 1e-6),
        (1.0, 100.0, 1.0, 1e-6),
        (-2.0, 3.0, -8.0, 1e-5),
        (-2.0, 2.0, 4.0, 1e-5),
    ],
)
def test_pow_f32_normal_values(base, exp, expected, tol):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(base))
    reg.set(Reg.BL, Registers.from_f32(exp))
    pow_f32(hw, src=Reg.BL)

    res = Registers.to_f32(reg.peek(Reg.AL))
    assert math.isclose(res, expected, rel_tol=tol, abs_tol=tol)
    assert not hw.reg.get_flag(StatusFlag.ERR)


@pytest.mark.parametrize(
    "base,exp,expected,tol",
    [
        (2.0, 10.0, 1024.0, 1e-10),
        (3.0, 4.0, 81.0, 1e-10),
        (9.0, 0.5, 3.0, 1e-10),
        (10.0, -5.0, 1e-5, 1e-10),
        (7.0, 0.0, 1.0, 1e-12),
        (1.0, 500.0, 1.0, 1e-12),
        (-3.0, 3.0, -27.0, 1e-10),
        (-3.0, 4.0, 81.0, 1e-10),
    ],
)
def test_pow_f64_normal_values(base, exp, expected, tol):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(base))
    reg.set(Reg.BX, Registers.from_f64(exp))
    pow_f64(hw, src=Reg.BX)

    res = Registers.to_f64(reg.peek(Reg.AX))
    assert math.isclose(res, expected, rel_tol=tol, abs_tol=tol)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_pow_zero_base():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # 0^3 = 0
    reg.set(Reg.AL, Registers.from_f32(0.0))
    reg.set(Reg.BL, Registers.from_f32(3.0))
    pow_f32(hw, src=Reg.BL)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 0.0
    assert hw.reg.get_flag(StatusFlag.ZERO)

    # 0^(-2) -> DivByZero (ERR=True, Inf)
    reg.set(Reg.AL, Registers.from_f32(0.0))
    reg.set(Reg.BL, Registers.from_f32(-2.0))
    pow_f32(hw, src=Reg.BL)
    assert math.isinf(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_pow_negative_base_fractional_exponent():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # (-2)^0.5 -> NaN, ERR=True
    reg.set(Reg.AL, Registers.from_f32(-2.0))
    reg.set(Reg.BL, Registers.from_f32(0.5))
    pow_f32(hw, src=Reg.BL)
    assert math.isnan(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.ERR)

    # 64-bit (-4)^0.5 -> NaN, ERR=True
    reg.set(Reg.AX, Registers.from_f64(-4.0))
    reg.set(Reg.BX, Registers.from_f64(0.5))
    pow_f64(hw, src=Reg.BX)
    assert math.isnan(Registers.to_f64(reg.peek(Reg.AX)))
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_pow_overflow_underflow():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # Overflow: 10^40 in F32
    reg.set(Reg.AL, Registers.from_f32(10.0))
    reg.set(Reg.BL, Registers.from_f32(40.0))
    pow_f32(hw, src=Reg.BL)
    assert math.isinf(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # Overflow on huge exponent triggering Python OverflowError: 10^400
    reg.set(Reg.AL, Registers.from_f32(10.0))
    reg.set(Reg.BL, Registers.from_f32(400.0))
    pow_f32(hw, src=Reg.BL)
    assert math.isinf(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)

    # Negative base overflow: (-10)^40
    reg.set(Reg.AL, Registers.from_f32(-10.0))
    reg.set(Reg.BL, Registers.from_f32(40.0))
    pow_f32(hw, src=Reg.BL)
    assert math.isinf(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)

    # Negative base huge exponent overflow: (-10)^401 (odd)
    reg.set(Reg.AL, Registers.from_f32(-10.0))
    reg.set(Reg.BL, Registers.from_f32(401.0))
    pow_f32(hw, src=Reg.BL)
    assert math.isinf(Registers.to_f32(reg.peek(Reg.AL)))
    assert Registers.to_f32(reg.peek(Reg.AL)) < 0
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)

    # Underflow: 10^(-50) in F32
    reg.set(Reg.AL, Registers.from_f32(10.0))
    reg.set(Reg.BL, Registers.from_f32(-50.0))
    pow_f32(hw, src=Reg.BL)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 0.0
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW)
    assert hw.reg.get_flag(StatusFlag.ZERO)

    # Negative base underflow: (-10)^(-50)
    reg.set(Reg.AL, Registers.from_f32(-10.0))
    reg.set(Reg.BL, Registers.from_f32(-50.0))
    pow_f32(hw, src=Reg.BL)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 0.0
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW)


def test_pow_f64_edge_cases():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # 0^3 = 0 in F64
    reg.set(Reg.AX, Registers.from_f64(0.0))
    reg.set(Reg.BX, Registers.from_f64(3.0))
    pow_f64(hw, src=Reg.BX)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 0.0
    assert hw.reg.get_flag(StatusFlag.ZERO)

    # 0^(-2) -> DivByZero in F64
    reg.set(Reg.AX, Registers.from_f64(0.0))
    reg.set(Reg.BX, Registers.from_f64(-2.0))
    pow_f64(hw, src=Reg.BX)
    assert math.isinf(Registers.to_f64(reg.peek(Reg.AX)))
    assert hw.reg.get_flag(StatusFlag.ERR)

    # Overflow: 10^400 in F64
    reg.set(Reg.AX, Registers.from_f64(10.0))
    reg.set(Reg.BX, Registers.from_f64(400.0))
    pow_f64(hw, src=Reg.BX)
    assert math.isinf(Registers.to_f64(reg.peek(Reg.AX)))
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # Negative base overflow: (-10)^400 in F64
    reg.set(Reg.AX, Registers.from_f64(-10.0))
    reg.set(Reg.BX, Registers.from_f64(400.0))
    pow_f64(hw, src=Reg.BX)
    assert math.isinf(Registers.to_f64(reg.peek(Reg.AX)))
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)

    # Negative base odd exponent overflow: (-10)^401 in F64
    reg.set(Reg.AX, Registers.from_f64(-10.0))
    reg.set(Reg.BX, Registers.from_f64(401.0))
    pow_f64(hw, src=Reg.BX)
    assert math.isinf(Registers.to_f64(reg.peek(Reg.AX)))
    assert Registers.to_f64(reg.peek(Reg.AX)) < 0
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)

    # Underflow: 10^(-400) in F64
    reg.set(Reg.AX, Registers.from_f64(10.0))
    reg.set(Reg.BX, Registers.from_f64(-400.0))
    pow_f64(hw, src=Reg.BX)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 0.0
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW)
    assert hw.reg.get_flag(StatusFlag.ZERO)

    # Negative base underflow: (-10)^(-400) in F64
    reg.set(Reg.AX, Registers.from_f64(-10.0))
    reg.set(Reg.BX, Registers.from_f64(-400.0))
    pow_f64(hw, src=Reg.BX)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 0.0
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW)


def test_alu_pow_delegation():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)

    reg.set(Reg.AL, Registers.from_f32(2.0))
    reg.set(Reg.BL, Registers.from_f32(4.0))
    alu.pow_f32(src=Reg.BL)
    assert math.isclose(Registers.to_f32(reg.peek(Reg.AL)), 16.0, rel_tol=1e-5)

    reg.set(Reg.AX, Registers.from_f64(2.0))
    reg.set(Reg.BX, Registers.from_f64(4.0))
    alu.pow_f64(src=Reg.BX)
    assert math.isclose(Registers.to_f64(reg.peek(Reg.AX)), 16.0, rel_tol=1e-10)
