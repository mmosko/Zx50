from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Union

from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.rom.fpu_const_map import FpuTable


class IW(IntEnum):
    W32 = 0
    W64 = 1


@dataclass
class MicroInstruction:
    """Represents a single micro-instruction word executed by the micro-sequencer."""

    op: MicroOp
    w: IW = IW.W32
    dst: Reg = Reg.NONE
    src: Union[Reg, FpuTable] = Reg.NONE
    src1: Reg = Reg.NONE
    flag: StatusFlag = StatusFlag.NONE # a "0" value
    imm: int = 0

    def is_w32(self) -> bool:
        return self.w == IW.W32

    def is_w64(self) -> bool:
        return self.w == IW.W64

    def to_int(self) -> int:
        op_val = int(self.op.value) & 0x3F
        w_val = int(self.w.value) & 0x01
        dst_val = self.dst.value & 0x0F
        src_val = self.src.value & 0x0F
        flag_val = self.flag.value & 0x07
        src1_val = self.src1.value & 0x0F
        imm_val = self.imm & 0x3FF

        return (
            (op_val << 26)
            | (w_val << 25)
            | (dst_val << 21)
            | (src_val << 17)
            | (flag_val << 14)
            | (src1_val << 10)
            | imm_val
        )

    def to_bytes(self) -> bytes:
        """
        Encodes the micro-instruction into machine code bytes (little-endian, 4 bytes).

        :return: 4-byte machine instruction word in little-endian byte order.
        """
        return self.to_int().to_bytes(4, byteorder="little", signed=False)

    def to_register(self, instr_reg: Register, imm_reg: Register) -> None:
        """Encodes bits [31:10] (22 bits) into a 22-bit Register instance."""
        word = self.to_int()
        instr_reg.write((word >> 10) & 0x3FFFFF)
        imm_reg.write(word & 0x3FF)

    @classmethod
    def from_int(cls, word: int) -> "MicroInstruction":
        """Decodes a 32-bit machine word integer into a MicroInstruction."""
        imm = word & 0x3FF
        src1_val = (word >> 10) & 0x0F
        flag_val = (word >> 14) & 0x07
        src_val = (word >> 17) & 0x0F
        dst_val = (word >> 21) & 0x0F
        w_val = (word >> 25) & 0x01
        op_val = (word >> 26) & 0x3F

        op = MicroOp(op_val)
        w = IW.W64 if w_val == 1 else IW.W32
        dst = Reg(dst_val)
        src = Reg(src_val)
        src1 = Reg(src1_val)
        flag = StatusFlag(flag_val)

        if op == MicroOp.LDC:
            try:
                src = FpuTable(src_val)
            except ValueError:
                src = Reg(src_val)

        return cls(
            op=op,
            w=w,
            dst=dst,
            src=src,
            src1=src1,
            flag=flag,
            imm=imm,
        )

    @classmethod
    def from_register(cls, r: Register) -> "MicroInstruction":
        """
        Decodes bits [31:10] (22 bits) from a 22-bit Register instance.

        N.B.: There is no immediate value in this register, imm will always be 0.
        """
        return cls.from_int(r.read_int() << 10)

    @classmethod
    def from_bytes(cls, data: bytes) -> "MicroInstruction":
        """Decodes 4 machine instruction bytes (little-endian) into a MicroInstruction."""
        if len(data) < 4:
            raise ValueError(f"MicroInstruction requires at least 4 bytes, got {len(data)}")
        word = int.from_bytes(data[:4], byteorder="little", signed=False)
        return cls.from_int(word)
