import pytest
from pathlib import Path

from fpu_emu.blocks.functional_block import FunctionalBlock
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import StatusFlag, UpcOverflowError
from fpu_emu.hardware.rom import Rom
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.user_opcodes import UserOpcode


@pytest.fixture
def fpga(tmp_path: Path):
    rom = Rom(size=16, rom_path=tmp_path / "dummy.rom")
    return FpgaModel(rom=rom)


def test_dispatcher_single_instruction_pipeline(fpga: FpgaModel):
    """Pipelined single instruction execution: T0 (fetch/prime), T1 (execute/writeback)."""
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x25)

    microcode = [
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    ]

    start_cycle = fpga.clock.cycles
    fpga.dispatcher._run(microcode)
    elapsed = fpga.clock.cycles - start_cycle

    # 1 cycle for T0 (fetch prime) + 1 cycle for T1 (execute) = 2 cycles total
    assert elapsed == 2
    assert fpga.reg_file.al.read_int() == 0x35
    # UPC should have advanced to 1
    assert fpga.dispatcher.upc == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_dispatcher_multi_instruction_pipeline(fpga: FpgaModel):
    """Pipelined multi-instruction execution: N instructions complete in N + 1 cycles."""
    fpga.reg_file.al.write(0x100)
    fpga.reg_file.bl.write(0x50)
    fpga.reg_file.dl.write(0x30)

    # microcode: AL = AL + BL (0x150), then AL = AL - DL (0x120)
    microcode = [
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(op=MicroOp.SUB, w=IW.W32, dst=Reg.AL, src=Reg.DL),
    ]

    start_cycle = fpga.clock.cycles
    fpga.dispatcher._run(microcode)
    elapsed = fpga.clock.cycles - start_cycle

    # T0 (fetch I0), T1 (exec I0, fetch I1), T2 (exec I1) = 3 cycles total
    assert elapsed == 3
    assert fpga.reg_file.al.read_int() == 0x120
    assert fpga.dispatcher.upc == 2


def test_dispatcher_branch_updates_upc(fpga: FpgaModel):
    """Execution block writing to UPC simulates a jump; dispatcher must branch to the new target."""
    target_upc = 2

    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x20)
    fpga.reg_file.dl.write(0x50)

    microcode = [
        # 0: Jump to target 2
        MicroInstruction(op=MicroOp.JMP, imm=target_upc),
        # 1: Should be skipped by the branch!
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        # 2: Target of jump: add DL (0x50) to AL (0x10)
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.DL),
    ]

    fpga.dispatcher._run(microcode)

    # AL should be 0x10 + 0x50 = 0x60 (instruction 1 skipped)
    assert fpga.reg_file.al.read_int() == 0x60
    assert fpga.dispatcher.upc == 3


def test_dispatcher_upc_overflow_raises_error(fpga: FpgaModel):
    """When UPC overflows 10 bits (>1023), UpcOverflowError must be raised and ERR flag asserted."""
    fpga.reg_file.upc.write(1023)
    long_microcode = [MicroInstruction(op=MicroOp.ADD, dst=Reg.NONE, src=Reg.NONE)] * 1024

    with pytest.raises(UpcOverflowError):
        fpga.dispatcher._run(long_microcode)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_dispatcher_control_commands_and_stack(fpga: FpgaModel):
    # Test batch mode flags
    fpga.dispatcher.execute(UserOpcode.SET_BATCH)
    assert fpga.dispatcher.batch_mode is True

    fpga.dispatcher.execute(UserOpcode.SET_IMMEDIATE)
    assert fpga.dispatcher.batch_mode is False

    # Test blocking mode and bwait_n
    fpga.dispatcher.execute(UserOpcode.SET_NONBLOCKING)
    assert fpga.dispatcher.blocking_mode is False
    assert fpga.dispatcher.bwait_n is True

    fpga.dispatcher.execute(UserOpcode.SET_BLOCKING)
    assert fpga.dispatcher.blocking_mode is True

    # Test stack clearing
    fpga.reg_file.sp.write(0x12)
    fpga.reg_file.osp.write(0x05)
    fpga.dispatcher.execute(UserOpcode.CLEAR_STACK)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.osp.read_int() == 0


def _push32(fpga: FpgaModel, val: int):
    fpga.reg_file.al.write(val)
    fpga.reg_file.upc.write(0)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.PUSH, src=Reg.AL)])


def _pop32(fpga: FpgaModel) -> int:
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
def test_dispatcher_user_opcode_add_i32(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, exp_vf: bool, desc: str
):
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


def test_dispatcher_add_i32_underflow_empty_stack(fpga: FpgaModel):
    """Executing ADD_I32 with empty stack must trigger underflow trap and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.ADD_I32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_dispatcher_add_i32_underflow_single_operand(fpga: FpgaModel):
    """Executing ADD_I32 with only 1 item on stack must trigger underflow on 2nd pop and trap."""
    fpga.reg_file.al.write(42)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.PUSH, src=Reg.AL)])
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.ADD_I32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True

