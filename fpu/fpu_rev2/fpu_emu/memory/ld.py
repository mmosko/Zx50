"""Immediate literal load (LD) operations.

Per SystemDesign.md Section 3 (Datapath Architecture) and Section 4.2 / 4.3:
- Loads immediate numeric literals from microcode instruction stream / ROM into
  a target register without touching DX or status flags.
- 32-bit registers (AL, AH, BL, BH, DL, DH, FL, FH, EA, EB): 2 clock cycles.
- 64-bit compound registers (AX, BX, DX, FX): 3 clock cycles.
- Control registers (C, SP, OSP): 1 clock cycle.
- Status flags are completely unaffected.
"""

from typing import Union
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg


def _int_to_bytes(val: int, length: int) -> bytes:
    """Converts integer (signed or unsigned) to little-endian bytes of exact length."""
    mask = (1 << (length * 8)) - 1
    return (val & mask).to_bytes(length, byteorder="little")


def _to_bytes(imm: Union[int, bytes, bytearray], length: int) -> bytes:
    """Normalizes int, bytes, or bytearray to exactly length bytes."""
    if isinstance(imm, int):
        return _int_to_bytes(imm, length)
    elif isinstance(imm, (bytes, bytearray)):
        if len(imm) < length:
            return bytes(imm) + b"\x00" * (length - len(imm))
        return bytes(imm[:length])
    raise TypeError(f"Invalid type for immediate operand: {type(imm).__name__}")


def ld32(hw: Hardware, dst: Reg, imm: Union[int, bytes, bytearray]) -> None:
    """Loads a 32-bit immediate literal into a register in 2 clock cycles."""
    if dst.is_64() or dst in (Reg.SP, Reg.OSP, Reg.C):
        raise ValueError(f"ld32 called with incompatible register: {dst}")

    data = _to_bytes(imm, 4)

    # 2 clock cycles for 32-bit immediate fetch and writeback
    hw.clock.tick(1)
    hw.clock.tick(1)
    hw.reg.set_res_bus(dst, data)


def ld64(hw: Hardware, dst: Reg, imm: Union[int, bytes, bytearray]) -> None:
    """Loads a 64-bit immediate literal into a compound register in 3 clock cycles."""
    if not dst.is_64():
        raise ValueError(f"ld64 requires 64-bit compound register: {dst}")

    data = _to_bytes(imm, 8)
    dst_lo = dst.lo_half()
    dst_hi = dst.hi_half()

    # 3 clock cycles: fetch low, fetch high & latch low, latch high
    hw.clock.tick(1)
    hw.clock.tick(1)
    hw.reg.set_res_bus(dst_lo, data[:4])
    hw.clock.tick(1)
    hw.reg.set_res_bus(dst_hi, data[4:8])


def ld_c(hw: Hardware, val: int) -> None:
    """Loads 6-bit loop counter C in 1 clock cycle."""
    hw.clock.tick(1)
    hw.reg.set_res_bus(Reg.C, val & 0x3F)


def ld_sp(hw: Hardware, val: int = 0) -> None:
    """Loads 8-bit Operand Stack Pointer SP in 1 clock cycle."""
    hw.clock.tick(1)
    hw.reg.sp = val & 0xFF


def ld_osp(hw: Hardware, val: int = 0) -> None:
    """Loads 8-bit Operation Stack Pointer OSP in 1 clock cycle."""
    hw.clock.tick(1)
    hw.reg.osp = val & 0xFF


def ld(hw: Hardware, dst: Reg, imm: Union[int, bytes, bytearray]) -> None:
    """Dispatches immediate load based on destination register type."""
    if isinstance(dst, str):
        dst = Reg[dst.upper()]

    if dst == Reg.SP:
        val = imm if isinstance(imm, int) else int.from_bytes(imm, byteorder="little")
        ld_sp(hw, val)
    elif dst == Reg.OSP:
        val = imm if isinstance(imm, int) else int.from_bytes(imm, byteorder="little")
        ld_osp(hw, val)
    elif dst == Reg.C:
        val = imm if isinstance(imm, int) else int.from_bytes(imm, byteorder="little")
        ld_c(hw, val)
    elif dst.is_64():
        ld64(hw, dst, imm)
    elif dst.is_32():
        ld32(hw, dst, imm)
    else:
        raise ValueError(f"Unsupported register for LD: {dst}")
