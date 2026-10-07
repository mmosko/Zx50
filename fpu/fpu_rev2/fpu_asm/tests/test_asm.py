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
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ]
    assert [u for _, u in prog] == expected
    assert [addr for addr, _ in prog] == list(range(len(expected)))

def test_add_f32():
    code = """
        ADD_F32:
            POP BL                      ; (pop operand B)
            JNZ UNDERFLOW, ADD_F32_HALT
            MOV DL, BL                  ; stash packed B into DL
            POP AL
            JNZ UNDERFLOW, ADD_F32_HALT
            MOV AH, AL                  ; stash packed A into AH for sign preservation)
            UNPACK BL, EB
            JZ ZERO, ADD_F32_RETURN_A   ; (RETURN_A: jump to PUSH AL, HALT)
            UNPACK AL, EA
            JZ ZERO, ADD_F32_RETURN_B    ; (RETURN_B: jump to PUSH DL, HALT)
            CMP EA, EB
            JNZ CARRY, ADD_F32_16        ; (SWAP_OPS: EA < EB)
            JNZ ZERO, ADD_F32_19         ;   (ALIGN_EXP: EA > EB)
            CMP AL, BL
            JNZ CARRY, ADD_F32_16        ; (SWAP_OPS: AL < BL)
            JMP ADD_F32_19               ; (ALIGN_EXP: AL >= BL)
        ADD_F32_16:
            SWAP AL, BL                 ; (larger mantissa in AL)
            SWAP EA, EB                 ; (larger exponent in EA)
            MOV AH, DL                  ; (AH now holds packed B with sign S_B)
        ADD_F32_19:
            EXP_SUB C, EA, EB           ; (C <- EA - EB; EA preserved!)
            CMP C, 32
            JNZ CARRY, ADD_F32_24       ; (DO_SHIFT: diff < 32)
            MOV BL, 0                   ; (diff >= 32: smaller mantissa shifts to 0)
            JMP ADD_F32_25              ; (DO_ARITH)
        ADD_F32_24:
            LSR BL, C                   ; (shift BL right by C)
        ADD_F32_25:
            JNZ DIFF_SIGN, ADD_F32_28   ; (DO_SUB)
            ADD AL, BL
            JMP NORMALIZE               ; (NORMALIZE)
        ADD_F32_28:
            SUB AL, BL
        NORMALIZE:
            LZC AL                              ; (leading zero count into C)
            JZ ZERO, ADD_F32_46                 ; (PACK_ZERO: exact cancellation)
            CMP C, 8
            JNZ CARRY, ADD_F32_OVERFLOW_RIGHT   ; (OVERFLOW_RIGHT: C < 8)
            JZ ZERO, ADD_F32_DONE_NORM          ; (DONE_NORM: C == 8)
            SUB C, 8                            ; (C <- C - 8)
            LSL AL, C                           ; (AL <- AL << C)
            EXP_SUB EA, C                       ; (EA <- EA - C)
            JMP ADD_F32_DONE_NORM
        ADD_F32_OVERFLOW_RIGHT:
            LSR AL, 1
            EXP_ADD EA, 1
        ADD_F32_DONE_NORM:
            OR AH, AH                       ; restores status.sign from bit 31 of AH
            PACK AL, EA
        ADD_F32_RETURN_A:
            PUSH AL
            HALT
        ADD_F32_RETURN_B:
            PUSH DL                 ; RETURN_B
            HALT
        ADD_F32_46:
            SUB AL, AL               ; (PACK_ZERO: AL <- 0)
            JMP ADD_F32_RETURN_A     ; (PUSH AL, HALT)
        ADD_F32_HALT:
            HALT
    """

    expected = [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=48),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.DL, src=Reg.BL),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=48),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AH, src=Reg.AL),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EB, src=Reg.BL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=42),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EA, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=44),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=16),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, imm=19),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=16),
            MicroInstruction(op=MicroOp.JMP, imm=19),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AH, src=Reg.DL),
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.C, src1=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.C, src=Reg.IMM, imm=32),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=24),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.IMM, imm=0),
            MicroInstruction(op=MicroOp.JMP, imm=25),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.BL, src=Reg.C),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.DIFF_SIGN, imm=28),
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.JMP, imm=29),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.LZC, dst=Reg.C, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=46),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.C, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=38),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=40),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.C, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.C),
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.C),
            MicroInstruction(op=MicroOp.JMP, imm=40),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AL, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AH),
            MicroInstruction(op=MicroOp.PACK, dst=Reg.AL, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.DL),
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.JMP, imm=42),
            MicroInstruction(op=MicroOp.HALT),
        ]

    assembler = Assembler()
    prog = assembler.assemble(code)
    assert Assembler.strip(prog) == expected

