"""Radix-4 Modified Booth Multiplier primitive (alu_booth_mul).

Per SystemDesign.md Section 3.6, Section 3.8, and Section 4:
- Hardware 2's complement multiplication retiring 2 bits per clock cycle.
- Inputs:
  * Multiplicand M: BL (32-bit) or BX (64-bit)
  * Multiplier Q: AL (32-bit) or AX (64-bit)
- Execution cycles:
  * 32-bit: 16 clock cycles -> produces 64-bit product in AX = {AH, AL}
  * 64-bit: 32 clock cycles -> produces 128-bit product in {DX, AX} = {DH, DL, AH, AL}
- Flag updates:
  * ZF: Set to 1 if entire product is 0, cleared otherwise
  * SF: Set to 1 if MSB of product is 1, cleared otherwise
  * CF: Cleared to 0
  * VF: Set to 1 if product overflows the source integer width
        (high half is not sign extension of low half)
"""

from typing import Set, Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers

# Width constants
WIDTH_32_BYTES = 4
WIDTH_64_BYTES = 8
BITS_PER_BYTE = 8

# Execution cycles
CYCLES_32 = 16
CYCLES_64 = 32

# Permitted source registers
VALID_32BIT_SRCS: Set[Reg] = {
    Reg.BL, Reg.DL, Reg.FL, Reg.BH, Reg.DH, Reg.FH
}
VALID_64BIT_SRCS: Set[Reg] = {
    Reg.BX, Reg.DX, Reg.FX
}


def _to_signed(val: int, bits: int) -> int:
    """Converts an unsigned integer of bit length `bits` to signed two's complement."""
    if val & (1 << (bits - 1)):
        return val - (1 << bits)
    return val


def booth_core(
    m_bytes: bytearray,
    q_bytes: bytearray,
    width_bytes: int = WIDTH_32_BYTES,
) -> Tuple[bytearray, bool, bool, bool, bool]:
    """Pure functional Radix-4 Modified Booth multiplication datapath.

    Simulates the step-by-step Radix-4 Booth iteration:
    - 3-bit window {Q[1:0], q_{-1}}
    - Partial product P addition/subtraction
    - Combined arithmetic right shift of {P, Q} by 2 bits.

    :param m_bytes: Multiplicand as Little-Endian bytearray (4 or 8 bytes).
    :param q_bytes: Multiplier as Little-Endian bytearray (4 or 8 bytes).
    :param width_bytes: 4 (32-bit) or 8 (64-bit).
    :return: (product_bytes, cf, zf, sf, vf)
    """
    if width_bytes not in (WIDTH_32_BYTES, WIDTH_64_BYTES):
        raise ValueError(f"Unsupported Booth multiplier width: {width_bytes} bytes")

    total_bits = width_bytes * BITS_PER_BYTE
    steps = total_bits // 2

    m_raw = Registers.to_int(m_bytes)
    q_raw = Registers.to_int(q_bytes)

    m_signed = _to_signed(m_raw, total_bits)
    q = q_raw
    p = 0
    q_minus_1 = 0

    for _ in range(steps):
        # 3-bit inspection window {Q[1:0], q_{-1}}
        window = ((q & 0x03) << 1) | q_minus_1

        match window:
            case 1 | 2:
                p += m_signed
            case 3:
                p += (m_signed << 1)
            case 4:
                p -= (m_signed << 1)
            case 5 | 6:
                p -= m_signed
            case _:
                pass  # Window 0 (000) or 7 (111): +0

        # Next booth bit q_{-1} is Q[1]
        q_minus_1 = (q >> 1) & 1

        # Arithmetic right shift of combined {P, Q} by 2 bits
        q = ((p & 0x03) << (total_bits - 2)) | (q >> 2)
        p >>= 2

    # Assemble 2N-bit product bytes
    low_half = q & ((1 << total_bits) - 1)
    high_half = p & ((1 << total_bits) - 1)

    low_bytes = Registers.from_int(low_half, width_bytes)
    high_bytes = Registers.from_int(high_half, width_bytes)
    product_bytes = low_bytes + high_bytes

    # Flag calculation
    cf = False
    zf = all(b == 0 for b in product_bytes)
    sf = bool(high_bytes[-1] & 0x80)

    # Overflow: High word is not the sign extension of low word
    sign_ext_mask = ((1 << total_bits) - 1) if (low_bytes[-1] & 0x80) else 0
    vf = (high_half != sign_ext_mask)

    return product_bytes, cf, zf, sf, vf


def mul32(hw: Hardware, src: Reg = Reg.BL):
    """MUL AL, src — 32-bit signed multiply yielding 64-bit product in AX (16 cycles)."""
    _validate_src32(src)
    hw.clock.tick(CYCLES_32)

    m_bytes = hw.reg.get(src)
    q_bytes = hw.reg.get(Reg.AL)

    prod_bytes, cf, zf, sf, vf = booth_core(m_bytes, q_bytes, width_bytes=WIDTH_32_BYTES)

    hw.reg.set(Reg.AX, prod_bytes)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def mul64(hw: Hardware, src: Reg = Reg.BX):
    """MUL AX, src — 64-bit signed multiply yielding 128-bit product in {DX, AX} (32 cycles)."""
    _validate_src64(src)
    hw.clock.tick(CYCLES_64)

    m_bytes = hw.reg.get(src)
    q_bytes = hw.reg.get(Reg.AX)

    prod_bytes, cf, zf, sf, vf = booth_core(m_bytes, q_bytes, width_bytes=WIDTH_64_BYTES)

    # Lower 64 bits to AX, upper 64 bits to DX
    hw.reg.set(Reg.AX, prod_bytes[0:8])
    hw.reg.set(Reg.DX, prod_bytes[8:16])
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def _validate_src32(src: Reg):
    if not isinstance(src, Reg) or src not in VALID_32BIT_SRCS:
        raise ValueError(f"Invalid 32-bit Booth multiply source register: {src}")


def _validate_src64(src: Reg):
    if not isinstance(src, Reg) or src not in VALID_64BIT_SRCS:
        raise ValueError(f"Invalid 64-bit Booth multiply source register: {src}")


def _set_flags(hw: Hardware, cf: bool, zf: bool, sf: bool, vf: bool):
    hw.reg.set_flag(StatusFlag.CARRY, cf)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
    hw.reg.set_flag(StatusFlag.OVERFLOW, vf)
