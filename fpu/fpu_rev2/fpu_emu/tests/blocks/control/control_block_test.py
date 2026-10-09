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
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        # 2: Target
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.DL),
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
        MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=2),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.DL),
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
        MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, imm=2),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.DL),
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


@pytest.mark.parametrize(
    "flag,bit_set,should_branch,desc",
    [
        (StatusFlag.ZERO, True, False, "JNZ ZERO with ZF=1 (not taken)"),
        (StatusFlag.ZERO, False, True, "JNZ ZERO with ZF=0 (taken)"),
        (StatusFlag.UNDERFLOW, True, True, "JNZ UNDERFLOW with UF=1 (taken)"),
        (StatusFlag.UNDERFLOW, False, False, "JNZ UNDERFLOW with UF=0 (not taken)"),
        (StatusFlag.OVERFLOW, True, True, "JNZ OVERFLOW with VF=1 (taken)"),
        (StatusFlag.OVERFLOW, False, False, "JNZ OVERFLOW with VF=0 (not taken)"),
        (StatusFlag.CARRY, True, True, "JNZ CARRY with CF=1 (taken)"),
        (StatusFlag.CARRY, False, False, "JNZ CARRY with CF=0 (not taken)"),
        (StatusFlag.ERR, True, True, "JNZ ERR with ERR=1 (taken)"),
        (StatusFlag.ERR, False, False, "JNZ ERR with ERR=0 (not taken)"),
        (StatusFlag.SIGN, True, True, "JNZ SIGN with SF=1 (taken)"),
        (StatusFlag.SIGN, False, False, "JNZ SIGN with SF=0 (not taken)"),
    ],
)
def test_control_jnz_all_flags(fpga: FpgaModel, flag: StatusFlag, bit_set: bool, should_branch: bool, desc: str):
    """JNZ conditionally branches across each status flag according to its active polarity."""
    fpga.reg_file.status.set_bit(flag, bit_set)
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x20)
    fpga.reg_file.dl.write(0x50)

    microcode = [
        MicroInstruction(op=MicroOp.JNZ, flag=flag, imm=2),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.DL),
    ]
    fpga.dispatcher._run(microcode)
    expected_al = 0x60 if should_branch else 0x80
    assert fpga.reg_file.al.read_int() == expected_al


@pytest.mark.parametrize(
    "flag,bit_set,should_branch,desc",
    [
        (StatusFlag.ZERO, True, True, "JZ ZERO with ZF=1 (taken)"),
        (StatusFlag.ZERO, False, False, "JZ ZERO with ZF=0 (not taken)"),
        (StatusFlag.UNDERFLOW, True, False, "JZ UNDERFLOW with UF=1 (not taken)"),
        (StatusFlag.UNDERFLOW, False, True, "JZ UNDERFLOW with UF=0 (taken)"),
        (StatusFlag.OVERFLOW, True, False, "JZ OVERFLOW with VF=1 (not taken)"),
        (StatusFlag.OVERFLOW, False, True, "JZ OVERFLOW with VF=0 (taken)"),
        (StatusFlag.CARRY, True, False, "JZ CARRY with CF=1 (not taken)"),
        (StatusFlag.CARRY, False, True, "JZ CARRY with CF=0 (taken)"),
        (StatusFlag.ERR, True, False, "JZ ERR with ERR=1 (not taken)"),
        (StatusFlag.ERR, False, True, "JZ ERR with ERR=0 (taken)"),
        (StatusFlag.SIGN, True, False, "JZ SIGN with SF=1 (not taken)"),
        (StatusFlag.SIGN, False, True, "JZ SIGN with SF=0 (taken)"),
    ],
)
def test_control_jz_all_flags(fpga: FpgaModel, flag: StatusFlag, bit_set: bool, should_branch: bool, desc: str):
    """JZ conditionally branches across each status flag according to its active polarity."""
    fpga.reg_file.status.set_bit(flag, bit_set)
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x20)
    fpga.reg_file.dl.write(0x50)

    microcode = [
        MicroInstruction(op=MicroOp.JZ, flag=flag, imm=2),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.DL),
    ]
    fpga.dispatcher._run(microcode)
    expected_al = 0x60 if should_branch else 0x80
    assert fpga.reg_file.al.read_int() == expected_al


def test_control_djnz_loop(fpga: FpgaModel):
    """DJNZ decrements C, sets ZF when C reaches 0, and branches until C is 0."""
    # Initialize C to 3
    fpga.reg_file.c.write(3)
    fpga.reg_file.al.write(0)
    fpga.reg_file.bl.write(1)

    microcode = [
        # 0: Loop body: AL += 1
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
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
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.DL),
        # 2: JMP to end (address 5) to skip subroutine body
        MicroInstruction(op=MicroOp.JMP, imm=5),
        # 3: Subroutine body: AL += BL (0x20)
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        # 4: RET to saved address (1)
        MicroInstruction(op=MicroOp.RET),
        # 5: End
        MicroInstruction(op=MicroOp.HALT),
    ]

    fpga.dispatcher._run(microcode)

    # AL should be: 0x10 + 0x20 (subroutine) + 0x05 (post-return) = 0x35
    assert fpga.reg_file.al.read_int() == 0x35
    assert fpga.control_block._csp.read_int() == 0


def test_control_nop(fpga: FpgaModel):
    """NOP executes as a 1-cycle bubble with no writeback or status changes."""
    fpga.reg_file.al.write(0x12345678)
    initial_cycles = fpga.clock.cycles
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.NOP)])
    # Pipeline T0 (1 cycle) + NOP execute (1 cycle) = 2 cycles elapsed
    assert fpga.clock.cycles - initial_cycles == 2
    assert fpga.reg_file.al.read_int() == 0x12345678
    assert fpga.reg_file.status.read_int() == 0


def test_control_halt(fpga: FpgaModel):
    """HALT resets BSY flag and terminates microprogram execution, preserving ERR."""
    fpga.reg_file.status.set_bit(StatusFlag.BUSY, True)
    microcode = [
        MicroInstruction(op=MicroOp.HALT),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.BUSY) is False
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is False

    # Also test HALT with ERR already set (equivalent to TRAP)
    fpga.reg_file.upc.write(0)
    fpga.reg_file.status.set_bit(StatusFlag.ERR, True)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.HALT)])
    assert fpga.reg_file.status.is_bit_set(StatusFlag.BUSY) is False
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True


def test_control_nested_call_asserts(fpga: FpgaModel):
    """Nested CALL without RET beyond 16 levels should fail assertion."""
    microcode = [MicroInstruction(op=MicroOp.CALL, imm=i) for i in range(1, 18)]
    with pytest.raises(AssertionError, match="Call stack out of range"):
        fpga.dispatcher._run(microcode)


def test_control_ret_without_call_asserts(fpga: FpgaModel):
    """RET without prior CALL should fail assertion."""
    microcode = [
        MicroInstruction(op=MicroOp.RET),
    ]
    with pytest.raises(AssertionError, match="Call stack out of range"):
        fpga.dispatcher._run(microcode)


def test_control_unsupported_opcode_raises(fpga: FpgaModel):
    """Unsupported opcode sent to ControlBlock raises HardwareBusError."""
    from fpu_emu.hardware.registers import HardwareBusError

    MicroInstruction(op=MicroOp.ADD).to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    with pytest.raises(HardwareBusError, match="Unsupported opcode"):
        fpga.control_block.execute()

