"""Integration tests for UserOpcode.EXP2_F32 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        # Exact integer powers of 2
        (0.0, 1.0, "2^0.0"),
        (1.0, 2.0, "2^1.0"),
        (2.0, 4.0, "2^2.0"),
        (3.0, 8.0, "2^3.0"),
        (4.0, 16.0, "2^4.0"),
        (10.0, 1024.0, "2^10.0"),
        (20.0, 1048576.0, "2^20.0"),
        (50.0, 2**50, "2^50.0"),
        (-1.0, 0.5, "2^-1.0"),
        (-2.0, 0.25, "2^-2.0"),
        (-3.0, 0.125, "2^-3.0"),
        (-10.0, 2**-10, "2^-10.0"),
        # Fractional powers
        (0.5, math.sqrt(2.0), "2^0.5"),
        (-0.5, 1.0 / math.sqrt(2.0), "2^-0.5"),
        (1.5, 2.0 * math.sqrt(2.0), "2^1.5"),
        (-1.5, 0.5 / math.sqrt(2.0), "2^-1.5"),
        (3.5, 8.0 * math.sqrt(2.0), "2^3.5"),
        (-3.5, 0.125 / math.sqrt(2.0), "2^-3.5"),
        (0.33333333, 2**0.33333333, "2^(1/3)"),
        (-0.33333333, 2**-0.33333333, "2^(-1/3)"),
        (0.1, 2**0.1, "2^0.1"),
        (-0.1, 2**-0.1, "2^-0.1"),
        (0.01, 2**0.01, "2^0.01"),
        (-0.01, 2**-0.01, "2^-0.01"),
        (5.75, 2**5.75, "2^5.75"),
        (-5.75, 2**-5.75, "2^-5.75"),
        (12.345, 2**12.345, "2^12.345"),
        (-12.345, 2**-12.345, "2^-12.345"),
    ],
)
def test_user_opcode_exp2_f32(fpga: FpgaModel, x: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.EXP2_F32 via dispatcher: computes 2^x."""
    user_push32(fpga, f32_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.EXP2_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    assert pytest.approx(res_float, rel=1e-5, abs=1e-6) == expected, (
        f"Failed {desc}: got {res_float}, expected {expected}"
    )


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        (128.0, float("inf"), "2^128 (overflow to +inf)"),
        (200.0, float("inf"), "2^200 (overflow to +inf)"),
        (float("inf"), float("inf"), "2^(+inf) == +inf"),
        (-150.0, 0.0, "2^-150 (underflow to 0.0)"),
        (-200.0, 0.0, "2^-200 (underflow to 0.0)"),
    ],
)
def test_exp2_f32_extremes(fpga: FpgaModel, x: float, expected: float, desc: str) -> None:
    """Tests overflow to +inf and underflow to 0.0."""
    user_push32(fpga, f32_to_bits(x))
    fpga.dispatcher.execute(UserOpcode.EXP2_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    if math.isinf(expected):
        assert math.isinf(res_float) and res_float > 0
    else:
        assert res_float == expected


def test_exp2_f32_nan(fpga: FpgaModel) -> None:
    """Tests that 2^nan == nan."""
    user_push32(fpga, f32_to_bits(float("nan")))
    fpga.dispatcher.execute(UserOpcode.EXP2_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert math.isnan(res_float)


def test_exp2_f32_stack_underflow(fpga: FpgaModel) -> None:
    """Tests executing EXP2_F32 on an empty stack asserts UNDERFLOW and ERR."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.EXP2_F32)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.sp.read_int() == 0
