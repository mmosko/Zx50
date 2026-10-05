"""Integration tests for UserOpcode.ADD_I32 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import Reg, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.user_opcodes import UserOpcode


def _push32(fpga: FpgaModel, val: int) -> None:
    """Helper to push a 32-bit word onto the math stack."""
    fpga.reg_file.al.write(val)
    fpga.reg_file.upc.write(0)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.PUSH, src=Reg.AL)])


def _pop32(fpga: FpgaModel) -> int:
    """Helper to pop a 32-bit word from the math stack into DL."""
    fpga.reg_file.upc.write(0)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.POP, dst=Reg.DL)])
    return fpga.reg_file.dl.read_int()


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        (0, 0, 0, False, True, False, False, "zero + zero"),
        (10, 25, 35, False, False, False, False, "small positive integers"),
        (100, 200, 300, False, False, False, False, "100 + 200"),
        # Unsigned boundary & carry out
        (0xFFFFFFFF, 1, 0, True, True, False, False, "max uint32 + 1"),
        (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFE, True, False, True, False, "max uint32 + max uint32"),
        # Signed positive overflow
        (0x7FFFFFFF, 1, 0x80000000, False, False, True, True, "max int32 + 1"),
        (0x7FFFFFFF, 0x7FFFFFFF, 0xFFFFFFFE, False, False, True, True, "max int32 + max int32"),
        # Signed negative overflow
        (0x80000000, 0x80000000, 0, True, True, False, True, "min int32 + min int32"),
        (0x80000000, 0xFFFFFFFF, 0x7FFFFFFF, True, False, False, True, "min int32 + (-1)"),
        # Mixed sign addition
        (0xFFFFFFF6, 10, 0, True, True, False, False, "(-10) + 10"),
        (0xFFFFFFF6, 5, 0xFFFFFFFB, False, False, True, False, "(-10) + 5 = -5"),
        (10, 0xFFFFFFFB, 5, True, False, False, False, "10 + (-5) = 5"),
    ],
)
def test_user_opcode_add_i32(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, exp_vf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.ADD_I32 via dispatcher with stack operands."""
    # Push operand a then operand b
    _push32(fpga, a)
    _push32(fpga, b)
    assert fpga.reg_file.sp.read_int() == 2

    # Execute user opcode ADD_I32
    fpga.dispatcher.execute(UserOpcode.ADD_I32)

    # After ADD_I32, stack pointer should be 1 (popped 2, pushed 1)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Status flags: CARRY, ZERO, and SIGN are preserved from ADD;
    # OVERFLOW and ERR are cleared by the subsequent successful PUSH.
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) == exp_cf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    # Pop result from stack
    res = _pop32(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_add_i32_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing ADD_I32 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.ADD_I32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_add_i32_underflow_single_operand(fpga: FpgaModel) -> None:
    """Executing ADD_I32 with only 1 item on stack must trigger underflow on 2nd pop."""
    _push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.ADD_I32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
