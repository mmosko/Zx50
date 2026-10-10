"""Integration tests for UserOpcode.MUL_U32 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,exp_zf,exp_sf,desc",
    [
        (0, 0, 0, False, True, False, "zero * zero"),
        (10, 25, 250, False, False, False, "10 * 25 = 250 (fits in 32-bit, CF=0)"),
        (6, 7, 42, False, False, False, "6 * 7 = 42"),
        (100, 200, 20000, False, False, False, "100 * 200 = 20000"),
        (0x12345678, 1, 0x12345678, False, False, False, "X * 1 = X"),
        # High word non-zero -> CF = True
        (0x00010000, 0x00010000, 0, True, False, False, "65536 * 65536 = 2^32 -> product = 0x1_00000000 (CF=1)"),
        (0x00010000, 0x00020000, 0, True, False, False, "65536 * 131072 = 2 * 2^32 -> product = 0x2_00000000 (CF=1)"),
        (0xFFFFFFFF, 2, 0xFFFFFFFE, True, False, False, "max uint32 * 2 -> product = 0x1_FFFFFFFE (bit 63 is 0, CF=1)"),
        (0x80000000, 2, 0, True, False, False, "0x80000000 * 2 -> product = 0x1_00000000 (CF=1)"),
        (0xFFFFFFFF, 0xFFFFFFFF, 1, True, False, True, "max uint32 * max uint32 -> product = 0xFFFFFFFE00000001 (bit 63 is 1, CF=1)"),
    ],
)
def test_user_opcode_mul_u32(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.MUL_U32 via dispatcher with stack operands (a * b)."""
    user_push32(fpga, a)
    user_push32(fpga, b)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.MUL_U32)

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


def test_mul_u32_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing MUL_U32 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.MUL_U32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_mul_u32_underflow_single_operand(fpga: FpgaModel) -> None:
    """Executing MUL_U32 with only 1 item on stack must trigger underflow on 2nd pop."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.MUL_U32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
