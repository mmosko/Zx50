"""Integration tests for CHS opcodes (CHS_I32, CHS_I64, CHS_F32, CHS_F64) executed via dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode


# ==============================================================================
# CHS_I32 Tests
# ==============================================================================


@pytest.mark.parametrize(
    "val,expected_res,exp_zf,exp_sf,exp_vf,desc",
    [
        (0, 0, True, False, False, "chs(0) = 0"),
        (42, -42 & 0xFFFFFFFF, False, True, False, "chs(42) = -42"),
        (-42 & 0xFFFFFFFF, 42, False, False, False, "chs(-42) = 42"),
        (1, 0xFFFFFFFF, False, True, False, "chs(1) = -1"),
        (0xFFFFFFFF, 1, False, False, False, "chs(-1) = 1"),
        (0x7FFFFFFF, 0x80000001, False, True, False, "chs(max_int)"),
        (0x80000000, 0x80000000, False, True, True, "chs(min_int) -> overflow"),
    ],
)
def test_user_opcode_chs_i32(
    fpga: FpgaModel, val: int, expected_res: int, exp_zf: bool, exp_sf: bool, exp_vf: bool, desc: str
) -> None:
    user_push32(fpga, val)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CHS_I32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf

    res = user_pop32(fpga)
    assert res == expected_res


def test_user_opcode_chs_i32_underflow(fpga: FpgaModel) -> None:
    fpga.dispatcher.execute(UserOpcode.CHS_I32)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


# ==============================================================================
# CHS_I64 Tests
# ==============================================================================


@pytest.mark.parametrize(
    "val,expected_res,exp_zf,exp_sf,exp_vf,desc",
    [
        (0, 0, True, False, False, "chs(0) = 0"),
        (100, -100 & 0xFFFFFFFFFFFFFFFF, False, True, False, "chs(100) = -100"),
        (-100 & 0xFFFFFFFFFFFFFFFF, 100, False, False, False, "chs(-100) = 100"),
        (1, 0xFFFFFFFFFFFFFFFF, False, True, False, "chs(1) = -1"),
        (0x7FFFFFFFFFFFFFFF, 0x8000000000000001, False, True, False, "chs(max_int64)"),
        (0x8000000000000000, 0x8000000000000000, False, True, True, "chs(min_int64) -> overflow"),
    ],
)
def test_user_opcode_chs_i64(
    fpga: FpgaModel, val: int, expected_res: int, exp_zf: bool, exp_sf: bool, exp_vf: bool, desc: str
) -> None:
    user_push64(fpga, val)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.CHS_I64)

    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf

    res = user_pop64(fpga)
    assert res == expected_res


def test_user_opcode_chs_i64_underflow(fpga: FpgaModel) -> None:
    # Empty stack
    fpga.dispatcher.execute(UserOpcode.CHS_I64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # Partial (only 32-bit pushed)
    user_push32(fpga, 42)
    fpga.dispatcher.execute(UserOpcode.CHS_I64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


# ==============================================================================
# CHS_F32 & CHS_F64 Tests
# ==============================================================================


def test_user_opcode_chs_f32(fpga: FpgaModel) -> None:
    # +1.0f in IEEE-754: 0x3F800000 -> -1.0f: 0xBF800000
    user_push32(fpga, 0x3F800000)
    fpga.dispatcher.execute(UserOpcode.CHS_F32)
    res = user_pop32(fpga)
    assert res == 0xBF800000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)

    # -1.0f -> +1.0f
    user_push32(fpga, 0xBF800000)
    fpga.dispatcher.execute(UserOpcode.CHS_F32)
    res = user_pop32(fpga)
    assert res == 0x3F800000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_user_opcode_chs_f64(fpga: FpgaModel) -> None:
    # +1.0 in IEEE-754 double: 0x3FF0000000000000 -> -1.0: 0xBFF0000000000000
    user_push64(fpga, 0x3FF0000000000000)
    fpga.dispatcher.execute(UserOpcode.CHS_F64)
    res = user_pop64(fpga)
    assert res == 0xBFF0000000000000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)

    # -1.0 -> +1.0
    user_push64(fpga, 0xBFF0000000000000)
    fpga.dispatcher.execute(UserOpcode.CHS_F64)
    res = user_pop64(fpga)
    assert res == 0x3FF0000000000000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