def test_sub_f32():
    code = """
        USER_SUB_F32:
            POP BL                         ; (pop operand B)
            JNZ UNDERFLOW, SUB_F32_49
            FCHS BL                        ; (invert sign bit: B <- -B)
            MOV DL, BL                     ; (stash packed -B into DL)
            POP AL                         ; (pop operand A)
            JNZ UNDERFLOW, SUB_F32_49
            MOV AH, AL                     ; (stash packed A into AH for sign preservation)
            UNPACK BL, EB                  ; (unpack -B)
            JZ ZERO, SUB_F32_43            ; (RETURN_A: jump to PUSH AL, HALT)
            UNPACK AL, EA                  ; (unpack A)
            JZ ZERO, SUB_F32_45           ;  (RETURN_B: jump to PUSH DL, HALT)
            CMP EA, EB
            JNZ CARRY, SUB_F32_17         ; (SWAP_OPS: EA < EB)
            JNZ ZERO, SUB_F32_20          ; (ALIGN_EXP: EA > EB)
            CMP AL, BL
            JNZ CARRY, SUB_F32_17         ;  (SWAP_OPS: AL < BL)
            JMP SUB_F32_20                ; (ALIGN_EXP: AL >= BL)
        SUB_F32_17:
            SWAP AL, BL                   ; (larger mantissa in AL)
            SWAP EA, EB                   ; (larger exponent in EA)
            MOV AH, DL                    ; (AH now holds packed larger operand sign)
        SUB_F32_20:
            EXP_SUB C, EA, EB             ; (C <- EA - EB; EA preserved!)
            CMP C, 32
            JNZ CARRY, SUB_F32_25         ; (DO_SHIFT: diff < 32)
            MOV BL, 0                     ; (diff >= 32: smaller mantissa shifts to 0)
            JMP SUB_F32_26                ; (DO_ARITH)
        SUB_F32_25:
            LSR BL, C                     ; (shift BL right by C)
        SUB_F32_26:
            JNZ DIFF_SIGN, SUB_F32_29     ; (DO_SUB)
            ADD AL, BL
            JMP SUB_F32_30               ; (NORMALIZE)
        SUB_F32_29:
            SUB AL, BL
        SUB_F32_30:
            LZC AL                        ; (leading zero count into C)
            JZ ZERO, SUB_F32_47           ;  (PACK_ZERO: exact cancellation)
            CMP C, 8
            JNZ CARRY, SUB_F32_39               ; (OVERFLOW_RIGHT: C < 8)
            JZ ZERO, SUB_F32_41           ;  (DONE_NORM: C == 8)
            SUB C, 8                  ; (C <- C - 8)
            LSL AL, C                 ;  (AL <- AL << C)
            EXP_SUB EA, C             ; (EA <- EA - C)
            JMP SUB_F32_41            ; (DONE_NORM)
        SUB_F32_39:
            LSR AL, 1
            EXP_ADD EA, 1
        SUB_F32_41:
            OR AH, AH                  ; (restores status.sign from bit 31 of AH)
            PACK AL, EA
        SUB_F32_43:
            PUSH AL
            HALT
        SUB_F32_45:
            PUSH DL                     ; (RETURN_B: -B)
            HALT
        SUB_F32_47:
            SUB AL, AL              ; (PACK_ZERO: AL <- 0)
            JMP SUB_F32_43
        SUB_F32_49:
            HALT
    """

    expected = [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=49),
            MicroInstruction(op=MicroOp.FCHS, dst=Reg.BL),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.DL, src=Reg.BL),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=49),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AH, src=Reg.AL),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EB, src=Reg.BL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=43),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EA, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=45),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=17),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, imm=20),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=17),
            MicroInstruction(op=MicroOp.JMP, imm=20),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AH, src=Reg.DL),
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.C, src1=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.C, src=Reg.IMM, imm=32),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=25),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.IMM, imm=0),
            MicroInstruction(op=MicroOp.JMP, imm=26),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.BL, src=Reg.C),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.DIFF_SIGN, imm=29),
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.JMP, imm=30),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.LZC, dst=Reg.C, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=47),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.C, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=39),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=41),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.C, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.C),
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.C),
            MicroInstruction(op=MicroOp.JMP, imm=41),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AL, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AH),
            MicroInstruction(op=MicroOp.PACK, dst=Reg.AL, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.DL),
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.JMP, imm=43),
            MicroInstruction(op=MicroOp.HALT),
        ]

    assembler = Assembler()
    prog = assembler.assemble(code)
    assert Assembler.strip(prog) == expected
