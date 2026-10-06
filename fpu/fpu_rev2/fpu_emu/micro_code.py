"""Microcode ROM mapping UserOpcode to micro-instruction sequences."""

from typing import Dict, List
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.registers import Reg, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.user_opcodes import UserOpcode


class MicroCode:
    """Microcode ROM lookup table."""

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
