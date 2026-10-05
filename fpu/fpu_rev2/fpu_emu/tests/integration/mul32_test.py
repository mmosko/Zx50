"""Integration tests for UserOpcode.MUL_I32 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,exp_zf,exp_sf,desc",
    [
        (0, 0, 0, False, True, False, "zero * zero"),
        (10, 25, 250, False, False, False, "small positive integers: 10 * 25"),
        (6, 7, 42, False, False, False, "6 * 7 = 42"),
        (100, 200, 20000, False, False, False, "100 * 200 = 20000"),
        # Positive * Negative
        (10, 0xFFFFFFFB, 0xFFFFFFCE, False, False, True, "10 * (-5) = -50"),
        (0xFFFFFFFB, 10, 0xFFFFFFCE, False, False, True, "(-5) * 10 = -50"),
        # Negative * Negative
        (0xFFFFFFF6, 0xFFFFFFFB, 50, False, False, False, "(-10) * (-5) = 50"),
        # Multiplying by 1 and -1
        (0x12345678, 1, 0x12345678, False, False, False, "X * 1 = X"),
        (0x12345678, 0xFFFFFFFF, 0xEDCBA988, False, False, True, "X * (-1) = -X"),
        # Truncation / 32-bit wrap (high word non-zero)
        (0x00010000, 0x00010000, 0, False, False, False, "65536 * 65536 = 2^32 -> low 32 bits 0"),
        (0x00010000, 0x00020000, 0, False, False, False, "65536 * 131072 = 2 * 2^32 -> low 32 bits 0"),
        (0x7FFFFFFF, 2, 0xFFFFFFFE, False, False, False, "max int32 * 2 -> 64-bit product is positive (+4294967294)"),
        (0x80000000, 1, 0x80000000, False, False, True, "min int32 * 1 -> 64-bit product is negative (-2147483648)"),
        (0x80000000, 0xFFFFFFFF, 0x80000000, False, False, False, "min int32 * (-1) -> 64-bit product is positive (+2147483648)"),
    ],
)
def test_user_opcode_mul_i32(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.MUL_I32 via dispatcher with stack operands (a * b)."""
    # Push operand a then operand b
    user_push32(fpga, a)
    user_push32(fpga, b)
    assert fpga.reg_file.sp.read_int() == 2

    # Execute user opcode MUL_I32
    fpga.dispatcher.execute(UserOpcode.MUL_I32)

    # After MUL_I32, stack pointer should be 1 (popped 2 words, pushed 1 word)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Status flags: CARRY (cleared by MUL), ZERO, and SIGN are preserved from MUL;
    # OVERFLOW and ERR are cleared by the subsequent successful PUSH.
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) == exp_cf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    # Pop result from stack
    res = user_pop32(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_mul_i32_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing MUL_I32 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.MUL_I32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_mul_i32_underflow_single_operand(fpga: FpgaModel) -> None:
    """Executing MUL_I32 with only 1 item on stack must trigger underflow on 2nd pop."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.MUL_I32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_mul_i32_timing_cycles(fpga: FpgaModel) -> None:
    """Verifies clock cycle execution count for MUL_I32."""
    user_push32(fpga, 6)
    user_push32(fpga, 7)

    cycles_before = fpga.clock.cycles
    fpga.dispatcher.execute(UserOpcode.MUL_I32)
    cycles_elapsed = fpga.clock.cycles - cycles_before

    # 1 (pipeline prime) + POP BL (~2) + JNZ (~1) + POP AL (~2) + JNZ (~1)
    # + MUL AL, BL (16) + PUSH AL (~2) + HALT (~1) = ~25-28 cycles
    assert 20 <= cycles_elapsed <= 35
    res = user_pop32(fpga)
    assert res == 42
