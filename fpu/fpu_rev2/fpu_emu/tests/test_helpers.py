"""Test helpers for simulating user operations against the FPGA model."""

import struct
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import Reg
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp

MASK_32 = 0xFFFFFFFF
MASK_64 = 0xFFFFFFFFFFFFFFFF


def f32_to_bits(val: float) -> int:
    """Converts a Python float to IEEE-754 32-bit integer bits."""
    return struct.unpack(">I", struct.pack(">f", val))[0]


def bits_to_f32(val: int) -> float:
    """Converts IEEE-754 32-bit integer bits to a Python float."""
    return struct.unpack(">f", struct.pack(">I", val & MASK_32))[0]


def f64_to_bits(val: float) -> int:
    """Converts a Python float to IEEE-754 64-bit integer bits."""
    return struct.unpack(">Q", struct.pack(">d", val))[0]


def bits_to_f64(val: int) -> float:
    """Converts IEEE-754 64-bit integer bits to a Python float."""
    return struct.unpack(">d", struct.pack(">Q", val & MASK_64))[0]



def user_push32(fpga: FpgaModel, val: int) -> None:
    """Simulates a user pushing a 32-bit word onto the math stack."""
    fpga.reg_file.al.write(val & MASK_32)
    fpga.reg_file.upc.write(0)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.PUSH, w=IW.W32, src=Reg.AL)])


def user_pop32(fpga: FpgaModel) -> int:
    """Simulates a user popping a 32-bit word from the math stack into DL."""
    fpga.reg_file.upc.write(0)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.POP, w=IW.W32, dst=Reg.DL)])
    return fpga.reg_file.dl.read_int()


def user_push64(fpga: FpgaModel, val: int) -> None:
    """Simulates a user pushing a 64-bit word onto the math stack (low word then high word)."""
    val_lo = val & MASK_32
    val_hi = (val >> 32) & MASK_32
    fpga.reg_file.al.write(val_lo)
    fpga.reg_file.ah.write(val_hi)
    fpga.reg_file.upc.write(0)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.PUSH, w=IW.W64, src=Reg.AL)])


def user_pop64(fpga: FpgaModel) -> int:
    """Simulates a user popping a 64-bit word from the math stack into DX (DH:DL)."""
    fpga.reg_file.upc.write(0)
    fpga.dispatcher._run([MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.DL)])
    res_lo = fpga.reg_file.dl.read_int()
    res_hi = fpga.reg_file.dh.read_int()
    return ((res_hi << 32) | res_lo) & MASK_64
