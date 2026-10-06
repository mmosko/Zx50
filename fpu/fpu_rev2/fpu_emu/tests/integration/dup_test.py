"""Integration tests for DUP4 and DUP8 executed via microcode dispatcher."""

from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode


def test_user_opcode_dup4(fpga: FpgaModel) -> None:
    """Tests duplicating a 32-bit stack entry."""
    user_push32(fpga, 0x12345678)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.DUP4)

    # After DUP4, stack should have 2 identical entries
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    val1 = user_pop32(fpga)
    val2 = user_pop32(fpga)
    assert val1 == 0x12345678
    assert val2 == 0x12345678
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_dup4_underflow(fpga: FpgaModel) -> None:
    """Tests DUP4 underflow on empty stack."""
    fpga.dispatcher.execute(UserOpcode.DUP4)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_dup8(fpga: FpgaModel) -> None:
    """Tests duplicating a 64-bit stack entry."""
    user_push64(fpga, 0x0123456789ABCDEF)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.DUP8)

    # After DUP8, stack should have 4 words (two 64-bit entries)
    assert fpga.reg_file.sp.read_int() == 4
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    val1 = user_pop64(fpga)
    val2 = user_pop64(fpga)
    assert val1 == 0x0123456789ABCDEF
    assert val2 == 0x0123456789ABCDEF
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_dup8_underflow(fpga: FpgaModel) -> None:
    """Tests DUP8 underflow on empty or incomplete stack."""
    # Empty stack
    fpga.dispatcher.execute(UserOpcode.DUP8)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # Only 32-bit pushed
    user_push32(fpga, 0x12345678)
    fpga.dispatcher.execute(UserOpcode.DUP8)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
