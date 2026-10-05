"""Integration tests for UserOpcode.SUB_I32 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        (0, 0, 0, False, True, False, False, "zero - zero"),
        (35, 10, 25, False, False, False, False, "35 - 10 = 25"),
        (10, 35, 0xFFFFFFE7, True, False, True, False, "10 - 35 = -25 (borrow)"),
        (300, 100, 200, False, False, False, False, "300 - 100 = 200"),
        # Unsigned boundary & borrow out
        (0, 1, 0xFFFFFFFF, True, False, True, False, "0 - 1 = -1 (borrow)"),
        (0xFFFFFFFF, 0xFFFFFFFF, 0, False, True, False, False, "max uint32 - max uint32"),
        (0xFFFFFFFF, 1, 0xFFFFFFFE, False, False, True, False, "max uint32 - 1"),
        # Signed positive overflow: max int32 - (-1)
        (0x7FFFFFFF, 0xFFFFFFFF, 0x80000000, True, False, True, True, "max int32 - (-1)"),
        # Signed negative overflow: min int32 - 1
        (0x80000000, 1, 0x7FFFFFFF, False, False, False, True, "min int32 - 1"),
        # Negative numbers
        (0xFFFFFFF6, 0xFFFFFFF6, 0, False, True, False, False, "(-10) - (-10) = 0"),
        (0xFFFFFFF6, 5, 0xFFFFFFF1, False, False, True, False, "(-10) - 5 = -15"),
        (5, 0xFFFFFFF6, 15, True, False, False, False, "5 - (-10) = 15 (borrow unsigned)"),
    ],
)
def test_user_opcode_sub_i32(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, exp_vf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.SUB_I32 via dispatcher with stack operands (a - b)."""
    # Push minuend a then subtrahend b
    user_push32(fpga, a)
    user_push32(fpga, b)
    assert fpga.reg_file.sp.read_int() == 2

    # Execute user opcode SUB_I32
    fpga.dispatcher.execute(UserOpcode.SUB_I32)

    # After SUB_I32, stack pointer should be 1 (popped 2, pushed 1)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Status flags: CARRY (borrow), ZERO, and SIGN are preserved from SUB;
    # OVERFLOW and ERR are cleared by the subsequent successful PUSH.
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) == exp_cf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    # Pop result from stack
    res = user_pop32(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_sub_i32_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing SUB_I32 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.SUB_I32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_sub_i32_underflow_single_operand(fpga: FpgaModel) -> None:
    """Executing SUB_I32 with only 1 item on stack must trigger underflow on 2nd pop."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.SUB_I32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
