from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


def test_micro_instruction_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=18, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode ADD AL, BL
    orig = MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL, flag=0, imm=0)
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.ADD
    assert decoded.w == IW.W32
    assert decoded.dst == Reg.AL
    assert decoded.src == Reg.BL
    assert decoded.flag == 0


def test_micro_instruction_jump_with_flag():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=18, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode JNZ with StatusFlag.UNDERFLOW and imm=42
    orig = MicroInstruction(
        op=MicroOp.JNZ,
        w=IW.W32,
        flag=StatusFlag.UNDERFLOW,
        imm=42,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.JNZ
    assert decoded.flag == StatusFlag.UNDERFLOW.value
    assert imm_reg.read_int() == 42
