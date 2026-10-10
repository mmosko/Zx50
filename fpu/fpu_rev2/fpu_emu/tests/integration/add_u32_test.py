"""Integration tests for UserOpcode.ADD_U32 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,exp_zf,exp_sf,desc",
    [
        (0, 0, 0, False, True, False, "zero + zero"),
        (10, 25, 35, False, False, False, "small positive integers"),
        (100, 200, 300, False, False, False, "100 + 200"),
        (0xFFFFFFFF, 1, 0, True, True, False, "max uint32 + 1 (wrap to 0, carry set)"),
        (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFE, True, False, True, "max uint32 + max uint32 (carry set)"),
        (0x80000000, 0x80000000, 0, True, True, False, "0x80000000 + 0x80000000 (carry set)"),
        (0x7FFFFFFF, 1, 0x80000000, False, False, True, "0x7FFFFFFF + 1 (no carry, MSB set)"),
        (0xF0000000, 0x20000000, 0x10000000, True, False, False, "carry out without MSB in result"),
    ],
)
def test_user_opcode_add_u32(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.ADD_U32 via dispatcher with stack operands."""
    user_push32(fpga, a)
    user_push32(fpga, b)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.ADD_U32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) == exp_cf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    res = user_pop32(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_add_u32_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing ADD_U32 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.ADD_U32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_add_u32_underflow_single_operand(fpga: FpgaModel) -> None:
    """Executing ADD_U32 with only 1 item on stack must trigger underflow on 2nd pop."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.ADD_U32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
