"""Integration tests for UserOpcode.MUL_I64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode

MASK_64 = 0xFFFFFFFFFFFFFFFF


@pytest.mark.parametrize(
    "a,b,expected_res,desc",
    [
        (0, 0, 0, "zero * zero"),
        (10, 0, 0, "positive * zero"),
        (0, 10, 0, "zero * positive"),
        (10, 25, 250, "small positive integers: 10 * 25"),
        (100000, 200000, 20000000000, "100,000 * 200,000 = 20,000,000,000"),
        # Crossing 32-bit boundary into high word
        (0x1_00000000, 3, 0x3_00000000, "2^32 * 3 = 3 * 2^32"),
        (0x1_00000002, 0x2_00000003, 0x7_00000006, "cross terms across 32-bit boundary"),
        # Positive * Negative
        (10, (-5) & MASK_64, (-50) & MASK_64, "10 * (-5) = -50"),
        ((-10) & MASK_64, 25, (-250) & MASK_64, "(-10) * 25 = -250"),
        # Negative * Negative
        ((-10) & MASK_64, (-5) & MASK_64, 50, "(-10) * (-5) = 50"),
        # Multiplying by 1 and -1
        (0x12345678_9ABCDEF0, 1, 0x12345678_9ABCDEF0, "X * 1 = X"),
        (
            0x12345678_9ABCDEF0,
            (-1) & MASK_64,
            (-0x12345678_9ABCDEF0) & MASK_64,
            "X * (-1) = -X",
        ),
        # 64-bit wrap (high product bits discarded mod 2^64)
        (0x2_00000000, 0x2_00000000, 0, "2^33 * 2^33 = 2^66 -> wraps to 0 mod 2^64"),
        (
            0x7FFFFFFF_FFFFFFFF,
            2,
            0xFFFFFFFF_FFFFFFFE,
            "large 64-bit product wraps mod 2^64",
        ),
    ],
)
def test_user_opcode_mul_i64(
    fpga: FpgaModel, a: int, b: int, expected_res: int, desc: str
) -> None:
    """Tests executing UserOpcode.MUL_I64 via dispatcher with 64-bit stack operands."""
    user_push64(fpga, a)
    user_push64(fpga, b)
    assert fpga.reg_file.sp.read_int() == 4

    fpga.dispatcher.execute(UserOpcode.MUL_I64)

    # After MUL_I64, stack pointer should be 2 (popped 4 words, pushed 2 words)
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    res = user_pop64(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_mul_i64_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing MUL_I64 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.MUL_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_mul_i64_underflow_single_32bit_operand(fpga: FpgaModel) -> None:
    """Executing MUL_I64 with only 1 word (32-bit) on stack must trigger underflow on 1st pop."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.MUL_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_mul_i64_underflow_single_64bit_operand(fpga: FpgaModel) -> None:
    """Executing MUL_I64 with only 1 64-bit word (2 words) on stack triggers underflow on 2nd pop."""
    user_push64(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.MUL_I64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_mul_i64_timing_cycles(fpga: FpgaModel) -> None:
    """Verifies clock cycle execution count for MUL_I64."""
    user_push64(fpga, 10)
    user_push64(fpga, 25)

    cycles_before = fpga.clock.cycles
    fpga.dispatcher.execute(UserOpcode.MUL_I64)
    cycles_elapsed = fpga.clock.cycles - cycles_before

    # 3 x 32-bit MULU (16 cycles each = 48 cycles) + memory STO/LD + 64-bit POP/PUSH = ~60-80 cycles
    assert 50 <= cycles_elapsed <= 120
    res = user_pop64(fpga)
    assert res == 250
