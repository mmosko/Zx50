"""Integration tests for UserOpcode.SUB_I64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        (0, 0, 0, False, True, False, False, "zero - zero"),
        (35, 10, 25, False, False, False, False, "35 - 10 = 25"),
        (10, 35, 0xFFFFFFFFFFFFFFE7, True, False, True, False, "10 - 35 = -25 (borrow)"),
        (300, 100, 200, False, False, False, False, "300 - 100 = 200"),
        # Carry propagation (borrow from high word into low word) without 64-bit borrow out
        (0x00000002_00000000, 1, 0x00000001_FFFFFFFF, False, False, False, False, "borrow from high word"),
        (0x00000003_00000000, 0x00000001_00000000, 0x00000002_00000000, False, False, False, False, "high words only"),
        # Unsigned boundary & borrow out (64-bit)
        (0, 1, 0xFFFFFFFFFFFFFFFF, True, False, True, False, "0 - 1 = -1 (borrow)"),
        (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF, 0, False, True, False, False, "max uint64 - max uint64"),
        (0xFFFFFFFFFFFFFFFF, 1, 0xFFFFFFFFFFFFFFFE, False, False, True, False, "max uint64 - 1"),
        # Signed positive overflow: max int64 - (-1)
        (0x7FFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF, 0x8000000000000000, True, False, True, True, "max int64 - (-1)"),
        # Signed negative overflow: min int64 - 1
        (0x8000000000000000, 1, 0x7FFFFFFFFFFFFFFF, False, False, False, True, "min int64 - 1"),
        # Negative numbers
        (0xFFFFFFFFFFFFFFF6, 0xFFFFFFFFFFFFFFF6, 0, False, True, False, False, "(-10) - (-10) = 0"),
        (0xFFFFFFFFFFFFFFF6, 5, 0xFFFFFFFFFFFFFFF1, False, False, True, False, "(-10) - 5 = -15"),
        (5, 0xFFFFFFFFFFFFFFF6, 15, True, False, False, False, "5 - (-10) = 15 (borrow unsigned)"),
    ],
)
def test_user_opcode_sub_i64(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, exp_vf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.SUB_I64 via dispatcher with 64-bit stack operands (a - b)."""
    # Push minuend a then subtrahend b
    user_push64(fpga, a)
    user_push64(fpga, b)
    assert fpga.reg_file.sp.read_int() == 4

    # Execute user opcode SUB_I64
    fpga.dispatcher.execute(UserOpcode.SUB_I64)

    # After SUB_I64, stack pointer should be 2 (popped 4 words, pushed 2 words)
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Status flags: CARRY (borrow), ZERO, and SIGN are preserved from SUB 64;
    # OVERFLOW and ERR are cleared by the subsequent successful PUSH.
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) == exp_cf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    # Pop result from stack
    res = user_pop64(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_sub_i64_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing SUB_I64 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.SUB_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_sub_i64_underflow_single_word_on_stack(fpga: FpgaModel) -> None:
    """Executing SUB_I64 with only one 32-bit word must trigger underflow during first 64-bit pop."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.SUB_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_sub_i64_underflow_single_64bit_operand(fpga: FpgaModel) -> None:
    """Executing SUB_I64 with only one 64-bit operand must trigger underflow during second 64-bit pop."""
    user_push64(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.SUB_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_sub_i64_underflow_three_words_on_stack(fpga: FpgaModel) -> None:
    """Executing SUB_I64 with 3 words (1 full operand + half of second) must trigger underflow."""
    user_push64(fpga, 100)
    user_push32(fpga, 200)
    assert fpga.reg_file.sp.read_int() == 3

    fpga.dispatcher.execute(UserOpcode.SUB_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
