"""Integration tests for UserOpcode.SIN_F32 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        # Quadrant 0 angles (0 <= x <= pi/2)
        (0.0, 0.0, "sin(0)"),
        (-0.0, -0.0, "sin(-0)"),
        (0.1, math.sin(0.1), "sin(0.1)"),
        (math.pi / 6.0, math.sin(math.pi / 6.0), "sin(pi/6) = 0.5"),
        (math.pi / 4.0, math.sin(math.pi / 4.0), "sin(pi/4) = sqrt(2)/2"),
        (math.pi / 3.0, math.sin(math.pi / 3.0), "sin(pi/3) = sqrt(3)/2"),
        (math.pi / 2.0, 1.0, "sin(pi/2) = 1.0"),
        # Negative quadrant 0 angles
        (-0.1, math.sin(-0.1), "sin(-0.1)"),
        (-math.pi / 6.0, math.sin(-math.pi / 6.0), "sin(-pi/6) = -0.5"),
        (-math.pi / 4.0, math.sin(-math.pi / 4.0), "sin(-pi/4) = -sqrt(2)/2"),
        (-math.pi / 3.0, math.sin(-math.pi / 3.0), "sin(-pi/3) = -sqrt(3)/2"),
        (-math.pi / 2.0, -1.0, "sin(-pi/2) = -1.0"),
        # Quadrant 1, 2, 3 angles (pi/2 < x <= 2*pi)
        (2.0 * math.pi / 3.0, math.sin(2.0 * math.pi / 3.0), "sin(2pi/3)"),
        (3.0 * math.pi / 4.0, math.sin(3.0 * math.pi / 4.0), "sin(3pi/4)"),
        (math.pi, math.sin(math.pi), "sin(pi) = 0"),
        (-math.pi, math.sin(-math.pi), "sin(-pi) = -0"),
        (7.0 * math.pi / 6.0, math.sin(7.0 * math.pi / 6.0), "sin(7pi/6)"),
        (3.0 * math.pi / 2.0, -1.0, "sin(3pi/2) = -1.0"),
        (-3.0 * math.pi / 2.0, 1.0, "sin(-3pi/2) = 1.0"),
        (2.0 * math.pi, math.sin(2.0 * math.pi), "sin(2pi) = 0"),
        (-2.0 * math.pi, math.sin(-2.0 * math.pi), "sin(-2pi) = -0"),
        # Larger angles
        (10.0, math.sin(10.0), "sin(10)"),
        (-10.0, math.sin(-10.0), "sin(-10)"),
        (50.0, math.sin(50.0), "sin(50)"),
        (100.0, math.sin(100.0), "sin(100)"),
        # Tiny angles (|x| < 2^-12)
        (1e-5, 1e-5, "sin(1e-5) ~ 1e-5"),
        (-1e-5, -1e-5, "sin(-1e-5) ~ -1e-5"),
        (1e-7, 1e-7, "sin(1e-7) ~ 1e-7"),
    ],
)
def test_user_opcode_sin_f32(fpga: FpgaModel, x: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.SIN_F32 via dispatcher."""
    user_push32(fpga, f32_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.SIN_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    if abs(expected) < 1e-6:
        assert abs(res_float - expected) < 2e-4, f"{desc}: got {res_float}, expected {expected}"
    else:
        assert math.isclose(res_float, expected, rel_tol=1e-4, abs_tol=1e-4), (
            f"{desc}: got {res_float}, expected {expected}"
        )


def test_user_opcode_sin_f32_special_cases(fpga: FpgaModel) -> None:
    """Tests executing UserOpcode.SIN_F32 on NaN and Inf."""
    # Test NaN
    user_push32(fpga, f32_to_bits(float("nan")))
    fpga.dispatcher.execute(UserOpcode.SIN_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    res_float = bits_to_f32(user_pop32(fpga))
    assert math.isnan(res_float)

    # Test +Inf
    user_push32(fpga, f32_to_bits(float("inf")))
    fpga.dispatcher.execute(UserOpcode.SIN_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    res_float = bits_to_f32(user_pop32(fpga))
    assert math.isnan(res_float)
