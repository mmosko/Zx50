"""Unit tests for floating-point trigonometric module (fp_trig.py / SIN, COS, TAN)."""

import math
import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.alu.fp_trig import cos_f32, cos_f64, sin_f32, sin_f64, tan_f32, tan_f64
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag
from fpu_emu.tests.testharness import RegTestHarness


# -----------------------------------------------------------------------------
# F32 Normal & Special Angle Tests
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "angle_rad",
    [
        0.0,
        math.pi / 6,
        math.pi / 4,
        math.pi / 3,
        math.pi / 2,
        2 * math.pi / 3,
        3 * math.pi / 4,
        math.pi,
        3 * math.pi / 2,
        2 * math.pi,
        -math.pi / 6,
        -math.pi / 4,
        -math.pi / 3,
        -math.pi / 2,
        -math.pi,
        5.0,
        -10.0,
    ],
)
def test_sin_f32_values(angle_rad: float):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(angle_rad))

    sin_f32(hw, Reg.AL)

    res = Registers.to_f32(reg.peek(Reg.AL))
    expected = math.sin(angle_rad)
    assert math.isclose(res, expected, rel_tol=1e-4, abs_tol=1e-6)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)


@pytest.mark.parametrize(
    "angle_rad",
    [
        0.0,
        math.pi / 6,
        math.pi / 4,
        math.pi / 3,
        math.pi / 2,
        2 * math.pi / 3,
        3 * math.pi / 4,
        math.pi,
        3 * math.pi / 2,
        2 * math.pi,
        -math.pi / 6,
        -math.pi / 4,
        -math.pi / 3,
        -math.pi / 2,
        -math.pi,
        5.0,
        -10.0,
    ],
)
def test_cos_f32_values(angle_rad: float):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(angle_rad))

    cos_f32(hw, Reg.AL)

    res = Registers.to_f32(reg.peek(Reg.AL))
    expected = math.cos(angle_rad)
    assert math.isclose(res, expected, rel_tol=1e-4, abs_tol=1e-6)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)


@pytest.mark.parametrize(
    "angle_rad",
    [
        0.0,
        math.pi / 6,
        math.pi / 4,
        math.pi / 3,
        2 * math.pi / 3,
        3 * math.pi / 4,
        math.pi,
        -math.pi / 6,
        -math.pi / 4,
        -math.pi / 3,
        -math.pi,
        5.0,
    ],
)
def test_tan_f32_values(angle_rad: float):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(angle_rad))

    tan_f32(hw, Reg.AL)

    res = Registers.to_f32(reg.peek(Reg.AL))
    expected = math.tan(angle_rad)
    assert math.isclose(res, expected, rel_tol=1e-3, abs_tol=1e-5)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_tan_f32_near_pi_over_2():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_f32(math.pi / 2))

    tan_f32(hw, Reg.AL)

    res = Registers.to_f32(reg.peek(Reg.AL))
    # In IEEE-754, pi/2 is not exactly representable; tan near pi/2 evaluates to a large magnitude
    assert abs(res) > 1e6
    assert not hw.reg.get_flag(StatusFlag.ERR)


# -----------------------------------------------------------------------------
# F64 Normal & Special Angle Tests
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "angle_rad",
    [
        0.0,
        math.pi / 6,
        math.pi / 4,
        math.pi / 3,
        math.pi / 2,
        2 * math.pi / 3,
        3 * math.pi / 4,
        math.pi,
        3 * math.pi / 2,
        2 * math.pi,
        -math.pi / 6,
        -math.pi / 4,
        -math.pi / 3,
        -math.pi / 2,
        -math.pi,
        5.0,
        -10.0,
    ],
)
def test_sin_f64_values(angle_rad: float):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(angle_rad))

    sin_f64(hw, Reg.AX)

    res = Registers.to_f64(reg.peek(Reg.AX))
    expected = math.sin(angle_rad)
    assert math.isclose(res, expected, rel_tol=1e-12, abs_tol=1e-15)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)


