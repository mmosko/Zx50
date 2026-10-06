"""Integration tests for UserOpcode.ADD_F32 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected,desc",
    [
        # Simple positive additions
        (1.0, 2.0, 3.0, "1.0 + 2.0"),
        (2.0, 1.0, 3.0, "2.0 + 1.0 (A > B)"),
        (1.5, 2.5, 4.0, "1.5 + 2.5"),
        (12.34, 56.78, 69.12, "12.34 + 56.78"),
        # Mantissa addition overflow (bit 24 -> LSR 1 & EXP+1)
        (1.0, 1.0, 2.0, "1.0 + 1.0 (sum overflows to 2.0)"),
        (1.75, 1.5, 3.25, "1.75 + 1.5"),
        # Swap operands (B > A in exponent)
        (0.25, 1.75, 2.0, "0.25 + 1.75 (swap operands)"),
        (1.0, 5.0, 6.0, "1.0 + 5.0"),
        # Swap operands (equal exponent, B > A in mantissa)
        (1.0, 1.5, 2.5, "1.0 + 1.5 (same exp, B mantissa larger)"),
        # Negative additions (same sign, negative result)
        (-1.0, -2.0, -3.0, "-1.0 + -2.0"),
        (-2.0, -1.0, -3.0, "-2.0 + -1.0"),
        (-1.5, -2.5, -4.0, "-1.5 + -2.5"),
        # Mixed signs: effective subtraction (|A| > |B|)
        (5.0, -2.0, 3.0, "5.0 + (-2.0)"),
        (-5.0, 2.0, -3.0, "-5.0 + 2.0"),
        (10.0, -3.0, 7.0, "10.0 + (-3.0)"),
        # Mixed signs: effective subtraction (|B| > |A|, swap triggered)
        (2.0, -5.0, -3.0, "2.0 + (-5.0) -> negative result"),
        (-2.0, 5.0, 3.0, "-2.0 + 5.0 -> positive result"),
        (0.75, -1.0, -0.25, "0.75 + (-1.0)"),
        # Exact cancellation to zero
        (1.0, -1.0, 0.0, "1.0 + (-1.0) (exact cancellation)"),
        (-2.5, 2.5, 0.0, "-2.5 + 2.5 (exact cancellation)"),
        (5.0, -5.0, 0.0, "5.0 + (-5.0) (exact cancellation)"),
        # Zero operand handling
        (0.0, 5.0, 5.0, "0.0 + 5.0"),
        (5.0, 0.0, 5.0, "5.0 + 0.0"),
        (0.0, 0.0, 0.0, "0.0 + 0.0"),
        (-5.0, 0.0, -5.0, "-5.0 + 0.0"),
        (0.0, -5.0, -5.0, "0.0 + (-5.0)"),
        # Shift differences >= 25 (smaller mantissa shifts out)
        (1000.0, 1e-10, 1000.0, "1000.0 + 1e-10 (diff > 24)"),
        (1e-10, 1000.0, 1000.0, "1e-10 + 1000.0 (diff > 24, swapped)"),
    ],
)
def test_user_opcode_add_f32(fpga: FpgaModel, a: float, b: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.ADD_F32 via dispatcher."""
    # Push operand a then operand b
    user_push32(fpga, f32_to_bits(a))
    user_push32(fpga, f32_to_bits(b))
    assert fpga.reg_file.sp.read_int() == 2

    # Execute ADD_F32
    fpga.dispatcher.execute(UserOpcode.ADD_F32)

    # After ADD_F32, stack pointer should be 1
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Pop result from stack
    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    if expected == 0.0:
        assert res_float == 0.0, f"Failed {desc}: got {res_float}, expected 0.0"
    else:
        assert pytest.approx(res_float, rel=1e-5) == expected, f"Failed {desc}: got {res_float}, expected {expected}"


def test_add_f32_stack_underflow(fpga: FpgaModel) -> None:
    """Tests that ADD_F32 with empty stack asserts UNDERFLOW and ERR."""
    fpga.dispatcher.execute(UserOpcode.ADD_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_add_f32_stack_single_operand(fpga: FpgaModel) -> None:
    """Tests that ADD_F32 with only one operand on stack asserts UNDERFLOW and ERR."""
    user_push32(fpga, f32_to_bits(1.0))
    fpga.dispatcher.execute(UserOpcode.ADD_F32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
