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
        # 1: JNZ UNDERFLOW -> 7 (TRAP)
        # 2: POP AL
        # 3: JNZ UNDERFLOW -> 7 (TRAP)
        # 4: ADD AL, BL
        # 5: PUSH AL
        # 6: RET
        # 7: TRAP
        UserOpcode.ADD_I32: [
            MicroInstruction(op=MicroOp.POP, w=IW.W32, dst=Reg.BL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=7),
            MicroInstruction(op=MicroOp.POP, dst=Reg.AL),
            MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=7),
            MicroInstruction(op=MicroOp.ADD, dst=Reg.AL, src=Reg.BL),
            MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
            MicroInstruction(op=MicroOp.RET),
            MicroInstruction(op=MicroOp.TRAP),
        ]
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
