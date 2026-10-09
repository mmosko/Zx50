"""Integration tests for UserOpcode.TAN_F32 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        # Zeros
        (0.0, 0.0, "tan(0) = 0.0"),
        (-0.0, -0.0, "tan(-0) = -0.0"),
        # Small angles (115 <= EA < 126)
        (0.1, math.tan(0.1), "tan(0.1)"),
        (-0.1, math.tan(-0.1), "tan(-0.1)"),
        # Quadrant 0 angles (0 <= x < pi/2)
        (math.pi / 6.0, math.tan(math.pi / 6.0), "tan(pi/6) = 1/sqrt(3)"),
        (math.pi / 4.0, 1.0, "tan(pi/4) = 1.0"),
        (math.pi / 3.0, math.tan(math.pi / 3.0), "tan(pi/3) = sqrt(3)"),
        # Negative quadrant 0 angles (odd function: tan(-x) = -tan(x))
        (-math.pi / 6.0, math.tan(-math.pi / 6.0), "tan(-pi/6) = -1/sqrt(3)"),
        (-math.pi / 4.0, -1.0, "tan(-pi/4) = -1.0"),
        (-math.pi / 3.0, math.tan(-math.pi / 3.0), "tan(-pi/3) = -sqrt(3)"),
        # Quadrant 1, 2, 3 angles
        (2.0 * math.pi / 3.0, math.tan(2.0 * math.pi / 3.0), "tan(2pi/3) = -sqrt(3)"),
        (3.0 * math.pi / 4.0, -1.0, "tan(3pi/4) = -1.0"),
        (math.pi, 0.0, "tan(pi) = 0.0"),
        (-math.pi, -0.0, "tan(-pi) = -0.0"),
        (7.0 * math.pi / 6.0, math.tan(7.0 * math.pi / 6.0), "tan(7pi/6) = 1/sqrt(3)"),
        (5.0 * math.pi / 4.0, 1.0, "tan(5pi/4) = 1.0"),
        (4.0 * math.pi / 3.0, math.tan(4.0 * math.pi / 3.0), "tan(4pi/3) = sqrt(3)"),
        (2.0 * math.pi, 0.0, "tan(2pi) = 0.0"),
        (-2.0 * math.pi, -0.0, "tan(-2pi) = -0.0"),
        # Larger angles
        (10.0, math.tan(10.0), "tan(10)"),
        (-10.0, math.tan(-10.0), "tan(-10)"),
        (50.0, math.tan(50.0), "tan(50)"),
        (100.0, math.tan(100.0), "tan(100)"),
        # Tiny angles (|x| < 2^-12) -> tan(x) ~ x
        (1e-5, 1e-5, "tan(1e-5) ~ 1e-5"),
        (-1e-5, -1e-5, "tan(-1e-5) ~ -1e-5"),
        (1e-7, 1e-7, "tan(1e-7) ~ 1e-7"),
    ],
)
def test_user_opcode_tan_f32(fpga: FpgaModel, x: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.TAN_F32 via dispatcher."""
    user_push32(fpga, f32_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.TAN_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    if abs(expected) < 1e-5:
        assert abs(res_float - expected) < 2e-4, f"{desc}: got {res_float}, expected {expected}"
    else:
        assert math.isclose(res_float, expected, rel_tol=2e-3, abs_tol=2e-3), (
            f"{desc}: got {res_float}, expected {expected}"
        )


def test_user_opcode_tan_f32_special_cases(fpga: FpgaModel) -> None:
    """Tests executing UserOpcode.TAN_F32 on NaN and Inf."""
    # Test NaN
    user_push32(fpga, f32_to_bits(float("nan")))
    fpga.dispatcher.execute(UserOpcode.TAN_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    res_float = bits_to_f32(user_pop32(fpga))
    assert math.isnan(res_float)

    # Test +Inf
    user_push32(fpga, f32_to_bits(float("inf")))
    fpga.dispatcher.execute(UserOpcode.TAN_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    res_float = bits_to_f32(user_pop32(fpga))
    assert math.isnan(res_float)

    # Test -Inf
    user_push32(fpga, f32_to_bits(float("-inf")))
    fpga.dispatcher.execute(UserOpcode.TAN_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    res_float = bits_to_f32(user_pop32(fpga))
    assert math.isnan(res_float)
