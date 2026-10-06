from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Union

from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.micro_opcodes import MicroOp


class IW(IntEnum):
    W32 = 0
    W64 = 1


@dataclass
class MicroInstruction:
    """Represents a single micro-instruction word executed by the micro-sequencer."""

    op: MicroOp
    w: IW = IW.W32
    dst: Reg = Reg.NONE
    src: Reg = Reg.NONE
    src1: Reg = Reg.NONE
    flag: Optional[StatusFlag] = None
    imm: int = 0

    def is_w32(self) -> bool:
        return self.w == IW.W32

    def is_w64(self) -> bool:
        return self.w == IW.W64

    def to_register(self, instr_reg: Register, imm_reg: Register) -> None:
        """Encodes bits [31:11] (21 bits) into a 21-bit Register instance."""
        op_val = int(self.op.value) & 0x3F
        w_val = self.w.value
        dst_val = self.dst.value & 0x0F
        src_val = self.src.value & 0x0F
        flag_val = self.flag.value if self.flag is not None else 0

        effective_dst = self.dst
        if effective_dst is Reg.NONE and self.op in (MicroOp.EXP_ADD, MicroOp.EXP_SUB):
            effective_dst = Reg.EA

        if self.src1 is not Reg.NONE:
            src1_val = self.src1.value & 0x07
        elif effective_dst is not Reg.NONE and effective_dst.value < 8:
            src1_val = effective_dst.value & 0x07
        else:
            src1_val = 0

        # Pack into 21-bit integer
        inst_21 = (
            (op_val << 15)
            | (w_val << 14)
            | (dst_val << 10)
            | (src_val << 6)
            | (flag_val << 3)
            | src1_val
        )

        instr_reg.write(inst_21)

        imm_val = self.imm & 0x3FF
        imm_reg.write(imm_val)

    @classmethod
    def from_register(cls, r: Register) -> "MicroInstruction":
        """
        Decodes bits [31:11] (21 bits) from a 21-bit Register instance.

        N.B.: There is no immediate value in this register, imm will always be 0.
        """
        inst_21 = r.read_int()

        # Unpack 21-bit fields
        src1_val = inst_21 & 0x07
        flag_val = (inst_21 >> 3) & 0x07
        src_val = (inst_21 >> 6) & 0x0F
        dst_val = (inst_21 >> 10) & 0x0F
        w_val = (inst_21 >> 14) & 0x01
        op_val = (inst_21 >> 15) & 0x3F

        op = MicroOp(op_val)
        w = IW.W64 if w_val == 1 else IW.W32

        dst = Reg(dst_val)
        src = Reg(src_val)

        if op in (MicroOp.JZ, MicroOp.JNZ) or (op == MicroOp.LDI and dst is Reg.NONE):
            flag = StatusFlag(flag_val)
        else:
            flag = None

        effective_dst = dst
        if effective_dst is Reg.NONE and op in (MicroOp.EXP_ADD, MicroOp.EXP_SUB):
            effective_dst = Reg.EA

        # Determine src1: if op reads HA_MUX and src1_val differs from canonical dst, restore src1
        if op in [
            MicroOp.ADD,
            MicroOp.SUB,
            MicroOp.CMP,
            MicroOp.AND,
            MicroOp.OR,
            MicroOp.XOR,
            MicroOp.EXP_ADD,
            MicroOp.EXP_SUB,
        ]:
            if effective_dst is not Reg.NONE and effective_dst.value < 8 and src1_val == effective_dst.value:
                src1 = Reg.NONE
            else:
                src1 = Reg(src1_val)
        else:
            src1 = Reg.NONE

        return cls(
            op=op,
            w=w,
            dst=dst,
            src=src,
            src1=src1,
            flag=flag,
            imm=0,  # Immediate loaded separately
        )
