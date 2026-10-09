"""Integration tests for UserOpcode.POW_F32 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "base,exp,expected,desc",
    [
        # Identity powers: y^0 == 1.0
        (2.0, 0.0, 1.0, "2^0 = 1.0"),
        (10.0, 0.0, 1.0, "10^0 = 1.0"),
        (0.5, 0.0, 1.0, "0.5^0 = 1.0"),
        (1.0, 0.0, 1.0, "1^0 = 1.0"),
        (0.0, 0.0, 1.0, "0^0 = 1.0"),
        # Base 1.0: 1^x == 1.0
        (1.0, 1.0, 1.0, "1^1 = 1.0"),
        (1.0, 2.0, 1.0, "1^2 = 1.0"),
        (1.0, -2.0, 1.0, "1^-2 = 1.0"),
        (1.0, 0.5, 1.0, "1^0.5 = 1.0"),
        (1.0, 100.0, 1.0, "1^100 = 1.0"),
        # Base 0.0 with positive exponent: 0^x == 0.0
        (0.0, 1.0, 0.0, "0^1 = 0.0"),
        (0.0, 2.0, 0.0, "0^2 = 0.0"),
        (0.0, 0.5, 0.0, "0^0.5 = 0.0"),
        # Integer powers of 2
        (2.0, 1.0, 2.0, "2^1 = 2.0"),
        (2.0, 2.0, 4.0, "2^2 = 4.0"),
        (2.0, 3.0, 8.0, "2^3 = 8.0"),
        (2.0, 4.0, 16.0, "2^4 = 16.0"),
        (2.0, 8.0, 256.0, "2^8 = 256.0"),
        (2.0, -1.0, 0.5, "2^-1 = 0.5"),
        (2.0, -2.0, 0.25, "2^-2 = 0.25"),
        (2.0, -3.0, 0.125, "2^-3 = 0.125"),
        # Integer powers of other integers
        (3.0, 2.0, 9.0, "3^2 = 9.0"),
        (3.0, 3.0, 27.0, "3^3 = 27.0"),
        (10.0, 2.0, 100.0, "10^2 = 100.0"),
        (10.0, -2.0, 0.01, "10^-2 = 0.01"),
        (5.0, 3.0, 125.0, "5^3 = 125.0"),
        # Fractional powers (roots)
        (4.0, 0.5, 2.0, "4^0.5 = 2.0"),
        (9.0, 0.5, 3.0, "9^0.5 = 3.0"),
        (16.0, 0.25, 2.0, "16^0.25 = 2.0"),
        (2.0, 0.5, math.sqrt(2.0), "2^0.5 = sqrt(2)"),
        (8.0, 1.0 / 3.0, 2.0, "8^(1/3) = 2.0"),
        (27.0, 1.0 / 3.0, 3.0, "27^(1/3) = 3.0"),
        # General floating-point powers
        (1.5, 2.5, 1.5**2.5, "1.5^2.5"),
        (2.7, 1.8, 2.7**1.8, "2.7^1.8"),
        (0.5, 0.5, 0.5**0.5, "0.5^0.5"),
        (0.25, -1.5, 0.25**-1.5, "0.25^-1.5 = 8.0"),
    ],
)
def test_user_opcode_pow_f32(fpga: FpgaModel, base: float, exp: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.POW_F32 via dispatcher: computes base^exp."""
    # Forth convention: ( base exp -- res )
    user_push32(fpga, f32_to_bits(base))
    user_push32(fpga, f32_to_bits(exp))
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.POW_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    assert pytest.approx(res_float, rel=1e-3, abs=1e-5) == expected, (
        f"Failed {desc}: got {res_float}, expected {expected}"
    )


def test_user_opcode_pow_f32_domain_error(fpga: FpgaModel) -> None:
    """Tests that negative base raises domain error (ERR=1)."""
    user_push32(fpga, f32_to_bits(-2.0))
    user_push32(fpga, f32_to_bits(3.0))
    fpga.dispatcher.execute(UserOpcode.POW_F32)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_pow_f32_zero_neg_exp(fpga: FpgaModel) -> None:
    """Tests that 0^(negative) returns +Inf and asserts ERR=1, VF=1."""
    user_push32(fpga, f32_to_bits(0.0))
    user_push32(fpga, f32_to_bits(-2.0))
    fpga.dispatcher.execute(UserOpcode.POW_F32)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    res_bits = user_pop32(fpga)
    assert res_bits == 0x7F800000  # POS_INF_F32


def test_user_opcode_pow_f32_stack_underflow(fpga: FpgaModel) -> None:
    """Tests that POW_F32 with < 2 stack entries asserts UF=1."""
    user_push32(fpga, f32_to_bits(2.0))
    fpga.dispatcher.execute(UserOpcode.POW_F32)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
