"""Integration tests for UserOpcode.SQRT_F32 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        # Perfect squares (exact root expected)
        (0.25, 0.5, "sqrt(0.25)"),
        (1.0, 1.0, "sqrt(1.0)"),
        (4.0, 2.0, "sqrt(4.0)"),
        (9.0, 3.0, "sqrt(9.0)"),
        (16.0, 4.0, "sqrt(16.0)"),
        (25.0, 5.0, "sqrt(25.0)"),
        (100.0, 10.0, "sqrt(100.0)"),
        (144.0, 12.0, "sqrt(144.0)"),
        (65536.0, 256.0, "sqrt(65536.0)"),
        # Non-perfect squares: [1.0, 2.0) (ODD_EXP branch)
        (2.0, math.sqrt(2.0), "sqrt(2.0)"),
        (1.5, math.sqrt(1.5), "sqrt(1.5)"),
        (1.2345, math.sqrt(1.2345), "sqrt(1.2345)"),
        (1.9999, math.sqrt(1.9999), "sqrt(1.9999)"),
        # Non-perfect squares: [2.0, 4.0) (EVEN_EXP branch)
        (3.0, math.sqrt(3.0), "sqrt(3.0)"),
        (2.5, math.sqrt(2.5), "sqrt(2.5)"),
        (3.5, math.sqrt(3.5), "sqrt(3.5)"),
        (3.9999, math.sqrt(3.9999), "sqrt(3.9999)"),
        # Fractions and numbers < 1.0
        (0.5, math.sqrt(0.5), "sqrt(0.5)"),
        (0.1, math.sqrt(0.1), "sqrt(0.1)"),
        (0.01, 0.1, "sqrt(0.01)"),
        (0.0001, 0.01, "sqrt(0.0001)"),
        # Large and small numbers across dynamic range
        (1e6, 1e3, "sqrt(1e6)"),
        (1e10, 1e5, "sqrt(1e10)"),
        (1e20, 1e10, "sqrt(1e20)"),
        (1e-10, 1e-5, "sqrt(1e-10)"),
        (1e-20, 1e-10, "sqrt(1e-20)"),
        (12345.67, math.sqrt(12345.67), "sqrt(12345.67)"),
        (987654.3, math.sqrt(987654.3), "sqrt(987654.3)"),
    ],
)
def test_user_opcode_sqrt_f32(fpga: FpgaModel, x: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.SQRT_F32 via dispatcher: computes sqrt(x)."""
    user_push32(fpga, f32_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 1

    # Execute SQRT_F32
    fpga.dispatcher.execute(UserOpcode.SQRT_F32)

    # After SQRT_F32, stack pointer should still be 1 (popped 1, pushed 1)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Pop result from stack
    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    # Within 1 ULP / relative error <= 1e-6
    assert pytest.approx(res_float, rel=1e-6) == expected, f"Failed {desc}: got {res_float}, expected {expected}"


@pytest.mark.parametrize(
    "x,expected_sign,desc",
    [
        (0.0, False, "sqrt(+0.0)"),
        (-0.0, True, "sqrt(-0.0)"),
    ],
)
def test_sqrt_f32_signed_zero(fpga: FpgaModel, x: float, expected_sign: bool, desc: str) -> None:
    """Tests IEEE-754 signed zero preservation: sqrt(+0.0) == +0.0, sqrt(-0.0) == -0.0."""
    user_push32(fpga, f32_to_bits(x))
    fpga.dispatcher.execute(UserOpcode.SQRT_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert res_float == 0.0, f"Failed {desc}: got {res_float}, expected 0.0"
    actual_sign = bool(res_bits & 0x80000000)
    assert actual_sign == expected_sign, f"Sign mismatch for {desc}: got {actual_sign}, expected {expected_sign}"


@pytest.mark.parametrize(
    "x,desc",
    [
        (-1.0, "sqrt(-1.0)"),
        (-4.0, "sqrt(-4.0)"),
        (-0.25, "sqrt(-0.25)"),
        (-1e10, "sqrt(-1e10)"),
        (float("-inf"), "sqrt(-inf)"),
    ],
)
def test_sqrt_f32_negative_domain_error(fpga: FpgaModel, x: float, desc: str) -> None:
    """Tests that negative operand asserts ERR and aborts push (domain error)."""
    user_push32(fpga, f32_to_bits(x))
    fpga.dispatcher.execute(UserOpcode.SQRT_F32)

    # Operand popped, nothing pushed -> SP == 0
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR), f"Expected ERR for {desc}"


def test_sqrt_f32_pos_inf(fpga: FpgaModel) -> None:
    """Tests that sqrt(+inf) == +inf."""
    user_push32(fpga, f32_to_bits(float("inf")))
    fpga.dispatcher.execute(UserOpcode.SQRT_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert math.isinf(res_float) and res_float > 0


def test_sqrt_f32_nan(fpga: FpgaModel) -> None:
    """Tests that sqrt(nan) == nan."""
    user_push32(fpga, f32_to_bits(float("nan")))
    fpga.dispatcher.execute(UserOpcode.SQRT_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert math.isnan(res_float)


def test_sqrt_f32_stack_underflow(fpga: FpgaModel) -> None:
    """Tests executing SQRT_F32 on an empty stack asserts UNDERFLOW and ERR."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.SQRT_F32)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.sp.read_int() == 0
