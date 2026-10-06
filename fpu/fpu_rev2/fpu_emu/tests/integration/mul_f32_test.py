"""Integration tests for UserOpcode.MUL_F32 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected,desc",
    [
        # Normal multiplication without mantissa overflow (1.f_A * 1.f_B < 2.0)
        (1.5, 1.0, 1.5, "1.5 * 1.0"),
        (1.5, 2.0, 3.0, "1.5 * 2.0"),
        (1.25, 1.5, 1.875, "1.25 * 1.5"),
        (10.0, 2.0, 20.0, "10.0 * 2.0"),
        (0.5, 0.5, 0.25, "0.5 * 0.5"),
        # Normal multiplication with mantissa overflow (1.f_A * 1.f_B >= 2.0)
        (1.5, 1.5, 2.25, "1.5 * 1.5"),
        (1.75, 1.75, 3.0625, "1.75 * 1.75"),
        (3.0, 3.0, 9.0, "3.0 * 3.0"),
        (5.0, 7.0, 35.0, "5.0 * 7.0"),
        (12.34, 5.0, 61.7, "12.34 * 5.0"),
        # Sign handling
        (3.0, 4.0, 12.0, "3.0 * 4.0"),
        (3.0, -4.0, -12.0, "3.0 * -4.0"),
        (-3.0, 4.0, -12.0, "-3.0 * 4.0"),
        (-3.0, -4.0, 12.0, "-3.0 * -4.0"),
        (-0.5, -0.5, 0.25, "-0.5 * -0.5"),
        # Identity / negation
        (42.0, 1.0, 42.0, "42.0 * 1.0"),
        (42.0, -1.0, -42.0, "42.0 * -1.0"),
        (-42.0, 1.0, -42.0, "-42.0 * 1.0"),
        (-42.0, -1.0, 42.0, "-42.0 * -1.0"),
        # Zero operand handling
        (0.0, 5.0, 0.0, "0.0 * 5.0"),
        (5.0, 0.0, 0.0, "5.0 * 0.0"),
        (0.0, 0.0, 0.0, "0.0 * 0.0"),
        (-0.0, 5.0, -0.0, "-0.0 * 5.0"),
        (5.0, -0.0, -0.0, "5.0 * -0.0"),
        (-5.0, -0.0, 0.0, "-5.0 * -0.0"),
        # Dynamic range
        (1e10, 1e10, 1e20, "1e10 * 1e10"),
        (1e-10, 1e-10, 1e-20, "1e-10 * 1e-10"),
        (1e15, 1e-15, 1.0, "1e15 * 1e-15"),
    ],
)
def test_user_opcode_mul_f32(fpga: FpgaModel, a: float, b: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.MUL_F32 via dispatcher: computes (a * b)."""
    # Push operand a then operand b: TOS is b, under TOS is a
    user_push32(fpga, f32_to_bits(a))
    user_push32(fpga, f32_to_bits(b))
    assert fpga.reg_file.sp.read_int() == 2

    # Execute MUL_F32
    fpga.dispatcher.execute(UserOpcode.MUL_F32)

    # After MUL_F32, stack pointer should be 1
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Pop result from stack
    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    if expected == 0.0:
        # Check signed zero preservation
        assert res_float == 0.0, f"Failed {desc}: got {res_float}, expected 0.0"
        expected_sign = math.copysign(1.0, a) * math.copysign(1.0, b) < 0
        actual_sign = bool(res_bits & 0x80000000)
        assert actual_sign == expected_sign, f"Sign mismatch for {desc}: got sign {actual_sign}, expected {expected_sign}"
    else:
        assert pytest.approx(res_float, rel=1e-5) == expected, f"Failed {desc}: got {res_float}, expected {expected}"


def test_mul_f32_overflow(fpga: FpgaModel) -> None:
    """Tests that multiplying very large floats produces infinity."""
    user_push32(fpga, f32_to_bits(1e25))
    user_push32(fpga, f32_to_bits(1e25))
    fpga.dispatcher.execute(UserOpcode.MUL_F32)
    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert math.isinf(res_float)


def test_mul_f32_underflow(fpga: FpgaModel) -> None:
    """Tests that multiplying very small floats asserts UNDERFLOW flag and produces zero."""
    user_push32(fpga, f32_to_bits(1e-25))
    user_push32(fpga, f32_to_bits(1e-25))
    fpga.dispatcher.execute(UserOpcode.MUL_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert res_float == 0.0


def test_mul_f32_stack_underflow(fpga: FpgaModel) -> None:
    """Tests that MUL_F32 with empty stack asserts UNDERFLOW and ERR."""
    fpga.dispatcher.execute(UserOpcode.MUL_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_mul_f32_stack_single_operand(fpga: FpgaModel) -> None:
    """Tests that MUL_F32 with only one operand on stack asserts UNDERFLOW and ERR."""
    user_push32(fpga, f32_to_bits(1.0))
    fpga.dispatcher.execute(UserOpcode.MUL_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
