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
    flag: Optional[StatusFlag] = None
    imm: int = 0

    def is_w32(self) -> bool:
        return self.w == IW.W32

    def is_w64(self) -> bool:
        return self.w == IW.W64

    def to_int(self) -> int:
        """
        Machine word format (32 bits):
        ```text
             31        26 25  24     21 20    17 16        14 13     11 10 9                      0
            +------------+---+---------+--------+------------+---------+-+-----------------------+
            |   OPCODE   | W |   DST   |  SRC2  | FLAG_COND  |  SRC1   |R|   IMMEDIATE / ADDR    |
            |   [5:0]    |   |  [3:0]  | [3:0]  |   [2:0]    |  [2:0]  | |         [9:0]         |
            +------------+---+---------+--------+------------+---------+-+-----------------------+
            |<----------------- INSTR [20:0] (21 bits) --------------->| |<- IMM [9:0] (10 bits)->|
        ```
        """
        op_val = int(self.op.value) & 0x3F
        w_val = int(self.w.value) & 0x01

        effective_dst = self.dst
        if effective_dst is Reg.NONE and self.op in (MicroOp.EXP_ADD, MicroOp.EXP_SUB):
            effective_dst = Reg.EA
        dst_val = effective_dst.value & 0x0F

        src_val = self.src.value & 0x0F
        flag_val = (self.flag.value if hasattr(self.flag, "value") else int(self.flag)) & 0x07 if self.flag is not None else 0

        if self.src1 is not Reg.NONE:
            src1_val = self.src1.value & 0x07
        elif self.op == MicroOp.LDC:
            src1_val = Reg.IMM.value & 0x07
        elif effective_dst is not Reg.NONE and effective_dst.value < 8:
            src1_val = effective_dst.value & 0x07
        else:
            src1_val = 0

        return (
            (op_val << 26)
            | (w_val << 25)
            | (dst_val << 21)
            | (src_val << 17)
            | (flag_val << 14)
            | (src1_val << 11)
            | (self.imm & 0x3FF)
        )

    def to_bytes(self) -> bytes:
        """
        Encodes the micro-instruction into machine code bytes (little-endian, 4 bytes).

        :return: 4-byte machine instruction word in little-endian byte order.
        """
        return self.to_int().to_bytes(4, byteorder="little", signed=False)

    def to_register(self, instr_reg: Register, imm_reg: Register) -> None:
        """Encodes bits [31:11] (21 bits) into a 21-bit Register instance."""
        word = self.to_int()
        instr_reg.write((word >> 11) & 0x1FFFFF)
        imm_reg.write(word & 0x3FF)

    @classmethod
    def from_int(cls, word: int) -> "MicroInstruction":
        """Decodes a 32-bit machine word integer into a MicroInstruction."""
        imm = word & 0x3FF
        src1_val = (word >> 11) & 0x07
        flag_val = (word >> 14) & 0x07
        src_val = (word >> 17) & 0x0F
        dst_val = (word >> 21) & 0x0F
        w_val = (word >> 25) & 0x01
        op_val = (word >> 26) & 0x3F

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
        elif op == MicroOp.LDC:
            try:
                src = FpuTable(src_val)
            except ValueError:
                src = Reg(src_val)
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
            imm=imm,
        )

    @classmethod
    def from_register(cls, r: Register) -> "MicroInstruction":
        """
        Decodes bits [31:11] (21 bits) from a 21-bit Register instance.

        N.B.: There is no immediate value in this register, imm will always be 0.
        """
        return cls.from_int(r.read_int() << 11)

    @classmethod
    def from_bytes(cls, data: bytes) -> "MicroInstruction":
        """Decodes 4 machine instruction bytes (little-endian) into a MicroInstruction."""
        if len(data) < 4:
            raise ValueError(f"MicroInstruction requires at least 4 bytes, got {len(data)}")
        word = int.from_bytes(data[:4], byteorder="little", signed=False)
        return cls.from_int(word)
