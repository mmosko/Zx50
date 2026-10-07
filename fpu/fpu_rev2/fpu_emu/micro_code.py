"""Microcode ROM mapping UserOpcode to micro-instruction sequences."""

from typing import Dict, List
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.registers import Reg, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.rom.fpu_const_map import FpuCheb, FpuConst, FpuTable
from fpu_emu.ucode import fpu_symbols, fpu_ucode
from fpu_emu.user_opcodes import UserOpcode


class MicroCode:
    """Microcode ROM lookup table."""

    # 512 is the true maximum, but we do not have an optimized assembly yet, so we have a relaxed max
    HARD_MAX_MICRO_INSTRUCTIONS: int = 1024
    SOFT_MAX_MICRO_INSTRUCTIONS: int = 512
    MAX_MICRO_INSTRUCTIONS: int = HARD_MAX_MICRO_INSTRUCTIONS

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
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src1=Reg.AL, src=Reg.BL),
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
        # MUL_F32:
        # 0: POP BL (pop operand B)
        # 1: JNZ UNDERFLOW -> 26 (TRAP)
        # 2: POP AL (pop operand A)
        # 3: JNZ UNDERFLOW -> 26 (TRAP)
        # 4: MOV BH, AL (stash A into BH)
        # 5: XOR BH, BL (BH[31] = s_A ^ s_B, preserved across MULU and shifts)
        # 6: UNPACK BL, EB (unpack B: EB <- exp_B, BL <- mant_B)
        # 7: JZ ZERO -> 24 (RETURN_ZERO)
        # 8: UNPACK AL, EA (unpack A: EA <- exp_A, AL <- mant_A)
        # 9: JZ ZERO -> 24 (RETURN_ZERO)
        # 10: EXP_ADD EA, EB (EA <- EA + EB)
        # 11: EXP_SUB EA, IMM=127 (EA <- EA - 127)
        # 12: MULU AL, BL ({AH, AL} <- AL * BL unsigned 48-bit product)
        # 13: LSR W64 AL, IMM=23 ({AH, AL} >>= 23, mantissa in AL[24:0])
        # 14: LZC AL (C <- leading zero count of AL)
        # 15: CMP C, IMM=8 (compare C with 8: 7 if bit 24 set, 8 if bit 23 set)
        # 16: JNZ CARRY -> 18 (OVERFLOW_RIGHT: C < 8)
        # 17: JMP 20 (DONE_NORM)
        # 18: LSR AL, IMM=1 (AL >>= 1)
        # 19: EXP_ADD EA, IMM=1 (EA += 1)
        # 20: OR BH, BH (restores status.sign from BH[31])
        # 21: PACK AL, EA (packs float32 into AL)
        # 22: PUSH AL
        # 23: HALT
        # 24: SUB AL, AL (RETURN_ZERO: AL <- 0)
        # 25: JMP 20 (DONE_NORM -> OR BH, BH -> PACK -> PUSH -> HALT)
        # 26: HALT (TRAP)
        UserOpcode.MUL_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=26),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=26),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BH, src=Reg.AL),
            MicroInstruction(op=MicroOp.XOR, dst=Reg.BH, src=Reg.BL),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EB, src=Reg.BL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=24),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EA, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=24),
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.IMM, imm=127),
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.LSR, w=IW.W64, dst=Reg.AL, src=Reg.IMM, imm=23),
            MicroInstruction(op=MicroOp.LZC, dst=Reg.C, src=Reg.AL),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.C, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=18),
            MicroInstruction(op=MicroOp.JMP, imm=20),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AL, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.OR, dst=Reg.BH, src=Reg.BH),
            MicroInstruction(op=MicroOp.PACK, dst=Reg.AL, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.JMP, imm=20),
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
        # DIV_F32:
        # 0: POP BL (divisor b)
        # 1: JNZ UNDERFLOW -> 36 (TRAP)
        # 2: POP AL (dividend a)
        # 3: JNZ UNDERFLOW -> 36 (TRAP)
        # 4: MOV BH, AL
        # 5: XOR BH, BL (BH[31] = s_A ^ s_B)
        # 6: UNPACK BL, EB (unpack divisor B: EB <- exp_B, BL <- mant_B)
        # 7: JZ ZERO -> 33 (DIV_BY_ZERO)
        # 8: UNPACK AL, EA (unpack dividend A: EA <- exp_A, AL <- mant_A)
        # 9: JZ ZERO -> 31 (RETURN_ZERO)
        # 10: EXP_SUB EA, EB (EA <- EA - EB)
        # 11: EXP_ADD EA, IMM=127 (EA <- EA + 127)
        # 12: LSL AL, IMM=8 (AL <- AL << 8)
        # 13: DIVU AL, BL (AL <- q0, DL <- r0)
        # 14: MOV AH, AL (AH <- q0)
        # 15: MOV AL, DL (AL <- r0)
        # 16: LSL AL, IMM=8 (AL <- r0 << 8)
        # 17: DIVU AL, BL (AL <- q1, DL <- r1)
        # 18: LSL AH, IMM=8 (AH <- q0 << 8)
        # 19: OR AH, AL (AH <- (q0 << 8) | q1)
        # 20: MOV AL, DL (AL <- r1)
        # 21: LSL AL, IMM=8 (AL <- r1 << 8)
        # 22: DIVU AL, BL (AL <- q2, DL <- r2)
        # 23: LSL AH, IMM=8 (AH <- (q0 << 16) | (q1 << 8))
        # 24: OR AH, AL (AH <- (q0 << 16) | (q1 << 8) | q2)
        # 25: MOV AL, AH (AL <- Q_24)
        # 26: LZC AL (C <- leading zero count)
        # 27: CMP C, IMM=8 (compare C with 8)
        # 28: JNZ CARRY -> 37 (SHIFT_RIGHT: C < 8, bit 24 is 1)
        # 29: EXP_SUB EA, IMM=1 (bit 24 is 0, normalize exponent: EA -= 1)
        # 30: JMP 38 (DONE_NORM)
        # 31: SUB AL, AL (RETURN_ZERO: AL <- 0)
        # 32: JMP 38 (DONE_NORM)
        # 33: SUB BL, BL (DIV_BY_ZERO: BL <- 0)
        # 34: DIVU AL, BL (trigger divide-by-zero error)
        # 35: HALT
        # 36: HALT (TRAP)
        # 37: LSR AL, IMM=1 (SHIFT_RIGHT: AL >>= 1, falls through to 38)
        # 38: OR BH, BH (DONE_NORM: restore sign bit)
        # 39: PACK AL, EA (pack float32)
        # 40: PUSH AL
        # 41: HALT
        UserOpcode.DIV_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=36),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=36),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BH, src=Reg.AL),
            MicroInstruction(op=MicroOp.XOR, dst=Reg.BH, src=Reg.BL),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EB, src=Reg.BL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=33),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EA, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=31),
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.IMM, imm=127),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AH, src=Reg.AL),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.DL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AL),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.DL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AL),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),
            MicroInstruction(op=MicroOp.LZC, dst=Reg.C, src=Reg.AL),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.C, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=37),
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.JMP, imm=38),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL),
            MicroInstruction(op=MicroOp.JMP, imm=38),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.BL, src=Reg.BL),
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AL, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.OR, dst=Reg.BH, src=Reg.BH),
            MicroInstruction(op=MicroOp.PACK, dst=Reg.AL, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        # SQRT_F32:
        #  0: POP AL                      # Pop input float32 X into AL
        #  1: JNZ UNDERFLOW -> 54         # Underflow trap
        #  2: MOV BH, AL                  # Save raw input in BH (for zero/NaN preservation)
        #  3: UNPACK EA, AL               # AL <- mantissa (bit 23 set), EA <- biased exponent
        #  4: JZ ZERO -> 55               # If X == 0: push original input (BH) and return
        #  5: JNZ SIGN -> 57              # If X < 0: domain error (assert ERR and abort)
        #  6: MOV BL, EA                  # BL <- biased exponent
        #  7: CMP BL, IMM=255             # Check for Inf / NaN
        #  8: JZ ZERO -> 55               # If Inf or NaN: push original input (BH) and return
        #  9: AND BL, IMM=1               # Check exponent parity (BL & 1)
        # 10: JZ ZERO -> 18               # If even exponent: jump to EVEN_EXP (line 18)
        # --- ODD_EXP (E unbiased is even: e = 2k => E is odd) ---
        # 11: MOV DL, AL                  # DL <- mantissa (Q0.24)
        # 12: LSL DL, IMM=7               # DL <- S in Q2.30 (range [1.0, 2.0))
        # 13: MOV BL, AL                  # BL <- mantissa
        # 14: LSR BL, IMM=16              # Shift out low bits
        # 15: AND BL, IMM=0x7F            # BL <- fraction index bits [22:16], bit 7 = 0
        # 16: EXP_ADD EA, IMM=127         # EA <- (E + 127)
        # 17: JMP 25                      # Jump to REJOIN
        # --- EVEN_EXP (E unbiased is odd: e = 2k+1 => E is even) ---
        # 18: MOV DL, AL                  # DL <- mantissa (Q0.24)
        # 19: LSL DL, IMM=8               # DL <- 2*M = S in Q2.30 (range [2.0, 4.0))
        # 20: MOV BL, AL                  # BL <- mantissa
        # 21: LSR BL, IMM=16              # Shift out low bits
        # 22: AND BL, IMM=0x7F            # Fraction index bits [22:16]
        # 23: OR BL, IMM=0x80             # Set bit 7 = 1 (selects table range [2.0, 4.0))
        # 24: EXP_ADD EA, IMM=126         # EA <- (E + 126)
        # --- REJOIN (line 25) ---
        # 25: MOV FL, EA                  # FL <- EA
        # 26: LSR FL, IMM=1               # FL <- EA >> 1 (unbiased exponent divided by 2 + 127)
        # 27: MOV EA, FL                  # EA <- final biased exponent
        # 28: LDC AH, SQRT, BL            # AH <- 16-bit seed y0 from EBR 4 (SQRT table)
        # 29: LSL AH, IMM=16              # AH <- y0 in Q0.32
        # 30: MOV BL, AH                  # BL <- y0 (initial reciprocal square root seed)
        # 31: LDI DH, IMM=3               # Constant 3 in DH
        # 32: LSL DH, IMM=30              # DH <- 3.0 in Q2.30 (0xC0000000)
        # 33: LDI C, IMM=2                # Counter C <- 2 iterations of Newton-Raphson
        # --- LOOP_NR (line 34..46) ---
        # 34: MOV AL, BL                  # AL <- y
        # 35: MULU AL, BL                 # {AH, AL} <- y^2 (high 32 bits in AH is Q2.30)
        # 36: MOV AL, AH                  # AL <- y^2
        # 37: MULU AL, DL                 # {AH, AL} <- S * y^2 (high 32 bits in AH is Q2.30)
        # 38: MOV BH, DH                  # BH <- 3.0 (from DH)
        # 39: SUB BH, AH                  # BH <- 3.0 - S * y^2 (valid on ha_mux!)
        # 40: MOV AL, BL                  # AL <- y
        # 41: MULU AL, BH                 # {AH, AL} <- y * (3.0 - S * y^2) (Q2.62)
        # 42: LSL AH, IMM=1               # High word shift: AH << 1 (divide by 2 in Q0.32)
        # 43: LSR AL, IMM=31              # Carry bit from AL: AL >> 31
        # 44: OR AH, AL                   # AH <- (AH << 1) | (AL >> 31)
        # 45: MOV BL, AH                  # BL <- updated y
        # 46: DJNZ 34                     # Loop 2 iterations
        # --- RESULT FORMATION (line 47..53) ---
        # 47: MOV AL, BL                  # AL <- final reciprocal square root y
        # 48: MULU AL, DL                 # {AH, AL} <- S * y = sqrt(S) in Q2.30
        # 49: ADD AH, IMM=0x40            # Half-ULP rounding bias
        # 50: LSR AH, IMM=7               # Align mantissa: bit 23 implicit 1 is at bit 23
        # 51: PACK AH, EA                 # Pack float32: mantissa AH, exponent EA, sign=0
        # 52: PUSH AH                     # Push result to stack
        # 53: HALT                        # Done
        # --- SPECIAL & ERROR HANDLERS (line 54..58) ---
        # 54: HALT                        # Stack underflow trap
        # 55: PUSH BH                     # RET_INPUT: push original input (for 0.0, -0.0, +Inf, NaN)
        # 56: HALT
        # 57: LDI Reg.NONE, IMM=1, ERR    # DOMAIN_ERR: assert ERR flag (X < 0)
        # 58: HALT
        UserOpcode.SQRT_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=54),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BH, src=Reg.AL),
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EA, src=Reg.AL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=55),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.SIGN, imm=57),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.EA),
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=255),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=55),
            MicroInstruction(op=MicroOp.AND, dst=Reg.BL, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=18),
            # ODD_EXP (11..17)
            MicroInstruction(op=MicroOp.MOV, dst=Reg.DL, src=Reg.AL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.DL, src=Reg.IMM, imm=7),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AL),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.BL, src=Reg.IMM, imm=16),
            MicroInstruction(op=MicroOp.AND, dst=Reg.BL, src=Reg.IMM, imm=0x7F),
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.IMM, imm=127),
            MicroInstruction(op=MicroOp.JMP, imm=25),
            # EVEN_EXP (18..24)
            MicroInstruction(op=MicroOp.MOV, dst=Reg.DL, src=Reg.AL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.DL, src=Reg.IMM, imm=8),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AL),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.BL, src=Reg.IMM, imm=16),
            MicroInstruction(op=MicroOp.AND, dst=Reg.BL, src=Reg.IMM, imm=0x7F),
            MicroInstruction(op=MicroOp.OR, dst=Reg.BL, src=Reg.IMM, imm=0x80),
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.IMM, imm=126),
            # REJOIN (25..33)
            MicroInstruction(op=MicroOp.MOV, dst=Reg.FL, src=Reg.EA),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.FL, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.EA, src=Reg.FL),
            MicroInstruction(op=MicroOp.LDC, dst=Reg.AH, src=FpuTable.SQRT, src1=Reg.BL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=16),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AH),
            MicroInstruction(op=MicroOp.LDI, dst=Reg.DH, src=Reg.IMM, imm=3),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.DH, src=Reg.IMM, imm=30),
            MicroInstruction(op=MicroOp.LDI, dst=Reg.C, src=Reg.IMM, imm=2),
            # LOOP_NR (34..46)
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.DL),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BH, src=Reg.DH),
            MicroInstruction(op=MicroOp.SUB, dst=Reg.BH, src=Reg.AH),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.BH),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AL, src=Reg.IMM, imm=31),
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AL),
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AH),
            MicroInstruction(op=MicroOp.DJNZ, imm=34),
            # RESULT (47..53)
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.DL),
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.IMM, imm=0x40),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AH, src=Reg.IMM, imm=7),
            MicroInstruction(op=MicroOp.PACK, dst=Reg.AH, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AH),
            MicroInstruction(op=MicroOp.HALT),
            # SPECIAL / ERROR (54..58)
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.BH),
            MicroInstruction(op=MicroOp.HALT),
            MicroInstruction(op=MicroOp.LDI, dst=Reg.NONE, src=Reg.IMM, flag=StatusFlag.ERR, imm=1),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.LOG2_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),  # 0: START
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=116),  # 1
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BH, src=Reg.AL),  # 2
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EA, src=Reg.AL),  # 3
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=114),  # 4
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.SIGN, imm=114),  # 5
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.EA),  # 6
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=255),  # 7
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=112),  # 8
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CONST, imm=FpuConst.ONE_F32),  # 9
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.BH, imm=0),  # 10
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=109),  # 11
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.SQRT2_MANT),  # 12
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.AL, imm=0),  # 13
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=16),  # 14
            MicroInstruction(op=MicroOp.JMP, imm=18),  # 15
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AL, src=Reg.IMM, imm=1),  # 16: REDUCE_M
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.IMM, imm=1),  # 17
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BH, src=Reg.IMM, imm=1),  # 18: PREPARE_DIV
            MicroInstruction(op=MicroOp.LSL, dst=Reg.BH, src=Reg.IMM, imm=23),  # 19
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AL),  # 20
            MicroInstruction(op=MicroOp.ADD, dst=Reg.BL, src=Reg.BH, imm=0),  # 21
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.BH, imm=0),  # 22
            MicroInstruction(op=MicroOp.LDI, dst=Reg.C, src=Reg.IMM, imm=0),  # 23
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.SIGN, imm=26),  # 24
            MicroInstruction(op=MicroOp.JMP, imm=29),  # 25
            MicroInstruction(op=MicroOp.LDI, dst=Reg.C, src=Reg.IMM, imm=1),  # 26: NEG_NUM
            MicroInstruction(op=MicroOp.NOT, dst=Reg.AL, src=Reg.AL),  # 27
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src=Reg.IMM, imm=1),  # 28
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=7),  # 29: DIV_START
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),  # 30
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AH, src=Reg.AL),  # 31
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.DL),  # 32
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=7),  # 33
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),  # 34
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=7),  # 35
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AL),  # 36
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.DL),  # 37
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=7),  # 38
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),  # 39
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=7),  # 40
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AL),  # 41
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.DL),  # 42
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=7),  # 43
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),  # 44
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=7),  # 45
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AL),  # 46
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.DL),  # 47
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=3),  # 48
            MicroInstruction(op=MicroOp.DIVU, dst=Reg.AL, src=Reg.BL),  # 49
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=3),  # 50
            MicroInstruction(op=MicroOp.OR, dst=Reg.AH, src=Reg.AL),  # 51
            MicroInstruction(op=MicroOp.MOV, dst=Reg.DH, src=Reg.AH),  # 52
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 53
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.AH),  # 54
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 55
            MicroInstruction(op=MicroOp.MOV, dst=Reg.DL, src=Reg.AH),  # 56
            MicroInstruction(op=MicroOp.LDC, dst=Reg.AL, src=FpuTable.CHEB, imm=FpuCheb.LOG2_C3),  # 57
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.DL),  # 58
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 59
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.LOG2_C2),  # 60
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 61
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 62
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.DL),  # 63
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 64
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.LOG2_C1),  # 65
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 66
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 67
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.DL),  # 68
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 69
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.LOG2_C0),  # 70
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 71
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 72
            MicroInstruction(op=MicroOp.MULU, dst=Reg.AL, src=Reg.DH),  # 73
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 74
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AH, src=Reg.IMM, imm=6),  # 75
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.C),  # 76
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=0),  # 77
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=81),  # 78
            MicroInstruction(op=MicroOp.NOT, dst=Reg.AH, src=Reg.AH),  # 79
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.IMM, imm=1),  # 80
            MicroInstruction(op=MicroOp.CMP, dst=Reg.EA, src=Reg.IMM, imm=127),  # 81: CHECK_EXP
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=98),  # 82
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=90),  # 83
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BH, src=Reg.IMM, imm=0),  # 84: EXP_POS
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.IMM, imm=127),  # 85
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.EA),  # 86
            MicroInstruction(op=MicroOp.LSL, dst=Reg.BL, src=Reg.IMM, imm=23),  # 87
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 88
            MicroInstruction(op=MicroOp.JMP, imm=117),  # 89
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BH, src=Reg.IMM, imm=1),  # 90: EXP_NEG
            MicroInstruction(op=MicroOp.LSL, dst=Reg.BH, src=Reg.IMM, imm=31),  # 91
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BL, src=Reg.IMM, imm=127),  # 92
            MicroInstruction(op=MicroOp.SUB, dst=Reg.BL, src=Reg.EA, imm=0),  # 93
            MicroInstruction(op=MicroOp.LSL, dst=Reg.BL, src=Reg.IMM, imm=23),  # 94
            MicroInstruction(op=MicroOp.SUB, dst=Reg.BL, src=Reg.AH, imm=0),  # 95
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AH, src=Reg.BL),  # 96
            MicroInstruction(op=MicroOp.JMP, imm=117),  # 97
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BH, src=Reg.IMM, imm=0),  # 98: EXP_ZERO
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AH),  # 99
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=0),  # 100
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=109),  # 101
            MicroInstruction(op=MicroOp.LSR, dst=Reg.BL, src=Reg.IMM, imm=31),  # 102
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=0),  # 103
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=117),  # 104
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BH, src=Reg.IMM, imm=1),  # 105
            MicroInstruction(op=MicroOp.LSL, dst=Reg.BH, src=Reg.IMM, imm=31),  # 106
            MicroInstruction(op=MicroOp.NOT, dst=Reg.AH, src=Reg.AH),  # 107
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.IMM, imm=1),  # 108
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL, imm=0),  # 109: RET_ZERO
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),  # 110
            MicroInstruction(op=MicroOp.HALT),  # 111
            MicroInstruction(op=MicroOp.PUSH, src=Reg.BH),  # 112: RET_INPUT
            MicroInstruction(op=MicroOp.HALT),  # 113
            MicroInstruction(op=MicroOp.LDI, dst=Reg.NONE, src=Reg.IMM, flag=StatusFlag.ERR, imm=1),  # 114: DOMAIN_ERR
            MicroInstruction(op=MicroOp.HALT),  # 115
            MicroInstruction(op=MicroOp.HALT),  # 116: TRAP_UNDERFLOW
            MicroInstruction(op=MicroOp.LZC, dst=Reg.BL, src=Reg.AH),  # 117: NORMALIZE
            MicroInstruction(op=MicroOp.LDI, dst=Reg.EA, src=Reg.IMM, imm=135),  # 118
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.BL, imm=0),  # 119
            MicroInstruction(op=MicroOp.LDI, dst=Reg.C, src=Reg.IMM, imm=8),  # 120
            MicroInstruction(op=MicroOp.SUB, dst=Reg.C, src=Reg.BL, imm=0),  # 121
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.SIGN, imm=125),  # 122
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AH, src=Reg.C, imm=0),  # 123
            MicroInstruction(op=MicroOp.JMP, imm=128),  # 124
            MicroInstruction(op=MicroOp.NOT, dst=Reg.C, src=Reg.C),  # 125: SHIFT_LEFT
            MicroInstruction(op=MicroOp.ADD, dst=Reg.C, src=Reg.IMM, imm=1),  # 126
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.C, imm=0),  # 127
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 128: DO_PACK
            MicroInstruction(op=MicroOp.OR, dst=Reg.BH, src=Reg.BH),  # 129
            MicroInstruction(op=MicroOp.PACK, dst=Reg.AL, src=Reg.EA),  # 130
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),  # 131
            MicroInstruction(op=MicroOp.HALT),  # 132
        ],
        UserOpcode.EXP2_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),  # 0: START
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=116),  # 1
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BH, src=Reg.AL),  # 2
            MicroInstruction(op=MicroOp.UNPACK, dst=Reg.EA, src=Reg.AL),  # 3
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=101),  # 4
            MicroInstruction(op=MicroOp.LDI, dst=Reg.C, src=Reg.IMM, imm=0),  # 5
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.SIGN, imm=8),  # 6
            MicroInstruction(op=MicroOp.JMP, imm=9),  # 7
            MicroInstruction(op=MicroOp.LDI, dst=Reg.C, src=Reg.IMM, imm=1),  # 8: SAVE_NEG
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.EA),  # 9: CHECK_SPECIAL
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=255),  # 10
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=114),  # 11
            MicroInstruction(op=MicroOp.CMP, dst=Reg.EA, src=Reg.IMM, imm=127),  # 12: CHECK_EXP
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=26),  # 13
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.IMM, imm=127),  # 14: EXP_GE
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.EA),  # 15
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=7),  # 16
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.CARRY, imm=23),  # 17
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=23),  # 18
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.C),  # 19
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=0),  # 20
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=107),  # 21
            MicroInstruction(op=MicroOp.JMP, imm=104),  # 22
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.EA),  # 23: IN_RANGE_GE
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.BL, imm=0),  # 24
            MicroInstruction(op=MicroOp.JMP, imm=29),  # 25
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BL, src=Reg.IMM, imm=127),  # 26: EXP_LESS
            MicroInstruction(op=MicroOp.SUB, dst=Reg.BL, src=Reg.EA, imm=0),  # 27
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AL, src=Reg.BL, imm=0),  # 28
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AL),  # 29: EXTRACT_K_R
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BH, src=Reg.IMM, imm=1),  # 30
            MicroInstruction(op=MicroOp.LSL, dst=Reg.BH, src=Reg.IMM, imm=22),  # 31
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src=Reg.BH, imm=0),  # 32
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AL, src=Reg.IMM, imm=23),  # 33
            MicroInstruction(op=MicroOp.MOV, dst=Reg.EA, src=Reg.AL),  # 34
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL, src=Reg.IMM, imm=23),  # 35
            MicroInstruction(op=MicroOp.SUB, dst=Reg.BL, src=Reg.AL, imm=0),  # 36
            MicroInstruction(op=MicroOp.LSL, dst=Reg.BL, src=Reg.IMM, imm=8),  # 37
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BH, src=Reg.C),  # 38
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BH, src=Reg.IMM, imm=0),  # 39
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=43),  # 40
            MicroInstruction(op=MicroOp.NOT, dst=Reg.BL, src=Reg.BL),  # 41
            MicroInstruction(op=MicroOp.ADD, dst=Reg.BL, src=Reg.IMM, imm=1),  # 42
            MicroInstruction(op=MicroOp.MOV, dst=Reg.DH, src=Reg.BL),  # 43: EVAL_POLY
            MicroInstruction(op=MicroOp.LDC, dst=Reg.AL, src=FpuTable.CHEB, imm=FpuCheb.EXP2_C6),  # 44
            MicroInstruction(op=MicroOp.MUL, dst=Reg.AL, src=Reg.DH),  # 45
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 46
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.EXP2_C5),  # 47
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 48
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 49
            MicroInstruction(op=MicroOp.MUL, dst=Reg.AL, src=Reg.DH),  # 50
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 51
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.EXP2_C4),  # 52
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 53
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 54
            MicroInstruction(op=MicroOp.MUL, dst=Reg.AL, src=Reg.DH),  # 55
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 56
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.EXP2_C3),  # 57
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 58
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 59
            MicroInstruction(op=MicroOp.MUL, dst=Reg.AL, src=Reg.DH),  # 60
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 61
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.EXP2_C2),  # 62
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 63
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 64
            MicroInstruction(op=MicroOp.MUL, dst=Reg.AL, src=Reg.DH),  # 65
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 66
            MicroInstruction(op=MicroOp.LDC, dst=Reg.BL, src=FpuTable.CHEB, imm=FpuCheb.EXP2_C1),  # 67
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 68
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 69
            MicroInstruction(op=MicroOp.MUL, dst=Reg.AL, src=Reg.DH),  # 70
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 71
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BL, src=Reg.IMM, imm=1),  # 72
            MicroInstruction(op=MicroOp.LSL, dst=Reg.BL, src=Reg.IMM, imm=31),  # 73
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AH, src=Reg.BL, imm=0),  # 74
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.AH),  # 75
            MicroInstruction(op=MicroOp.LSR, dst=Reg.BL, src=Reg.IMM, imm=31),  # 76
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=0),  # 77
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=82),  # 78
            MicroInstruction(op=MicroOp.LDI, dst=Reg.EB, src=Reg.IMM, imm=127),  # 79
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AH, src=Reg.IMM, imm=8),  # 80
            MicroInstruction(op=MicroOp.JMP, imm=85),  # 81
            MicroInstruction(op=MicroOp.LDI, dst=Reg.EB, src=Reg.IMM, imm=126),  # 82: MANT_LESS_ONE
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AH, src=Reg.IMM, imm=1),  # 83
            MicroInstruction(op=MicroOp.LSR, dst=Reg.AH, src=Reg.IMM, imm=8),  # 84
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.C),  # 85: CALC_FINAL_EXP
            MicroInstruction(op=MicroOp.CMP, dst=Reg.BL, src=Reg.IMM, imm=0),  # 86
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.ZERO, imm=92),  # 87
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.EA),  # 88
            MicroInstruction(op=MicroOp.MOV, dst=Reg.EA, src=Reg.EB),  # 89
            MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.EA, src=Reg.BL, imm=0),  # 90
            MicroInstruction(op=MicroOp.JMP, imm=95),  # 91
            MicroInstruction(op=MicroOp.MOV, dst=Reg.BL, src=Reg.EA),  # 92: POS_EXP_SUM
            MicroInstruction(op=MicroOp.MOV, dst=Reg.EA, src=Reg.EB),  # 93
            MicroInstruction(op=MicroOp.EXP_ADD, dst=Reg.EA, src=Reg.BL, imm=0),  # 94
            MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.AH),  # 95: DO_PACK
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BH, src=Reg.IMM, imm=0),  # 96
            MicroInstruction(op=MicroOp.OR, dst=Reg.BH, src=Reg.BH),  # 97
            MicroInstruction(op=MicroOp.PACK, dst=Reg.AL, src=Reg.EA),  # 98
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),  # 99
            MicroInstruction(op=MicroOp.HALT),  # 100
            MicroInstruction(op=MicroOp.LDC, dst=Reg.AL, src=FpuTable.CONST, imm=FpuConst.ONE_F32),  # 101: RET_ONE
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),  # 102
            MicroInstruction(op=MicroOp.HALT),  # 103
            MicroInstruction(op=MicroOp.SUB, dst=Reg.AL, src=Reg.AL, imm=0),  # 104: RET_ZERO
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),  # 105
            MicroInstruction(op=MicroOp.HALT),  # 106
            MicroInstruction(op=MicroOp.LDI, dst=Reg.EA, src=Reg.IMM, imm=255),  # 107: RET_INF
            MicroInstruction(op=MicroOp.LDI, dst=Reg.AL, src=Reg.IMM, imm=0),  # 108
            MicroInstruction(op=MicroOp.LDI, dst=Reg.BH, src=Reg.IMM, imm=0),  # 109
            MicroInstruction(op=MicroOp.OR, dst=Reg.BH, src=Reg.BH),  # 110
            MicroInstruction(op=MicroOp.PACK, dst=Reg.AL, src=Reg.EA),  # 111
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),  # 112
            MicroInstruction(op=MicroOp.HALT),  # 113
            MicroInstruction(op=MicroOp.PUSH, src=Reg.BH),  # 114: RET_INPUT
            MicroInstruction(op=MicroOp.HALT),  # 115
            MicroInstruction(op=MicroOp.HALT),  # 116: TRAP_UNDERFLOW
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
        # Mathematical Constants (0xA0..0xAF) - Using scratch register FL/FH
        UserOpcode.PUSH_PI_32: [
            MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.PI_F32),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_PI_64: [
            MicroInstruction(op=MicroOp.LDC, w=IW.W64, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.PI_F64),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_E_32: [
            MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.E_F32),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_E_64: [
            MicroInstruction(op=MicroOp.LDC, w=IW.W64, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.E_F64),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_LN2_32: [
            MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.LN2_F32),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_LN2_64: [
            MicroInstruction(op=MicroOp.LDC, w=IW.W64, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.LN2_F64),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_LOG2E_32: [
            MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.LOG2E_F32),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_LOG2E_64: [
            MicroInstruction(op=MicroOp.LDC, w=IW.W64, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.LOG2E_F64),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_LOG2_10_32: [
            MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.LOG2_10_F32),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_LOG2_10_64: [
            MicroInstruction(op=MicroOp.LDC, w=IW.W64, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.LOG2_10_F64),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_LOG10_2_32: [
            MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.LOG10_2_F32),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_LOG10_2_64: [
            MicroInstruction(op=MicroOp.LDC, w=IW.W64, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.LOG10_2_F64),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_SQRT2_32: [
            MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.SQRT2_F32),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_SQRT2_64: [
            MicroInstruction(op=MicroOp.LDC, w=IW.W64, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.SQRT2_F64),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_INV_SQRT2_32: [
            MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.INV_SQRT2_F32),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
            MicroInstruction(op=MicroOp.HALT),
        ],
        UserOpcode.PUSH_INV_SQRT2_64: [
            MicroInstruction(op=MicroOp.LDC, w=IW.W64, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.INV_SQRT2_F64),
            MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.FL),
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
    def get_address(cls, opcode: UserOpcode) -> int:
        """Returns the start UPC address for an opcode in the microcode ROM."""
        sym = f"USER_{opcode.name}"
        if sym in fpu_symbols:
            return fpu_symbols[sym]
        return 0

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
        sym = f"USER_{opcode.name}"
        if sym in fpu_symbols:
            return fpu_ucode
        if opcode not in cls._ucode:
            raise NotImplementedError(f"Microcode for opcode {opcode} not implemented")
        return cls._ucode[opcode]

    @classmethod
    def instruction_count(cls, opcode: UserOpcode) -> int:
        """Returns the number of micro-instructions in a given user opcode's sequence."""
        sym = f"USER_{opcode.name}"
        if sym in fpu_symbols:
            sorted_addrs = sorted(fpu_symbols.values())
            idx = sorted_addrs.index(fpu_symbols[sym])
            if idx + 1 < len(sorted_addrs):
                return sorted_addrs[idx + 1] - sorted_addrs[idx]
            return len(fpu_ucode) - sorted_addrs[idx]
        if opcode not in cls._ucode:
            raise NotImplementedError(f"Microcode for opcode {opcode} not implemented")
        return len(cls._ucode[opcode])

    @classmethod
    def total_instructions(cls) -> int:
        """Returns the total number of micro-instructions across all defined opcodes."""
        return sum(cls.instruction_count(op) for op in cls._ucode.keys())

    @classmethod
    def remaining_capacity(cls) -> int:
        """Returns the remaining micro-instruction slots available in the 512-word EBR store."""
        return cls.MAX_MICRO_INSTRUCTIONS - cls.total_instructions()

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

