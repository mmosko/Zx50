"""Integration tests for UserOpcode.ADD_I64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        (0, 0, 0, False, True, False, False, "zero + zero"),
        (10, 25, 35, False, False, False, False, "small positive integers"),
        (100, 200, 300, False, False, False, False, "100 + 200"),
        # Carry propagation across 32-bit boundary into high word
        (0x00000001_FFFFFFFF, 1, 0x00000002_00000000, False, False, False, False, "low word carry to high word"),
        (0x00000000_00000001, 0x00000001_00000000, 0x00000001_00000001, False, False, False, False, "low and high non-zero"),
        (0x00000001_00000000, 0x00000002_00000000, 0x00000003_00000000, False, False, False, False, "high words only"),
        # Unsigned boundary & carry out (64-bit)
        (0xFFFFFFFFFFFFFFFF, 1, 0, True, True, False, False, "max uint64 + 1"),
        (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFE, True, False, True, False, "max uint64 + max uint64"),
        # Signed positive overflow
        (0x7FFFFFFFFFFFFFFF, 1, 0x8000000000000000, False, False, True, True, "max int64 + 1"),
        (0x7FFFFFFFFFFFFFFF, 0x7FFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFE, False, False, True, True, "max int64 + max int64"),
        # Signed negative overflow
        (0x8000000000000000, 0x8000000000000000, 0, True, True, False, True, "min int64 + min int64"),
        (0x8000000000000000, 0xFFFFFFFFFFFFFFFF, 0x7FFFFFFFFFFFFFFF, True, False, False, True, "min int64 + (-1)"),
        # Mixed sign addition
        (0xFFFFFFFFFFFFFFF6, 10, 0, True, True, False, False, "(-10) + 10"),
        (0xFFFFFFFFFFFFFFF6, 5, 0xFFFFFFFFFFFFFFFB, False, False, True, False, "(-10) + 5 = -5"),
        (10, 0xFFFFFFFFFFFFFFFB, 5, True, False, False, False, "10 + (-5) = 5"),
    ],
)
def test_user_opcode_add_i64(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, exp_vf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.ADD_I64 via dispatcher with 64-bit stack operands."""
    # Push operand a then operand b
    user_push64(fpga, a)
    user_push64(fpga, b)
    assert fpga.reg_file.sp.read_int() == 4

    # Execute user opcode ADD_I64
    fpga.dispatcher.execute(UserOpcode.ADD_I64)

    # After ADD_I64, stack pointer should be 2 (popped 4 words, pushed 2 words)
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Status flags: CARRY, ZERO, and SIGN are preserved from ADD 64;
    # OVERFLOW and ERR are cleared by the subsequent successful PUSH.
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) == exp_cf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    # Pop result from stack
    res = user_pop64(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_add_i64_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing ADD_I64 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.ADD_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_add_i64_underflow_single_word_on_stack(fpga: FpgaModel) -> None:
    """Executing ADD_I64 with only one 32-bit word must trigger underflow during first 64-bit pop."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.ADD_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_add_i64_underflow_single_64bit_operand(fpga: FpgaModel) -> None:
    """Executing ADD_I64 with only one 64-bit operand must trigger underflow during second 64-bit pop."""
    user_push64(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.ADD_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_add_i64_underflow_three_words_on_stack(fpga: FpgaModel) -> None:
    """Executing ADD_I64 with 3 words (1 full operand + half of second) must trigger underflow."""
    user_push64(fpga, 100)
    user_push32(fpga, 200)
    assert fpga.reg_file.sp.read_int() == 3

    fpga.dispatcher.execute(UserOpcode.ADD_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
