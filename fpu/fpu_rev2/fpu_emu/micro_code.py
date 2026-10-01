"""Microcode ROM mapping UserOpcode to micro-instruction sequences."""

from typing import Dict, List
from fpu_emu.memory.registers import Reg, StatusFlag
from fpu_emu.micro_opcodes import MicroOp, MicroInstruction
from fpu_emu.user_opcodes import UserOpcode


class MicroCode:
    """Microcode ROM lookup table."""

    _ucode: Dict[UserOpcode, List[MicroInstruction]] = {
        # ADD_I32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 7 (TRAP)
        # 2: POP AL
        # 3: JNZ UNDERFLOW -> 7 (TRAP)
        # 4: ADD AL, BL
        # 5: PUSH AL
        # 6: RET
        # 7: TRAP
        UserOpcode.ADD_I32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.ADD, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # ADD_F32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 25 (TRAP)
        # 2: POP AL
        # 3: JNZ UNDERFLOW -> 25 (TRAP)
        # 4: UNPACK_F32 EB, BL
        # 5: UNPACK_F32 EA, AL
        # 6: EXP_DIFF
        # 7: JZ CARRY -> 10
        # 8: SWAP AL, BL
        # 9: SWAP EA, EB
        # 10: LSR BL
        # 11: JZ DIFF_SIGN -> 18
        # 12: SUB AL, BL
        # 13: JNZ ZERO -> 22
        # 14: LZC AL
        # 15: LSL AL
        # 16: EXP_NORM
        # 17: JMP -> 22
        # 18: ADD AL, BL
        # 19: JZ CARRY -> 22
        # 20: RRC AL
        # 21: EXP_INC
        # 22: PACK_F32 AL, EA
        # 23: PUSH AL
        # 24: RET
        # 25: TRAP
        UserOpcode.ADD_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=25),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=25),
            MicroInstruction(op=MicroOp.UNPACK_F32, dst=Reg.EB, src=Reg.BL),
            MicroInstruction(op=MicroOp.UNPACK_F32, dst=Reg.EA, src=Reg.AL),
            MicroInstruction(op=MicroOp.EXP_DIFF),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.CARRY, target=10),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.DIFF_SIGN, target=18),
            # Effective Subtraction:
            MicroInstruction(op=MicroOp.SUB, src=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, target=22),
            MicroInstruction(op=MicroOp.LZC, src=Reg.AL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL),
            MicroInstruction(op=MicroOp.EXP_NORM),
            MicroInstruction(op=MicroOp.JMP, target=22),
            # Effective Addition:
            MicroInstruction(op=MicroOp.ADD, src=Reg.BL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.CARRY, target=22),
            MicroInstruction(op=MicroOp.RRC, dst=Reg.AL),
            MicroInstruction(op=MicroOp.EXP_INC),
            # Pack & Return:
            MicroInstruction(op=MicroOp.PACK_F32, dst=Reg.AL, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # ADD_I64:
        # 0: POP64 BX
        # 1: JNZ UNDERFLOW -> 7 (TRAP)
        # 2: POP64 AX
        # 3: JNZ UNDERFLOW -> 7 (TRAP)
        # 4: ADD64 AX, BX
        # 5: PUSH64 AX
        # 6: RET
        # 7: TRAP
        UserOpcode.ADD_I64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.ADD64, src=Reg.BX),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # ADD_F64:
        # 0: POP64 BX
        # 1: JNZ UNDERFLOW -> 25 (TRAP)
        # 2: POP64 AX
        # 3: JNZ UNDERFLOW -> 25 (TRAP)
        # 4: UNPACK_F64 EB, BX
        # 5: UNPACK_F64 EA, AX
        # 6: EXP_DIFF AX
        # 7: JZ CARRY -> 10
        # 8: SWAP AX, BX
        # 9: SWAP EA, EB
        # 10: LSR64 BX
        # 11: JZ DIFF_SIGN -> 18
        # 12: SUB64 BX
        # 13: JNZ ZERO -> 22
        # 14: LZC64 AX
        # 15: LSL64 AX
        # 16: EXP_NORM
        # 17: JMP -> 22
        # 18: ADD64 BX
        # 19: JZ CARRY -> 22
        # 20: RRC64 AX
        # 21: EXP_INC
        # 22: PACK_F64 AX, EA
        # 23: PUSH64 AX
        # 24: RET
        # 25: TRAP
        UserOpcode.ADD_F64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=25),
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=25),
            MicroInstruction(op=MicroOp.UNPACK_F64, dst=Reg.EB, src=Reg.BX),
            MicroInstruction(op=MicroOp.UNPACK_F64, dst=Reg.EA, src=Reg.AX),
            MicroInstruction(op=MicroOp.EXP_DIFF, src=Reg.AX),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.CARRY, target=10),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.AX, src=Reg.BX),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.LSR64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.DIFF_SIGN, target=18),
            # Effective Subtraction:
            MicroInstruction(op=MicroOp.SUB64, src=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, target=22),
            MicroInstruction(op=MicroOp.LZC64, src=Reg.AX),
            MicroInstruction(op=MicroOp.LSL64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.EXP_NORM),
            MicroInstruction(op=MicroOp.JMP, target=22),
            # Effective Addition:
            MicroInstruction(op=MicroOp.ADD64, src=Reg.BX),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.CARRY, target=22),
            MicroInstruction(op=MicroOp.RRC64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.EXP_INC),
            # Pack & Return:
            MicroInstruction(op=MicroOp.PACK_F64, dst=Reg.AX, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # SUB_I32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 7 (TRAP)
        # 2: POP AL
        # 3: JNZ UNDERFLOW -> 7 (TRAP)
        # 4: SUB AL, BL
        # 5: PUSH AL
        # 6: RET
        # 7: TRAP
        UserOpcode.SUB_I32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.SUB, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # SUB_F32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 26 (TRAP)
        # 2: CHS BL
        # 3: POP AL
        # 4: JNZ UNDERFLOW -> 26 (TRAP)
        # 5: UNPACK_F32 EB, BL
        # 6: UNPACK_F32 EA, AL
        # 7: EXP_DIFF
        # 8: JZ CARRY -> 11
        # 9: SWAP AL, BL
        # 10: SWAP EA, EB
        # 11: LSR BL
        # 12: JZ DIFF_SIGN -> 19
        # 13: SUB AL, BL
        # 14: JNZ ZERO -> 23
        # 15: LZC AL
        # 16: LSL AL
        # 17: EXP_NORM
        # 18: JMP -> 23
        # 19: ADD AL, BL
        # 20: JZ CARRY -> 23
        # 21: RRC AL
        # 22: EXP_INC
        # 23: PACK_F32 AL, EA
        # 24: PUSH AL
        # 25: RET
        # 26: TRAP
        UserOpcode.SUB_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=26),
            MicroInstruction(op=MicroOp.CHS, dst=Reg.BL),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=26),
            MicroInstruction(op=MicroOp.UNPACK_F32, dst=Reg.EB, src=Reg.BL),
            MicroInstruction(op=MicroOp.UNPACK_F32, dst=Reg.EA, src=Reg.AL),
            MicroInstruction(op=MicroOp.EXP_DIFF),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.CARRY, target=11),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.LSR, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.DIFF_SIGN, target=19),
            # Effective Subtraction:
            MicroInstruction(op=MicroOp.SUB, src=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, target=23),
            MicroInstruction(op=MicroOp.LZC, src=Reg.AL),
            MicroInstruction(op=MicroOp.LSL, dst=Reg.AL),
            MicroInstruction(op=MicroOp.EXP_NORM),
            MicroInstruction(op=MicroOp.JMP, target=23),
            # Effective Addition:
            MicroInstruction(op=MicroOp.ADD, src=Reg.BL),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.CARRY, target=23),
            MicroInstruction(op=MicroOp.RRC, dst=Reg.AL),
            MicroInstruction(op=MicroOp.EXP_INC),
            # Pack & Return:
            MicroInstruction(op=MicroOp.PACK_F32, dst=Reg.AL, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # SUB_I64:
        # 0: POP64 BX
        # 1: JNZ UNDERFLOW -> 7 (TRAP)
        # 2: POP64 AX
        # 3: JNZ UNDERFLOW -> 7 (TRAP)
        # 4: SUB64 AX, BX
        # 5: PUSH64 AX
        # 6: RET
        # 7: TRAP
        UserOpcode.SUB_I64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.SUB64, src=Reg.BX),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # SUB_F64:
        # 0: POP64 BX
        # 1: JNZ UNDERFLOW -> 26 (TRAP)
        # 2: CHS BX
        # 3: POP64 AX
        # 4: JNZ UNDERFLOW -> 26 (TRAP)
        # 5: UNPACK_F64 EB, BX
        # 6: UNPACK_F64 EA, AX
        # 7: EXP_DIFF AX
        # 8: JZ CARRY -> 11
        # 9: SWAP AX, BX
        # 10: SWAP EA, EB
        # 11: LSR64 BX
        # 12: JZ DIFF_SIGN -> 19
        # 13: SUB64 BX
        # 14: JNZ ZERO -> 23
        # 15: LZC64 AX
        # 16: LSL64 AX
        # 17: EXP_NORM
        # 18: JMP -> 23
        # 19: ADD64 BX
        # 20: JZ CARRY -> 23
        # 21: RRC64 AX
        # 22: EXP_INC
        # 23: PACK_F64 AX, EA
        # 24: PUSH64 AX
        # 25: RET
        # 26: TRAP
        UserOpcode.SUB_F64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=26),
            MicroInstruction(op=MicroOp.CHS, dst=Reg.BX),
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=26),
            MicroInstruction(op=MicroOp.UNPACK_F64, dst=Reg.EB, src=Reg.BX),
            MicroInstruction(op=MicroOp.UNPACK_F64, dst=Reg.EA, src=Reg.AX),
            MicroInstruction(op=MicroOp.EXP_DIFF, src=Reg.AX),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.CARRY, target=11),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.AX, src=Reg.BX),
            MicroInstruction(op=MicroOp.SWAP, dst=Reg.EA, src=Reg.EB),
            MicroInstruction(op=MicroOp.LSR64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.DIFF_SIGN, target=19),
            # Effective Subtraction:
            MicroInstruction(op=MicroOp.SUB64, src=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, target=23),
            MicroInstruction(op=MicroOp.LZC64, src=Reg.AX),
            MicroInstruction(op=MicroOp.LSL64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.EXP_NORM),
            MicroInstruction(op=MicroOp.JMP, target=23),
            # Effective Addition:
            MicroInstruction(op=MicroOp.ADD64, src=Reg.BX),
            MicroInstruction(op=MicroOp.JZ, flag=StatusFlag.CARRY, target=23),
            MicroInstruction(op=MicroOp.RRC64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.EXP_INC),
            # Pack & Return:
            MicroInstruction(op=MicroOp.PACK_F64, dst=Reg.AX, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # MUL_I32:
        # 0: POP BL
        # 1: JNZ UNDERFLOW -> 7 (TRAP)
        # 2: POP AL
        # 3: JNZ UNDERFLOW -> 7 (TRAP)
        # 4: MUL AL, BL
        # 5: PUSH AL
        # 6: RET
        # 7: TRAP
        UserOpcode.MUL_I32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.MUL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # MUL_I64:
        # 0: POP64 BX
        # 1: JNZ UNDERFLOW -> 7 (TRAP)
        # 2: POP64 AX
        # 3: JNZ UNDERFLOW -> 7 (TRAP)
        # 4: MUL64 AX, BX
        # 5: PUSH64 AX
        # 6: RET
        # 7: TRAP
        UserOpcode.MUL_I64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.MUL64, src=Reg.BX),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # SQRT_F32:
        # 0: POP AL
        # 1: JNZ UNDERFLOW -> 11 (TRAP)
        # 2: UNPACK_F32 EA, AL
        # 3: JNZ ZERO -> 8 (Return 0.0 directly)
        # 4: JNZ SIGN -> 11 (Domain error: sqrt of negative number)
        # 5: SQRT_EXP EA
        # 6: SQRT_CORE AL
        # 7: PACK_F32 AL, EA
        # 8: PUSH AL
        # 9: RET
        # 10: NOP
        # 11: TRAP
        UserOpcode.SQRT_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=11),
            MicroInstruction(op=MicroOp.UNPACK_F32, dst=Reg.EA, src=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, target=8),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.SIGN, target=11),
            MicroInstruction(op=MicroOp.SQRT_EXP, dst=Reg.EA),
            MicroInstruction(op=MicroOp.SQRT_CORE, dst=Reg.AL),
            MicroInstruction(op=MicroOp.PACK_F32, dst=Reg.AL, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.NOP),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # SQRT_F64:
        # 0: POP64 AX
        # 1: JNZ UNDERFLOW -> 11 (TRAP)
        # 2: UNPACK_F64 EA, AX
        # 3: JNZ ZERO -> 8 (Return 0.0 directly)
        # 4: JNZ SIGN -> 11 (Domain error: sqrt of negative number)
        # 5: SQRT_EXP64 EA
        # 6: SQRT_CORE64 AX
        # 7: PACK_F64 AX, EA
        # 8: PUSH64 AX
        # 9: RET
        # 10: NOP
        # 11: TRAP
        UserOpcode.SQRT_F64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=11),
            MicroInstruction(op=MicroOp.UNPACK_F64, dst=Reg.EA, src=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ZERO, target=8),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.SIGN, target=11),
            MicroInstruction(op=MicroOp.SQRT_EXP64, dst=Reg.EA),
            MicroInstruction(op=MicroOp.SQRT_CORE64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.PACK_F64, dst=Reg.AX, src=Reg.EA),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.NOP),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # ABS_I32:
        UserOpcode.ABS_I32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=5),
            MicroInstruction(op=MicroOp.ABS_INT, dst=Reg.AL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # ABS_I64:
        UserOpcode.ABS_I64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=5),
            MicroInstruction(op=MicroOp.ABS_INT64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # DUP4:
        UserOpcode.DUP4: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=6),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.OVERFLOW, target=6),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # DUP8:
        UserOpcode.DUP8: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=6),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.OVERFLOW, target=6),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # MUL_F32:
        UserOpcode.MUL_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.MUL_F32, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # DIV_F32:
        UserOpcode.DIV_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=8),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=8),
            MicroInstruction(op=MicroOp.DIV_F32, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=8),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # MUL_F64:
        UserOpcode.MUL_F64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=7),
            MicroInstruction(op=MicroOp.MUL_F64, dst=Reg.AX, src=Reg.BX),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # DIV_F64:
        UserOpcode.DIV_F64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=8),
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=8),
            MicroInstruction(op=MicroOp.DIV_F64, dst=Reg.AX, src=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=8),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # LN_F32:
        UserOpcode.LN_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=6),
            MicroInstruction(op=MicroOp.LN_F32),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=6),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # LN_F64:
        UserOpcode.LN_F64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=6),
            MicroInstruction(op=MicroOp.LN_F64),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=6),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # EXP_F32:
        UserOpcode.EXP_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=6),
            MicroInstruction(op=MicroOp.EXP_F32),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=6),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # EXP_F64:
        UserOpcode.EXP_F64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=6),
            MicroInstruction(op=MicroOp.EXP_F64),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=6),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # POW_F32:
        UserOpcode.POW_F32: [
            MicroInstruction(op=MicroOp.POP, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=8),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=8),
            MicroInstruction(op=MicroOp.POW_F32, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=8),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        # POW_F64:
        UserOpcode.POW_F64: [
            MicroInstruction(op=MicroOp.POP64, dst=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=8),
            MicroInstruction(op=MicroOp.POP64, dst=Reg.AX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, target=8),
            MicroInstruction(op=MicroOp.POW_F64, dst=Reg.AX, src=Reg.BX),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=8),
            MicroInstruction(op=MicroOp.PUSH64, src=Reg.AX),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ],
        UserOpcode.ZERO_MEM: [
            MicroInstruction(op=MicroOp.ZERO_MEM),
            MicroInstruction(op=MicroOp.RET),
        ],
    }

    # Dynamically register constants (0xA0..0xAF) and storage slots (0xD0..0xDF, 0xE0..0xEF)
    for _op in range(0xA0, 0xB0):
        _user_op = UserOpcode(_op)
        if _op & 1:  # 64-bit constant
            _ucode[_user_op] = [
                MicroInstruction(op=MicroOp.LOAD_CONST, imm=_op),
                MicroInstruction(op=MicroOp.PUSH64, src=Reg.FX),
                MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.OVERFLOW, target=4),
                MicroInstruction(op=MicroOp.RET),
                MicroInstruction(op=MicroOp.TRAP),
            ]
        else:  # 32-bit constant
            _ucode[_user_op] = [
                MicroInstruction(op=MicroOp.LOAD_CONST, imm=_op),
                MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
                MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.OVERFLOW, target=4),
                MicroInstruction(op=MicroOp.RET),
                MicroInstruction(op=MicroOp.TRAP),
            ]

    for _slot in range(16):
        _cp_mem = UserOpcode(0xD0 + _slot)
        _ucode[_cp_mem] = [
            MicroInstruction(op=MicroOp.CP_MEM_TOS, imm=_slot),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=3),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ]

        _cp_tos = UserOpcode(0xE0 + _slot)
        _ucode[_cp_tos] = [
            MicroInstruction(op=MicroOp.CP_TOS_MEM, imm=_slot),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.ERR, target=3),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ]

    @classmethod
    def get(cls, opcode: UserOpcode) -> List[MicroInstruction]:
        if opcode not in cls._ucode:
            raise NotImplementedError(f"Microcode for opcode {opcode} not implemented")
        return cls._ucode[opcode]
