"""Integration tests for UserOpcode.DIV_I32 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected_quot,exp_zf,exp_sf,desc",
    [
        (100, 5, 20, False, False, "100 / 5 = 20"),
        (7, 2, 3, False, False, "7 / 2 = 3"),
        (0, 15, 0, True, False, "0 / 15 = 0"),
        (-100, 5, -20, False, True, "(-100) / 5 = -20"),
        (100, -5, -20, False, True, "100 / (-5) = -20"),
        (-100, -5, 20, False, False, "(-100) / (-5) = 20"),
        (7, -2, -3, False, True, "7 / (-2) = -3"),
        (-7, 2, -3, False, True, "(-7) / 2 = -3"),
        (-7, -2, 3, False, False, "(-7) / (-2) = 3"),
        (0x7FFFFFFF, 1, 0x7FFFFFFF, False, False, "max_int / 1"),
        (0x7FFFFFFF, 0x7FFFFFFF, 1, False, False, "max_int / max_int = 1"),
    ],
)
def test_user_opcode_div_i32(
    fpga: FpgaModel, a: int, b: int, expected_quot: int, exp_zf: bool, exp_sf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.DIV_I32 via dispatcher with stack operands (a / b)."""
    # Push dividend a (NOS), then divisor b (TOS)
    user_push32(fpga, a & 0xFFFFFFFF)
    user_push32(fpga, b & 0xFFFFFFFF)
    assert fpga.reg_file.sp.read_int() == 2

    # Execute DIV_I32
    fpga.dispatcher.execute(UserOpcode.DIV_I32)

    # After DIV_I32, stack pointer should be 1 (popped 2, pushed 1)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf

    # Pop quotient from stack
    res = user_pop32(fpga)
    expected_u32 = expected_quot & 0xFFFFFFFF
    assert res == expected_u32
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_div_i32_divide_by_zero(fpga: FpgaModel) -> None:
    """Tests executing UserOpcode.DIV_I32 with divisor 0 triggers ERR and aborts push."""
    user_push32(fpga, 42)
    user_push32(fpga, 0)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.DIV_I32)

    # Both operands were popped before DIV, and push aborted due to ERR
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_div_i32_underflow(fpga: FpgaModel) -> None:
    """Tests DIV_I32 underflow with insufficient stack depth."""
    # Stack empty
    fpga.dispatcher.execute(UserOpcode.DIV_I32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # Only 1 operand on stack
    user_push32(fpga, 10)
    fpga.dispatcher.execute(UserOpcode.DIV_I32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
