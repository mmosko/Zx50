"""Integration tests for UserOpcode.DIV_U32 executed via the microcode dispatcher."""

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
        # High bit set treated as unsigned magnitude
        (0xFFFFFFFF, 2, 0x7FFFFFFF, False, False, "4294967295 / 2 = 2147483647"),
        (0xFFFFFFFF, 0xFFFFFFFF, 1, False, False, "max uint32 / max uint32 = 1"),
        (0x80000000, 2, 0x40000000, False, False, "2147483648 / 2 = 1073741824"),
        (0x80000000, 1, 0x80000000, False, True, "2147483648 / 1 = 2147483648 (MSB set)"),
        (10, 20, 0, True, False, "10 / 20 = 0"),
    ],
)
def test_user_opcode_div_u32(
    fpga: FpgaModel, a: int, b: int, expected_quot: int, exp_zf: bool, exp_sf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.DIV_U32 via dispatcher with stack operands (a / b)."""
    user_push32(fpga, a)
    user_push32(fpga, b)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.DIV_U32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf

    res = user_pop32(fpga)
    assert res == expected_quot
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_div_u32_divide_by_zero(fpga: FpgaModel) -> None:
    """Tests executing UserOpcode.DIV_U32 with divisor 0 triggers ERR and aborts push."""
    user_push32(fpga, 42)
    user_push32(fpga, 0)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.DIV_U32)

    # Both operands popped, push aborted due to ERR
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_div_u32_underflow(fpga: FpgaModel) -> None:
    """Tests DIV_U32 underflow with insufficient stack depth."""
    # Stack empty
    fpga.dispatcher.execute(UserOpcode.DIV_U32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # Only 1 operand on stack
    user_push32(fpga, 10)
    fpga.dispatcher.execute(UserOpcode.DIV_U32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
