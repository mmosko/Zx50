from pathlib import Path

import pytest

from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


@pytest.fixture
def fpga(tmp_path: Path):
    rom = Rom(size=16, rom_path=tmp_path / "dummy.rom")
    return FpgaModel(rom=rom)


def test_control_jmp(fpga: FpgaModel):
    """JMP should immediately update UPC to target address."""
    target_upc = 2
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x20)
    fpga.reg_file.dl.write(0x50)

    microcode = [
        # 0: JMP to 2
        MicroInstruction(op=MicroOp.JMP, imm=target_upc),
        # 1: Skipped
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.BL),
        # 2: Target
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.DL),
    ]

    fpga.dispatcher._run(microcode)
    # AL should be 0x10 + 0x50 = 0x60 (instruction 1 skipped)
    assert fpga.reg_file.al.read_int() == 0x60
    assert fpga.dispatcher.upc == 3


def test_control_jz_branch_taken_and_not_taken(fpga: FpgaModel):
    """JZ branches only when ZF is set."""
    # Case 1: ZF = 1 (branch taken)
    fpga.reg_file.status.set_bit(StatusFlag.ZERO, True)
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x20)
    fpga.reg_file.dl.write(0x50)

    microcode = [
        MicroInstruction(op=MicroOp.JZ, imm=2),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.BL),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.DL),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.al.read_int() == 0x60

    # Case 2: ZF = 0 (branch NOT taken)
    fpga.clock.tick(1)
    fpga.reg_file.status.set_bit(StatusFlag.ZERO, False)
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.upc.write(0)

    fpga.dispatcher._run(microcode)
    # Both ADDs execute: 0x10 + 0x20 + 0x50 = 0x80
    assert fpga.reg_file.al.read_int() == 0x80


def test_control_jnz_branch_taken_and_not_taken(fpga: FpgaModel):
    """JNZ branches only when ZF is clear."""
    # Case 1: ZF = 0 (branch taken)
    fpga.reg_file.status.set_bit(StatusFlag.ZERO, False)
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x20)
    fpga.reg_file.dl.write(0x50)

    microcode = [
        MicroInstruction(op=MicroOp.JNZ, imm=2),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.BL),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.DL),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.al.read_int() == 0x60

    # Case 2: ZF = 1 (branch NOT taken)
    fpga.clock.tick(1)
    fpga.reg_file.status.set_bit(StatusFlag.ZERO, True)
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.upc.write(0)

    fpga.dispatcher._run(microcode)
    # Both ADDs execute: 0x10 + 0x20 + 0x50 = 0x80
    assert fpga.reg_file.al.read_int() == 0x80


def test_control_djnz_loop(fpga: FpgaModel):
    """DJNZ decrements C, sets ZF when C reaches 0, and branches until C is 0."""
    # Initialize C to 3
    fpga.reg_file.c.write(3)
    fpga.reg_file.al.write(0)
    fpga.reg_file.bl.write(1)

    microcode = [
        # 0: Loop body: AL += 1
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.BL),
        # 1: DJNZ back to 0
        MicroInstruction(op=MicroOp.DJNZ, imm=0),
    ]

    fpga.dispatcher._run(microcode)

    # After 3 iterations: AL == 3, C == 0, ZF == 1
    assert fpga.reg_file.al.read_int() == 3
    assert fpga.reg_file.c.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) is True


def test_control_call_and_ret(fpga: FpgaModel):
    """CALL jumps to subroutine and saves return address; RET jumps back."""
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x20)
    fpga.reg_file.dl.write(0x05)

    microcode = [
        # 0: CALL subroutine at address 3
        MicroInstruction(op=MicroOp.CALL, imm=3),
        # 1: After return: AL += DL (0x05)
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.DL),
        # 2: JMP to end (address 5) to skip subroutine body
        MicroInstruction(op=MicroOp.JMP, imm=5),
        # 3: Subroutine body: AL += BL (0x20)
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, src=Reg.BL),
        # 4: RET to saved address (1)
        MicroInstruction(op=MicroOp.RET),
        # 5: End
        MicroInstruction(op=MicroOp.NOP),
    ]

    fpga.dispatcher._run(microcode)

    # AL should be: 0x10 + 0x20 (subroutine) + 0x05 (post-return) = 0x35
    assert fpga.reg_file.al.read_int() == 0x35
    assert fpga.control_block._ret_set.read_int() == 0


def test_control_trap(fpga: FpgaModel):
    """TRAP asserts ERR status flag."""
    microcode = [
        MicroInstruction(op=MicroOp.TRAP),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True


def test_control_nop(fpga: FpgaModel):
    """NOP executes without changing registers or flags."""
    fpga.reg_file.al.write(0x42)
    start_cycle = fpga.clock.cycles
    microcode = [
        MicroInstruction(op=MicroOp.NOP),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.al.read_int() == 0x42
    assert fpga.clock.cycles - start_cycle == 2  # 1 prime + 1 exec


def test_control_nested_call_asserts(fpga: FpgaModel):
    """Nested CALL without RET should fail assertion."""
    microcode = [
        MicroInstruction(op=MicroOp.CALL, imm=1),
        MicroInstruction(op=MicroOp.CALL, imm=2),
    ]
    with pytest.raises(AssertionError, match="Nested microcode CALL is unsupported"):
        fpga.dispatcher._run(microcode)


def test_control_ret_without_call_asserts(fpga: FpgaModel):
    """RET without prior CALL should fail assertion."""
    microcode = [
        MicroInstruction(op=MicroOp.RET),
    ]
    with pytest.raises(AssertionError, match="Microcode RET without prior CALL"):
        fpga.dispatcher._run(microcode)


def test_control_unsupported_opcode_raises(fpga: FpgaModel):
    """Unsupported opcode sent to ControlBlock raises HardwareBusError."""
    from fpu_emu.hardware.registers import HardwareBusError

    MicroInstruction(op=MicroOp.ADD).to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    with pytest.raises(HardwareBusError, match="Unsupported opcode"):
        fpga.control_block.execute()