@pytest.mark.parametrize(
    "angle_rad",
    [
        0.0,
        math.pi / 6,
        math.pi / 4,
        math.pi / 3,
        math.pi / 2,
        2 * math.pi / 3,
        3 * math.pi / 4,
        math.pi,
        3 * math.pi / 2,
        2 * math.pi,
        -math.pi / 6,
        -math.pi / 4,
        -math.pi / 3,
        -math.pi / 2,
        -math.pi,
        5.0,
        -10.0,
    ],
)
def test_cos_f64_values(angle_rad: float):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(angle_rad))

    cos_f64(hw, Reg.AX)

    res = Registers.to_f64(reg.peek(Reg.AX))
    expected = math.cos(angle_rad)
    assert math.isclose(res, expected, rel_tol=1e-12, abs_tol=1e-15)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)


@pytest.mark.parametrize(
    "angle_rad",
    [
        0.0,
        math.pi / 6,
        math.pi / 4,
        math.pi / 3,
        2 * math.pi / 3,
        3 * math.pi / 4,
        math.pi,
        -math.pi / 6,
        -math.pi / 4,
        -math.pi / 3,
        -math.pi,
        5.0,
    ],
)
def test_tan_f64_values(angle_rad: float):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(angle_rad))

    tan_f64(hw, Reg.AX)

    res = Registers.to_f64(reg.peek(Reg.AX))
    expected = math.tan(angle_rad)
    assert math.isclose(res, expected, rel_tol=1e-10, abs_tol=1e-14)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_tan_f64_near_pi_over_2():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_f64(math.pi / 2))

    tan_f64(hw, Reg.AX)

    res = Registers.to_f64(reg.peek(Reg.AX))
    # In IEEE-754, pi/2 is not exactly representable; tan near pi/2 evaluates to a large magnitude
    assert abs(res) > 1e15
    assert not hw.reg.get_flag(StatusFlag.ERR)


# -----------------------------------------------------------------------------
# Edge cases: Tiny angles, Zero, NaN, Infinity
# -----------------------------------------------------------------------------
def test_trig_special_values_f32():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # +0.0
    reg.set(Reg.AL, Registers.from_f32(0.0))
    sin_f32(hw, Reg.AL)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 0.0
    assert hw.reg.get_flag(StatusFlag.ZERO)

    reg.set(Reg.AL, Registers.from_f32(0.0))
    cos_f32(hw, Reg.AL)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 1.0
    assert not hw.reg.get_flag(StatusFlag.ZERO)

    # Tiny angle (< 2^-12)
    tiny = 1e-5
    reg.set(Reg.AL, Registers.from_f32(tiny))
    sin_f32(hw, Reg.AL)
    assert math.isclose(Registers.to_f32(reg.peek(Reg.AL)), tiny, rel_tol=1e-5)

    reg.set(Reg.AL, Registers.from_f32(tiny))
    cos_f32(hw, Reg.AL)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 1.0

    # NaN
    reg.set(Reg.AL, Registers.from_f32(float("nan")))
    sin_f32(hw, Reg.AL)
    assert math.isnan(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.ERR)

    # Infinity
    reg.set(Reg.AL, Registers.from_f32(float("inf")))
    cos_f32(hw, Reg.AL)
    assert math.isnan(Registers.to_f32(reg.peek(Reg.AL)))
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_trig_special_values_f64():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # +0.0
    reg.set(Reg.AX, Registers.from_f64(0.0))
    sin_f64(hw, Reg.AX)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 0.0
    assert hw.reg.get_flag(StatusFlag.ZERO)

    reg.set(Reg.AX, Registers.from_f64(0.0))
    cos_f64(hw, Reg.AX)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 1.0
    assert not hw.reg.get_flag(StatusFlag.ZERO)

    # Tiny angle (< 2^-27)
    tiny = 1e-10
    reg.set(Reg.AX, Registers.from_f64(tiny))
    sin_f64(hw, Reg.AX)
    assert math.isclose(Registers.to_f64(reg.peek(Reg.AX)), tiny, rel_tol=1e-10)

    reg.set(Reg.AX, Registers.from_f64(tiny))
    cos_f64(hw, Reg.AX)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 1.0

    # NaN
    reg.set(Reg.AX, Registers.from_f64(float("nan")))
    sin_f64(hw, Reg.AX)
    assert math.isnan(Registers.to_f64(reg.peek(Reg.AX)))
    assert hw.reg.get_flag(StatusFlag.ERR)

    # Infinity
    reg.set(Reg.AX, Registers.from_f64(float("inf")))
    cos_f64(hw, Reg.AX)
    assert math.isnan(Registers.to_f64(reg.peek(Reg.AX)))
    assert hw.reg.get_flag(StatusFlag.ERR)


