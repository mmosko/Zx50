"""Integration tests for UserOpcode.DIV_I64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode

MASK_64 = 0xFFFFFFFFFFFFFFFF
SIGN_64 = 0x8000000000000000
MIN_INT64 = -0x8000000000000000


@pytest.mark.parametrize(
    "a,b,expected_quot,exp_zf,exp_sf,exp_vf,desc",
    [
        (100, 5, 20, False, False, False, "100 / 5 = 20"),
        (7, 2, 3, False, False, False, "7 / 2 = 3"),
        (0, 15, 0, True, False, False, "0 / 15 = 0"),
        (-100, 5, -20, False, True, False, "(-100) / 5 = -20"),
        (100, -5, -20, False, True, False, "100 / (-5) = -20"),
        (-100, -5, 20, False, False, False, "(-100) / (-5) = 20"),
        (7, -2, -3, False, True, False, "7 / (-2) = -3"),
        (-7, 2, -3, False, True, False, "(-7) / 2 = -3"),
        (-7, -2, 3, False, False, False, "(-7) / (-2) = 3"),
        # Crossing 32-bit boundary into high word
        (0x1_00000000, 2, 0x80000000, False, False, False, "2^32 / 2 = 2^31"),
        (0x12345678_9ABCDEF0, 1, 0x12345678_9ABCDEF0, False, False, False, "X / 1 = X"),
        (
            0x12345678_9ABCDEF0,
            -1,
            -0x12345678_9ABCDEF0,
            False,
            True,
            False,
            "X / (-1) = -X",
        ),
        (
            0x7FFFFFFF_FFFFFFFF,
            1,
            0x7FFFFFFF_FFFFFFFF,
            False,
            False,
            False,
            "max_int64 / 1",
        ),
        (
            0x7FFFFFFF_FFFFFFFF,
            0x7FFFFFFF_FFFFFFFF,
            1,
            False,
            False,
            False,
            "max_int64 / max_int64 = 1",
        ),
        (
            MIN_INT64,
            2,
            -0x40000000_00000000,
            False,
            True,
            False,
            "-2^63 / 2 = -2^62",
        ),
        (
            MIN_INT64,
            -2,
            0x40000000_00000000,
            False,
            False,
            False,
            "-2^63 / -2 = 2^62",
        ),
        # Signed 64-bit overflow: -2^63 / -1 -> overflow
        (
            MIN_INT64,
            -1,
            MIN_INT64,
            False,
            True,
            True,
            "-2^63 / -1 -> signed overflow",
        ),
        # Large 64-bit values
        (
            123456789012345678,
            987654321,
            124999998,
            False,
            False,
            False,
            "large positive division",
        ),
        (
            123456789012345678,
            -987654321,
            -124999998,
            False,
            True,
            False,
            "large positive / negative division",
        ),
        (
            -123456789012345678,
            -987654321,
            124999998,
            False,
            False,
            False,
            "large negative / negative division",
        ),
    ],
)
def test_user_opcode_div_i64(
    fpga: FpgaModel,
    a: int,
    b: int,
    expected_quot: int,
    exp_zf: bool,
    exp_sf: bool,
    exp_vf: bool,
    desc: str,
) -> None:
    """Tests executing UserOpcode.DIV_I64 via dispatcher with 64-bit stack operands (a / b)."""
    # Push dividend a (NOS), then divisor b (TOS)
    user_push64(fpga, a & MASK_64)
    user_push64(fpga, b & MASK_64)
    assert fpga.reg_file.sp.read_int() == 4

    # Execute DIV_I64
    fpga.dispatcher.execute(UserOpcode.DIV_I64)

    # After DIV_I64, stack pointer should be 2 (popped 4 words, pushed 2 words)
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) == exp_vf

    # Pop quotient from stack
    res = user_pop64(fpga)
    expected_u64 = expected_quot & MASK_64
    assert res == expected_u64
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_div_i64_divide_by_zero(fpga: FpgaModel) -> None:
    """Tests executing UserOpcode.DIV_I64 with divisor 0 triggers ERR and OVERFLOW, aborting push."""
    user_push64(fpga, 42)
    user_push64(fpga, 0)
    assert fpga.reg_file.sp.read_int() == 4

    fpga.dispatcher.execute(UserOpcode.DIV_I64)

    # Operands were popped before DIV, and push aborted due to divide-by-zero
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_div_i64_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing DIV_I64 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.DIV_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_user_opcode_div_i64_underflow_partial_stack(fpga: FpgaModel) -> None:
    """Executing DIV_I64 with fewer than 4 words must trigger underflow."""
    # 1 word (32-bit) on stack
    user_push32(fpga, 10)
    assert fpga.reg_file.sp.read_int() == 1
    fpga.dispatcher.execute(UserOpcode.DIV_I64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True

    # Reset stack and push 1 64-bit operand (2 words)
    fpga.reg_file.sp.write(0)
    fpga.reg_file.status.write(0)
    user_push64(fpga, 10)
    assert fpga.reg_file.sp.read_int() == 2
    fpga.dispatcher.execute(UserOpcode.DIV_I64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True

    # Reset stack and push 3 words
    fpga.reg_file.sp.write(0)
    fpga.reg_file.status.write(0)
    user_push64(fpga, 10)
    user_push32(fpga, 5)
    assert fpga.reg_file.sp.read_int() == 3
    fpga.dispatcher.execute(UserOpcode.DIV_I64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
