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
    flag: Optional[StatusFlag] = None
    imm: int = 0

    def is_w32(self) -> bool:
        return self.w == IW.W32

    def is_w64(self) -> bool:
        return self.w == IW.W64

    def to_register(self, instr_reg: Register, imm_reg: Register) -> None:
        """Encodes bits [31:14] (18 bits) into an 18-bit Register instance."""
        op_val = int(self.op.value) & 0x3F
        w_val = self.w.value
        dst_val = self.dst.value & 0x0F
        src_val = self.src.value & 0x0F
        flag_val = self.flag.value if self.flag is not None else 0

        # Pack into 18-bit integer
        inst_18 = (
            (op_val << 12)
            | (w_val << 11)
            | (dst_val << 7)
            | (src_val << 3)
            | flag_val
        )

        instr_reg.write(inst_18)

        imm_val = self.imm & 0x3FF
        imm_reg.write(imm_val)

    @classmethod
    def from_register(cls, r: Register) -> "MicroInstruction":
        """
        Decodes bits [31:14] (18 bits) from an 18-bit Register instance.

        N.B.: There is no immediate value in this register, imm will always be 0.
        """
        inst_18 = r.read_int()

        # Unpack 18-bit fields
        flag_val = inst_18 & 0x07
        src_val = (inst_18 >> 3) & 0x0F
        dst_val = (inst_18 >> 7) & 0x0F
        w_val = (inst_18 >> 11) & 0x01
        op_val = (inst_18 >> 12) & 0x3F

        op = MicroOp(op_val)
        w = IW.W64 if w_val == 1 else IW.W32

        dst = Reg(dst_val)
        src = Reg(src_val)

        flag = StatusFlag(flag_val) if src is Reg.NONE else None

        return cls(
            op=op,
            w=w,
            dst=dst,
            src=src,
            flag=flag,
            imm=0,  # Immediate loaded separately
        )