# -----------------------------------------------------------------------------
# Register Validation & Arbitrary Register Target Tests
# -----------------------------------------------------------------------------
def test_trig_register_validation():
    hw = Hardware()
    with pytest.raises(ValueError, match="Expected 32-bit register"):
        sin_f32(hw, Reg.AX)

    with pytest.raises(ValueError, match="Expected 64-bit register"):
        sin_f64(hw, Reg.AL)


def test_trig_non_default_registers():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # Run sin_f32 on BL instead of AL
    reg.set(Reg.BL, Registers.from_f32(math.pi / 6))
    sin_f32(hw, Reg.BL)
    res32 = Registers.to_f32(reg.peek(Reg.BL))
    assert math.isclose(res32, 0.5, rel_tol=1e-4)

    # Run cos_f64 on BX instead of AX
    reg.set(Reg.BX, Registers.from_f64(math.pi / 3))
    cos_f64(hw, Reg.BX)
    res64 = Registers.to_f64(reg.peek(Reg.BX))
    assert math.isclose(res64, 0.5, rel_tol=1e-10)


# -----------------------------------------------------------------------------
# Alu Class Coordinator Tests
# -----------------------------------------------------------------------------
def test_alu_coordinator_trig():
    hw = Hardware()
    alu = Alu(hw)
    reg = RegTestHarness(hw.reg)

    reg.set(Reg.AL, Registers.from_f32(math.pi / 4))
    alu.sin_f32(Reg.AL)
    assert math.isclose(Registers.to_f32(reg.peek(Reg.AL)), math.sin(math.pi / 4), rel_tol=1e-4)

    reg.set(Reg.AL, Registers.from_f32(math.pi / 4))
    alu.cos_f32(Reg.AL)
    assert math.isclose(Registers.to_f32(reg.peek(Reg.AL)), math.cos(math.pi / 4), rel_tol=1e-4)

    reg.set(Reg.AL, Registers.from_f32(math.pi / 4))
    alu.tan_f32(Reg.AL)
    assert math.isclose(Registers.to_f32(reg.peek(Reg.AL)), 1.0, rel_tol=1e-3)

    reg.set(Reg.AX, Registers.from_f64(math.pi / 4))
    alu.sin_f64(Reg.AX)
    assert math.isclose(Registers.to_f64(reg.peek(Reg.AX)), math.sin(math.pi / 4), rel_tol=1e-12)

    reg.set(Reg.AX, Registers.from_f64(math.pi / 4))
    alu.cos_f64(Reg.AX)
    assert math.isclose(Registers.to_f64(reg.peek(Reg.AX)), math.cos(math.pi / 4), rel_tol=1e-12)

    reg.set(Reg.AX, Registers.from_f64(math.pi / 4))
    alu.tan_f64(Reg.AX)
    assert math.isclose(Registers.to_f64(reg.peek(Reg.AX)), 1.0, rel_tol=1e-10)
