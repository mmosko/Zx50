import pytest

from fpu_asm.assembler import Assembler
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import StatusFlag
from fpu_emu.micro_instruction import IW
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.rom.fpu_const_map import FpuConst, FpuTable


def test_assemble_sample_program():
    code = """
        .org 0x000
    start:
        ADD AL, BL          ; 2-operand 32-bit addition
        ADD AX, BX, DL      ; 3-operand 64-bit addition
        LDC AL, CONST, 0x02 ; Load pi constant
        JNZ ERR, start      ; Conditional jump on error
        HALT
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    assert isinstance(prog, list)
    assert len(prog) == 5
    assert [addr for addr, _ in prog] == [0, 1, 2, 3, 4]

    prog_dict = dict(prog)

    # [0] ADD AL, BL
    u0 = prog_dict[0]
    assert u0.op == MicroOp.ADD
    assert u0.w == IW.W32
    assert u0.dst == Reg.AL
    assert u0.src == Reg.BL
    assert u0.src1 == Reg.AL
    assert u0.imm == 0

    # [1] ADD AX, BX, DL (64-bit)
    u1 = prog_dict[1]
    assert u1.op == MicroOp.ADD
    assert u1.w == IW.W64
    assert u1.dst == Reg.AL
    assert u1.src1 == Reg.BL
    assert u1.src == Reg.DL

    # [2] LDC AL, CONST, 0x02
    u2 = prog_dict[2]
    assert u2.op == MicroOp.LDC
    assert u2.w == IW.W32
    assert u2.dst == Reg.AL
    assert u2.src == FpuTable.CONST
    assert u2.imm == 2

    # [3] JNZ ERR, start (start == 0)
    u3 = prog_dict[3]
    assert u3.op == MicroOp.JNZ
    assert u3.flag == StatusFlag.ERR
    assert u3.imm == 0

    # [4] HALT
    u4 = prog_dict[4]
    assert u4.op == MicroOp.HALT


def test_forward_and_backward_labels():
    code = """
        .org 0x010
    loop_start:
        ADD AL, #1
        CMP AL, #10
        JZ ZERO, loop_end
        JMP loop_start
    loop_end:
        RET
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    assert isinstance(prog, list)
    prog_dict = dict(prog)

    assert prog_dict[0x010].imm == 1
    assert prog_dict[0x010].src == Reg.IMM
    assert prog_dict[0x011].op == MicroOp.CMP
    assert prog_dict[0x011].imm == 10
    # JZ jumps to loop_end (0x014)
    assert prog_dict[0x012].op == MicroOp.JZ
    assert prog_dict[0x012].imm == 0x014
    # JMP jumps to loop_start (0x010)
    assert prog_dict[0x013].op == MicroOp.JMP
    assert prog_dict[0x013].imm == 0x010
    # RET
    assert prog_dict[0x014].op == MicroOp.RET


def test_equ_and_align_directives():
    code = """
        .equ MY_CONST, 42
        .org 0x001
        LDI BL, MY_CONST
        .align 4
    aligned_entry:
        NOP
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    assert isinstance(prog, list)
    prog_dict = dict(prog)

    assert prog_dict[1].op == MicroOp.LDI
    assert prog_dict[1].dst == Reg.BL
    assert prog_dict[1].imm == 42
    # 0x001 + 1 instruction = address 2, aligned to 4 becomes 4
    assert 4 in prog_dict
    assert prog_dict[4].op == MicroOp.NOP


def test_symbolic_constants():
    code = """
        LDC FL, CONST, PI_F32
        PUSH FL
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    assert isinstance(prog, list)
    prog_dict = dict(prog)

    assert prog_dict[0].op == MicroOp.LDC
    assert prog_dict[0].src == FpuTable.CONST
    assert prog_dict[0].imm == FpuConst.PI_F32.value
    assert prog_dict[1].op == MicroOp.PUSH
    assert prog_dict[1].src == Reg.FL


def test_undefined_symbol_raises():
    code = """
        JMP non_existent_label
    """
    assembler = Assembler()
    with pytest.raises(Exception):
        assembler.assemble(code)
