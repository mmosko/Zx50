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

    class MockBranchBlock(FunctionalBlock):
        def __init__(self, outputs, clock):
            self._outputs = outputs
            self._clock = clock

        def execute(self):
            # Advance clock for cycle and drive branch target on block_res bus to upc_mux
            self._clock.tick(1)
            self._outputs.block_res.set(target_upc)
            self._outputs.block_res_sel.set(Reg.UPC.value)
            self._outputs.exec_wb.set(1)

    # Install mock branch block as Block 3 (Control)
    fpga.blocks[3] = MockBranchBlock(outputs=fpga.control_block.outputs, clock=fpga.clock)

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
    long_microcode = [MicroInstruction(op=MicroOp.NOP)] * 1024

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
