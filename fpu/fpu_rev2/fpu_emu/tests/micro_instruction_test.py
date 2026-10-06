from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


def test_micro_instruction_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode ADD AL, BL
    orig = MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL, flag=None, imm=0)
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.ADD
    assert decoded.w == IW.W32
    assert decoded.dst == Reg.AL
    assert decoded.src == Reg.BL
    assert decoded.src1 == Reg.NONE
    assert decoded.flag == None


def test_micro_instruction_jump_with_flag():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
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


def test_micro_instruction_three_address_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode EXP_SUB C, EA, EB (C <- EA - EB)
    orig = MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.C, src1=Reg.EA, src=Reg.EB)
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.EXP_SUB
    assert decoded.dst == Reg.C
    assert decoded.src1 == Reg.EA
    assert decoded.src == Reg.EB


def test_micro_instruction_ldi_flag_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode LDI ERR, 1: dst=NONE, src=IMM, flag=ERR, imm=1
    orig = MicroInstruction(
        op=MicroOp.LDI,
        dst=Reg.NONE,
        src=Reg.IMM,
        flag=StatusFlag.ERR,
        imm=1,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.LDI
    assert decoded.dst == Reg.NONE
    assert decoded.flag == StatusFlag.ERR
    assert imm_reg.read_int() == 1


