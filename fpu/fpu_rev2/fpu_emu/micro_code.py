"""Microcode ROM mapping UserOpcode to micro-instruction sequences."""

from typing import Dict, List
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.registers import Reg, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.user_opcodes import UserOpcode


class MicroCode:
    """Microcode ROM lookup table."""

    MAX_MICRO_INSTRUCTIONS: int = 512

    _ucode: Dict[UserOpcode, List[MicroInstruction]] = {
        # ADD_I32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 6 (HALT)
        # 2: POP AL
        # 3: JNZ UNDERFLOW -> 6 (HALT)
        # 4: ADD AL, BL
        # 5: PUSH AL
        # 6: HALT
        UserOpcode.ADD_I32: [
            MicroInstruction(op=MicroOp.POP, w=IW.W32, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # ADD_F32:
        # 0: POP BL (pop operand B)
        # 1: JNZ UNDERFLOW -> 48 (TRAP)
        # 2: MOV DL, BL (stash packed B into DL)
        # 3: POP AL (pop operand A)
        # 4: JNZ UNDERFLOW -> 48 (TRAP)
        # 5: MOV AH, AL (stash packed A into AH for sign preservation)
        # 6: UNPACK BL, EB
        # 7: JZ ZERO -> 42 (RETURN_A: jump to PUSH AL, HALT)
        # 8: UNPACK AL, EA
        # 9: JZ ZERO -> 44 (RETURN_B: jump to PUSH DL, HALT)
        # 10: CMP EA, EB
        # 11: JNZ CARRY -> 16 (SWAP_OPS: EA < EB)
        # 12: JNZ ZERO -> 19 (ALIGN_EXP: EA > EB)
        # 13: CMP AL, BL
        # 14: JNZ CARRY -> 16 (SWAP_OPS: AL < BL)
        # 15: JMP 19 (ALIGN_EXP: AL >= BL)
        # 16: SWAP AL, BL (larger mantissa in AL)
        # 17: SWAP EA, EB (larger exponent in EA)
        # 18: MOV AH, DL (AH now holds packed B with sign S_B)
        # 19: EXP_SUB C, EA, EB (C <- EA - EB; EA preserved!)
        # 20: CMP C, IMM=32
        # 21: JNZ CARRY -> 24 (DO_SHIFT: diff < 32)
        # 22: MOV BL, IMM=0 (diff >= 32: smaller mantissa shifts to 0)
        # 23: JMP 25 (DO_ARITH)
        # 24: LSR BL, C (shift BL right by C)
        # 25: JNZ DIFF_SIGN -> 28 (DO_SUB)
        # 26: ADD AL, BL
        # 27: JMP 29 (NORMALIZE)
        # 28: SUB AL, BL
        # 29: LZC AL (leading zero count into C)
        # 30: JZ ZERO -> 46 (PACK_ZERO: exact cancellation)
        # 31: CMP C, IMM=8
        # 32: JNZ CARRY -> 38 (OVERFLOW_RIGHT: C < 8)
        # 33: JZ ZERO -> 40 (DONE_NORM: C == 8)
        # 34: SUB C, IMM=8 (C <- C - 8)
        # 35: LSL AL, C (AL <- AL << C)
        # 36: EXP_SUB EA, C (EA <- EA - C)
        # 37: JMP 40 (DONE_NORM)
        # 38: LSR AL, IMM=1
        # 39: EXP_ADD EA, IMM=1
        # 40: OR AH, AH (restores status.sign from bit 31 of AH)
        # 41: PACK AL, EA
        # 42: PUSH AL
        # 43: HALT
        # 44: PUSH DL (RETURN_B)
        # 45: HALT
        # 46: SUB AL, AL (PACK_ZERO: AL <- 0)
        # 47: JMP 42 (PUSH AL, HALT)
        # 48: HALT (TRAP)
        UserOpcode.ADD_F32: [
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
        ],
        # ADD_I64:
        # 0: POP BX
        # 1: JNZ UNDERFLOW -> 6 (HALT)
        # 2: POP AX
        # 3: JNZ UNDERFLOW -> 6 (HALT)
        # 4: ADD AX, BX
        # 5: PUSH AX
        # 6: HALT
        UserOpcode.ADD_I64: [
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.ADD, w=IW.W64, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # SUB_I32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 6 (HALT)
        # 2: POP AL
        # 3: JNZ UNDERFLOW -> 6 (HALT)
        # 4: SUB AL, BL
        # 5: PUSH AL
        # 6: HALT
        UserOpcode.SUB_I32: [
            MicroInstruction(op=MicroOp.POP, w=IW.W32, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # SUB_F32:
        # A - B = A + (-B)
        # 0: POP BL (pop operand B)
        # 1: JNZ UNDERFLOW -> 49 (TRAP)
        # 2: FCHS BL (invert sign bit: B <- -B)
        # 3: MOV DL, BL (stash packed -B into DL)
        # 4: POP AL (pop operand A)
        # 5: JNZ UNDERFLOW -> 49 (TRAP)
        # 6: MOV AH, AL (stash packed A into AH for sign preservation)
        # 7: UNPACK BL, EB (unpack -B)
        # 8: JZ ZERO -> 43 (RETURN_A: jump to PUSH AL, HALT)
        # 9: UNPACK AL, EA (unpack A)
        # 10: JZ ZERO -> 45 (RETURN_B: jump to PUSH DL, HALT)
        # 11: CMP EA, EB
        # 12: JNZ CARRY -> 17 (SWAP_OPS: EA < EB)
        # 13: JNZ ZERO -> 20 (ALIGN_EXP: EA > EB)
        # 14: CMP AL, BL
        # 15: JNZ CARRY -> 17 (SWAP_OPS: AL < BL)
        # 16: JMP 20 (ALIGN_EXP: AL >= BL)
        # 17: SWAP AL, BL (larger mantissa in AL)
        # 18: SWAP EA, EB (larger exponent in EA)
        # 19: MOV AH, DL (AH now holds packed larger operand sign)
        # 20: EXP_SUB C, EA, EB (C <- EA - EB; EA preserved!)
        # 21: CMP C, IMM=32
        # 22: JNZ CARRY -> 25 (DO_SHIFT: diff < 32)
        # 23: MOV BL, IMM=0 (diff >= 32: smaller mantissa shifts to 0)
        # 24: JMP 26 (DO_ARITH)
        # 25: LSR BL, C (shift BL right by C)
        # 26: JNZ DIFF_SIGN -> 29 (DO_SUB)
        # 27: ADD AL, BL
        # 28: JMP 30 (NORMALIZE)
        # 29: SUB AL, BL
        # 30: LZC AL (leading zero count into C)
        # 31: JZ ZERO -> 47 (PACK_ZERO: exact cancellation)
        # 32: CMP C, IMM=8
        # 33: JNZ CARRY -> 39 (OVERFLOW_RIGHT: C < 8)
        # 34: JZ ZERO -> 41 (DONE_NORM: C == 8)
        # 35: SUB C, IMM=8 (C <- C - 8)
        # 36: LSL AL, C (AL <- AL << C)
        # 37: EXP_SUB EA, C (EA <- EA - C)
        # 38: JMP 41 (DONE_NORM)
        # 39: LSR AL, IMM=1
        # 40: EXP_ADD EA, IMM=1
        # 41: OR AH, AH (restores status.sign from bit 31 of AH)
        # 42: PACK AL, EA
        # 43: PUSH AL
        # 44: HALT
        # 45: PUSH DL (RETURN_B: -B)
        # 46: HALT
        # 47: SUB AL, AL (PACK_ZERO: AL <- 0)
        # 48: JMP 43 (PUSH AL, HALT)
        # 49: HALT (TRAP)
        UserOpcode.SUB_F32: [
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
        ],
        # SUB_I64:
        # 0: POP BX
        # 1: JNZ UNDERFLOW -> 6 (HALT)
        # 2: POP AX
        # 3: JNZ UNDERFLOW -> 6 (HALT)
        # 4: SUB AX, BX
        # 5: PUSH AX
        # 6: HALT
        UserOpcode.SUB_I64: [
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.SUB, w=IW.W64, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # MUL_I32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 6 (HALT)
        # 2: POP AL
        # 3: JNZ UNDERFLOW -> 6 (HALT)
        # 4: MUL AL, BL
        # 5: PUSH AL
        # 6: HALT
        UserOpcode.MUL_I32: [
            MicroInstruction(op=MicroOp.POP, w=IW.W32, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=6),
            MicroInstruction(op=MicroOp.MUL, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # MUL_I64:
        # Scratchpad mapping:
        # SCR[0] = BL (B_low), SCR[1] = BH (B_high)
        # SCR[2] = AL (A_low), SCR[3] = AH (A_high)
        # SCR[4] = cross-terms sum
        #
        #  0: POP W64 BL
        #  1: JNZ UNDERFLOW -> 21 (HALT)
        #  2: STO 0, BL, W64
        #  3: POP W64 AL
        #  4: JNZ UNDERFLOW -> 21 (HALT)
        #  5: STO 2, AL, W64
        #  6: LD BL, 1            # BL = B_high
        #  7: MULU BL             # {AH, AL} = A_low * B_high
        #  8: STO 4, AL           # SCR[4] = (A_low * B_high)_low
        #  9: LD AL, 3            # AL = A_high
        # 10: LD BL, 0            # BL = B_low
        # 11: MULU BL             # {AH, AL} = A_high * B_low
        # 12: LD BL, 4            # BL = (A_low * B_high)_low
        # 13: ADD AL, BL          # AL = sum of cross terms
        # 14: STO 4, AL           # SCR[4] = sum of cross terms
        # 15: LD AL, 2            # AL = A_low
        # 16: LD BL, 0            # BL = B_low
        # 17: MULU BL             # {AH, AL} = A_low * B_low (AL is final product low word)
        # 18: LD BL, 4            # BL = sum of cross terms (AL untouched)
        # 19: ADD AH, BL          # AH = (A_low * B_low)_high + cross terms
        # 20: PUSH W64 AL         # Push {AH, AL}
        # 21: HALT
        UserOpcode.MUL_I64: [
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=21),
            MicroInstruction(op=MicroOp.STO, w=IW.W64, src=Reg.BL, imm=0),
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=21),
            MicroInstruction(op=MicroOp.STO, w=IW.W64, src=Reg.AL, imm=2),
            MicroInstruction(op=MicroOp.LD, dst=Reg.BL, imm=1),
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.STO, src=Reg.AL, imm=4),
            MicroInstruction(op=MicroOp.LD, dst=Reg.AL, imm=3),
            MicroInstruction(op=MicroOp.LD, dst=Reg.BL, imm=0),
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.LD, dst=Reg.BL, imm=4),
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.STO, src=Reg.AL, imm=4),
            MicroInstruction(op=MicroOp.LD, dst=Reg.AL, imm=2),
            MicroInstruction(op=MicroOp.LD, dst=Reg.BL, imm=0),
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.LD, dst=Reg.BL, imm=4),
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # DIV_I32:
        # 0: POP BL (divisor b)
        # 1: JNZ UNDERFLOW -> 7 (HALT)
        # 2: POP AL (dividend a)
        # 3: JNZ UNDERFLOW -> 7 (HALT)
        # 4: DIV AL, BL
        # 5: JNZ ERR -> 7 (HALT - don't push quotient if divide-by-zero error)
        # 6: PUSH AL
        # 7: HALT
        UserOpcode.DIV_I32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=7),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=7),
            MicroInstruction(op=MicroOp.DIV, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, imm=7),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # CHS_I32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 5 (HALT)
        # 2: SUB AL, AL
        # 3: SUB AL, BL
        # 4: PUSH AL
        # 5: HALT
        UserOpcode.CHS_I32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=5),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # CHS_I64:
        # 0: POP W64 BL
        # 1: JNZ UNDERFLOW -> 5 (HALT)
        # 2: SUB W64 AL, AL
        # 3: SUB W64 AL, BL
        # 4: PUSH W64 AL
        # 5: HALT
        UserOpcode.CHS_I64: [
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=5),
            MicroInstruction(op=MicroOp.SUB, w=IW.W64, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.SUB, w=IW.W64, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # CHS_F32:
        # 0: POP AL
        # 1: JNZ UNDERFLOW -> 4 (HALT)
        # 2: FCHS AL
        # 3: PUSH AL
        # 4: HALT
        UserOpcode.CHS_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=4),
            MicroInstruction(op=MicroOp.FCHS, dst=Reg.AL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # CHS_F64:
        # 0: POP W64 AL
        # 1: JNZ UNDERFLOW -> 4 (HALT)
        # 2: FCHS W64 AL
        # 3: PUSH W64 AL
        # 4: HALT
        UserOpcode.CHS_F64: [
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=4),
            MicroInstruction(op=MicroOp.FCHS, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # ABS_I32:
        # 0: POP AL
        # 1: JNZ UNDERFLOW -> 8 (HALT)
        # 2: OR AL, AL
        # 3: JZ SIGN -> 7 (skip negate to PUSH AL)
        # 4: MOV BL, AL
        # 5: SUB AL, AL
        # 6: SUB AL, BL
        # 7: PUSH AL
        # 8: HALT
        UserOpcode.ABS_I32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=8),
            MicroInstruction(op=MicroOp.OR, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.SIGN, imm=7),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AL),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # ABS_I64:
        # 0: POP W64 AL
        # 1: JNZ UNDERFLOW -> 8 (HALT)
        # 2: OR W64 AL, AL
        # 3: JZ SIGN -> 7 (skip negate to PUSH W64 AL)
        # 4: MOV W64 BL, AL
        # 5: SUB W64 AL, AL
        # 6: SUB W64 AL, BL
        # 7: PUSH W64 AL
        # 8: HALT
        UserOpcode.ABS_I64: [
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=8),
            MicroInstruction(op=MicroOp.OR, w=IW.W64, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.SIGN, imm=7),
            MicroInstruction(op=MicroOp.MOV, w=IW.W64, dst=Reg.BL, src=Reg.AL),
            MicroInstruction(op=MicroOp.SUB, w=IW.W64, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.SUB, w=IW.W64, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # ABS_F32:
        # 0: POP AL
        # 1: JNZ UNDERFLOW -> 4 (HALT)
        # 2: FABS AL
        # 3: PUSH AL
        # 4: HALT
        UserOpcode.ABS_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=4),
            MicroInstruction(op=MicroOp.FABS, dst=Reg.AL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # ABS_F64:
        # 0: POP W64 AL
        # 1: JNZ UNDERFLOW -> 4 (HALT)
        # 2: FABS W64 AL
        # 3: PUSH W64 AL
        # 4: HALT
        UserOpcode.ABS_F64: [
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=4),
            MicroInstruction(op=MicroOp.FABS, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # DUP4:
        # 0: POP AL
        # 1: JNZ UNDERFLOW -> 4 (HALT)
        # 2: PUSH AL
        # 3: PUSH AL
        # 4: HALT
        UserOpcode.DUP4: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=4),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # DUP8:
        # 0: POP W64 AL
        # 1: JNZ UNDERFLOW -> 4 (HALT)
        # 2: PUSH W64 AL
        # 3: PUSH W64 AL
        # 4: HALT
        UserOpcode.DUP8: [
            MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=4),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
    }

    # Populate CP_MEM0_TOS..CP_MEM15_TOS (0xD0..0xDF) and CP_TOS_MEM0..CP_TOS_MEM15 (0xE0..0xEF)
    for _slot in range(16):
        _ucode[UserOpcode(0xD0 + _slot)] = [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=3),
            MicroInstruction(op=MicroOp.STO, src=Reg.AL, imm=_slot),
            MicroInstruction(op=MicroOp.HALT),
        ]
        _ucode[UserOpcode(0xE0 + _slot)] = [
            MicroInstruction(op=MicroOp.LD, dst=Reg.AL, imm=_slot),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ]

    # ZERO_MEM (0xF0): Clear all 16 user storage memory slots to zero (17 cycles)
    _ucode[UserOpcode.ZERO_MEM] = [
        MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL),
        *[MicroInstruction(op=MicroOp.STO, src=Reg.AL, imm=_slot) for _slot in range(16)],
        MicroInstruction(op=MicroOp.HALT),
    ]


    @classmethod
    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 5 & 6, 512x32) for runtime microcode execution store",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_microcode_rom",
    )
    def get(cls, opcode: UserOpcode) -> List[MicroInstruction]:
        if opcode not in cls._ucode:
            raise NotImplementedError(f"Microcode for opcode {opcode} not implemented")
        return cls._ucode[opcode]

    @classmethod
    def total_instructions(cls) -> int:
        """Returns the total number of micro-instructions across all defined opcodes."""
        return sum(len(seq) for seq in cls._ucode.values())

    @classmethod
    def remaining_capacity(cls) -> int:
        """Returns the remaining micro-instruction slots available in the 512-word EBR store."""
        return cls.MAX_MICRO_INSTRUCTIONS - cls.total_instructions()

    @classmethod
    def instruction_count(cls, opcode: UserOpcode) -> int:
        """Returns the number of micro-instructions in a given user opcode's sequence."""
        return len(cls.get(opcode))

    @classmethod
    def validate_budget(cls) -> None:
        """Validates that total micro-instructions do not exceed the 512 EBR limit."""
        total = cls.total_instructions()
        if total > cls.MAX_MICRO_INSTRUCTIONS:
            raise ValueError(
                f"Total microcode instructions ({total}) exceeds EBR capacity limit of {cls.MAX_MICRO_INSTRUCTIONS}"
            )


# Enforce budget compliance at module import time
MicroCode.validate_budget()

