from fpu_asm.assembler import Assembler
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


def test_add_i32():
    code = """
    ADD_I32:
        POP BL
        JNZ UF, ADD_I32_HALT
        POP AL
        JNZ UF, ADD_I32_HALT
        ADD AL, BL
        PUSH AL
    ADD_I32_HALT:
        HALT
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    expected = [
            MicroInstruction(op=MicroOp.POP, w=IW.W32, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src1=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ]
    assert [u for _, u in prog] == expected
    assert [addr for addr, _ in prog] == list(range(len(expected)))
