"""Integration tests for UserOpcode.DIV_F32 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected,desc",
    [
        # Normal division: a >= b (mantissa ratio >= 1.0, bit 24 set)
        (6.0, 2.0, 3.0, "6.0 / 2.0"),
        (1.5, 1.0, 1.5, "1.5 / 1.0"),
        (10.0, 2.0, 5.0, "10.0 / 2.0"),
        (20.0, 4.0, 5.0, "20.0 / 4.0"),
        (100.0, 10.0, 10.0, "100.0 / 10.0"),
        (35.0, 7.0, 5.0, "35.0 / 7.0"),
        (2.25, 1.5, 1.5, "2.25 / 1.5"),
        (61.7, 5.0, 12.34, "61.7 / 5.0"),
        (0.5, 0.5, 1.0, "0.5 / 0.5"),
        # Normal division: a < b (mantissa ratio < 1.0, bit 23 set)
        (1.0, 4.0, 0.25, "1.0 / 4.0"),
        (1.5, 2.0, 0.75, "1.5 / 2.0"),
        (1.0, 2.0, 0.5, "1.0 / 2.0"),
        (1.875, 2.5, 0.75, "1.875 / 2.5"),
        (1.0, 3.0, 1.0 / 3.0, "1.0 / 3.0"),
        (2.0, 3.0, 2.0 / 3.0, "2.0 / 3.0"),
        (1.0, 7.0, 1.0 / 7.0, "1.0 / 7.0"),
        # Sign handling
        (12.0, 3.0, 4.0, "12.0 / 3.0"),
        (12.0, -3.0, -4.0, "12.0 / -3.0"),
        (-12.0, 3.0, -4.0, "-12.0 / 3.0"),
        (-12.0, -3.0, 4.0, "-12.0 / -3.0"),
        (-0.25, -0.5, 0.5, "-0.25 / -0.5"),
        (-1.0, 4.0, -0.25, "-1.0 / 4.0"),
        # Identity / negation
        (42.0, 1.0, 42.0, "42.0 / 1.0"),
        (42.0, -1.0, -42.0, "42.0 / -1.0"),
        (-42.0, 1.0, -42.0, "-42.0 / 1.0"),
        (-42.0, -1.0, 42.0, "-42.0 / -1.0"),
        # Zero dividend handling (0.0 / b = 0.0)
        (0.0, 5.0, 0.0, "0.0 / 5.0"),
        (-0.0, 5.0, -0.0, "-0.0 / 5.0"),
        (0.0, -5.0, -0.0, "0.0 / -5.0"),
        (-0.0, -5.0, 0.0, "-0.0 / -5.0"),
        # Dynamic range
        (1e20, 1e10, 1e10, "1e20 / 1e10"),
        (1e-20, 1e-10, 1e-10, "1e-20 / 1e-10"),
        (1.0, 1e15, 1e-15, "1.0 / 1e15"),
        (1.0, 1e-15, 1e15, "1.0 / 1e-15"),
    ],
)
def test_user_opcode_div_f32(fpga: FpgaModel, a: float, b: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.DIV_F32 via dispatcher: computes (a / b)."""
    # Push operand a then operand b: TOS is b (divisor), under TOS is a (dividend)
    user_push32(fpga, f32_to_bits(a))
    user_push32(fpga, f32_to_bits(b))
    assert fpga.reg_file.sp.read_int() == 2

    # Execute DIV_F32
    fpga.dispatcher.execute(UserOpcode.DIV_F32)

    # After DIV_F32, stack pointer should be 1
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


@pytest.mark.parametrize(
    "a,b,desc",
    [
        (5.0, 0.0, "5.0 / 0.0"),
        (-5.0, 0.0, "-5.0 / 0.0"),
        (0.0, 0.0, "0.0 / 0.0"),
        (1.0, -0.0, "1.0 / -0.0"),
    ],
)
def test_div_f32_divide_by_zero(fpga: FpgaModel, a: float, b: float, desc: str) -> None:
    """Tests that dividing by zero asserts ERR and aborts push."""
    user_push32(fpga, f32_to_bits(a))
    user_push32(fpga, f32_to_bits(b))
    fpga.dispatcher.execute(UserOpcode.DIV_F32)

    # Operands popped, nothing pushed -> SP == 0
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR), f"Expected ERR for {desc}"


def test_div_f32_overflow(fpga: FpgaModel) -> None:
    """Tests that dividing by very small float produces infinity."""
    user_push32(fpga, f32_to_bits(1e25))
    user_push32(fpga, f32_to_bits(1e-25))
    fpga.dispatcher.execute(UserOpcode.DIV_F32)
    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert math.isinf(res_float)


def test_div_f32_underflow(fpga: FpgaModel) -> None:
    """Tests that dividing very small float by large float asserts UNDERFLOW flag and produces zero."""
    user_push32(fpga, f32_to_bits(1e-25))
    user_push32(fpga, f32_to_bits(1e25))
    fpga.dispatcher.execute(UserOpcode.DIV_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert res_float == 0.0


def test_div_f32_stack_underflow(fpga: FpgaModel) -> None:
    """Tests that DIV_F32 with empty stack asserts UNDERFLOW and ERR."""
    fpga.dispatcher.execute(UserOpcode.DIV_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_div_f32_stack_single_operand(fpga: FpgaModel) -> None:
    """Tests that DIV_F32 with only one operand on stack asserts UNDERFLOW and ERR."""
    user_push32(fpga, f32_to_bits(1.0))
    fpga.dispatcher.execute(UserOpcode.DIV_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
