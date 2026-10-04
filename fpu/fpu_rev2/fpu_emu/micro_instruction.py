from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Optional

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
    dst: Optional[Reg] = None
    src: Optional[Reg] = None
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
        dst_val = (int(self.dst.value) & 0x0F) if self.dst is not None else 0
        src_val = (int(self.src.value) & 0x0F) if self.src is not None else 0
        flag_val = self.flag.value & 0x07 if self.flag is not None else 0

        # Pack into 18-bit integer
        inst_18 = (
            (op_val << 12)
            | (w_val << 11)
            | (dst_val << 7)
            | (src_val << 3)
            | flag_val
        )

        buf = inst_18.to_bytes(instr_reg.size_in_bytes, byteorder="big")
        instr_reg.write(buf)

        imm_val = self.imm & 0x3FF
        buf = imm_val.to_bytes(imm_reg.size_in_bytes, byteorder="big")
        imm_reg.write(buf)

    @classmethod
    def from_register(cls, r: Register) -> "MicroInstruction":
        """
        Decodes bits [31:14] (18 bits) from an 18-bit Register instance.

        N.B.: There is no immedaite value, will always be 0
        """
        raw_bytes = r.read()
        inst_18 = int.from_bytes(raw_bytes, byteorder="big")

        # Unpack 18-bit fields
        flag_val = inst_18 & 0x07
        src_val = (inst_18 >> 3) & 0x0F
        dst_val = (inst_18 >> 7) & 0x0F
        w_val = (inst_18 >> 11) & 0x01
        op_val = (inst_18 >> 12) & 0x3F

        op = MicroOp(op_val)
        w = IW.W64 if w_val == 1 else IW.W32
        flag = StatusFlag(flag_val) if flag_val > 0 else None

        try:
            dst = Reg(dst_val)
        except ValueError:
            dst = None

        try:
            src = Reg(src_val)
        except ValueError:
            src = None

        return cls(
            op=op,
            w=w,
            dst=dst,
            src=src,
            flag=flag,
            imm=0,  # Immediate loaded separately
        )
