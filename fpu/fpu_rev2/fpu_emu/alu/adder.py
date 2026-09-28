"""32-bit and 64-bit parallel adder/subtractor ALU primitive (alu_adder).

Implements ADD, ADC, SUB, SBB, and CMP per SystemDesign.md Section 3.1.
Operates on the physical hardware register file and advances the system clock.
"""

from typing import Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag

# Permitted source registers
VALID_32BIT_SRCS = {
    Reg.BL, Reg.DL, Reg.FL, Reg.BH, Reg.DH, Reg.FH, Reg.AH, Reg.AL
}
VALID_64BIT_SRCS = {
    Reg.BX, Reg.DX, Reg.FX, Reg.AX
}


def adder_core(
    a: bytearray,
    b: bytearray,
    cin: int = 0,
    sub: bool = False
) -> Tuple[bytearray, bool, bool, bool, bool]:
    """Pure byte-by-byte 32-bit carry-lookahead/ripple adder-subtractor core.

    Models MachXO2 CCU2C dedicated carry chains.

    :param a: 4-byte Little-Endian operand A
    :param b: 4-byte Little-Endian operand B
    :param cin: Carry-in (0 or 1) for addition; Borrow-in (0 or 1) for subtraction
    :param sub: True for subtraction (A - B - cin), False for addition (A + B + cin)
    :return: (result, carry_borrow_out, zf, sf, vf)
    """
    if len(a) != 4 or len(b) != 4:
        raise ValueError(f"Operands must be 4 bytes each, got len(a)={len(a)}, len(b)={len(b)}")

    res = bytearray(4)

    # In two's-complement subtraction: A - B - borrow = A + (~B) + (1 - borrow)
    carry = (0 if cin else 1) if sub else cin

    for i in range(4):
        b_val = (b[i] ^ 0xFF) if sub else b[i]
        temp = a[i] + b_val + carry
        res[i] = temp & 0xFF
        carry = (temp >> 8) & 1

    # Zero flag: all 32 bits are 0
    zf = (res == b"\x00\x00\x00\x00")

    # Sign flag: bit 31 of result is 1
    sf = bool(res[3] & 0x80)

    a_msb = bool(a[3] & 0x80)
    b_msb = bool(b[3] & 0x80)
    r_msb = sf

    if sub:
        # Borrow out: carry == 0 means borrow occurred (A < B + borrow_in)
        cf = (carry == 0)
        # Two's complement signed overflow on subtraction:
        # Occurs when operands have different signs and result sign differs from A
        vf = (a_msb != b_msb) and (a_msb != r_msb)
    else:
        # Unsigned carry out of MSB
        cf = bool(carry)
        # Two's complement signed overflow on addition:
        # Occurs when operands have same sign and result sign differs from inputs
        vf = (a_msb == b_msb) and (a_msb != r_msb)

    return res, cf, zf, sf, vf


# -----------------------------------------------------------------------------
# 32-Bit Micro-Operations (1 cycle execution)
# -----------------------------------------------------------------------------
def add32(hw: Hardware, src: Reg):
    """ADD AL, src: 32-bit addition without carry (1 cycle)."""
    _validate_src32(src)
    hw.clock.tick(1)
    a = hw.reg.get(Reg.AL)
    b = hw.reg.get(src)
    res, cf, zf, sf, vf = adder_core(a, b, cin=0, sub=False)
    hw.reg.set(Reg.AL, res)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def adc32(hw: Hardware, src: Reg):
    """ADC AL, src: 32-bit addition with carry (1 cycle)."""
    _validate_src32(src)
    hw.clock.tick(1)
    cin = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0
    a = hw.reg.get(Reg.AL)
    b = hw.reg.get(src)
    res, cf, zf, sf, vf = adder_core(a, b, cin=cin, sub=False)
    hw.reg.set(Reg.AL, res)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def sub32(hw: Hardware, src: Reg):
    """SUB AL, src: 32-bit subtraction without borrow (1 cycle)."""
    _validate_src32(src)
    hw.clock.tick(1)
    a = hw.reg.get(Reg.AL)
    b = hw.reg.get(src)
    res, cf, zf, sf, vf = adder_core(a, b, cin=0, sub=True)
    hw.reg.set(Reg.AL, res)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def sbb32(hw: Hardware, src: Reg):
    """SBB AL, src: 32-bit subtraction with borrow (1 cycle)."""
    _validate_src32(src)
    hw.clock.tick(1)
    borrow_in = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0
    a = hw.reg.get(Reg.AL)
    b = hw.reg.get(src)
    res, cf, zf, sf, vf = adder_core(a, b, cin=borrow_in, sub=True)
    hw.reg.set(Reg.AL, res)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def cmp32(hw: Hardware, src: Reg):
    """CMP AL, src: 32-bit compare AL - src without modifying AL (1 cycle)."""
    _validate_src32(src)
    hw.clock.tick(1)
    a = hw.reg.get(Reg.AL)
    b = hw.reg.get(src)
    _, cf, zf, sf, vf = adder_core(a, b, cin=0, sub=True)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


# -----------------------------------------------------------------------------
# 64-Bit Compound Micro-Operations (2 cycle synthesized execution)
# -----------------------------------------------------------------------------
def add64(hw: Hardware, src: Reg):
    """ADD AX, src: 64-bit addition without carry (2 cycles)."""
    _validate_src64(src)
    hw.clock.tick(2)
    src_bytes = hw.reg.get(src)
    src_l, src_h = src_bytes[0:4], src_bytes[4:8]

    # Cycle 1: Low word add
    al = hw.reg.get(Reg.AL)
    res_l, cout_l, zf_l, _, _ = adder_core(al, src_l, cin=0, sub=False)

    # Cycle 2: High word add with carry
    ah = hw.reg.get(Reg.AH)
    res_h, cf, zf_h, sf, vf = adder_core(ah, src_h, cin=(1 if cout_l else 0), sub=False)

    hw.reg.set(Reg.AX, res_l + res_h)
    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


def adc64(hw: Hardware, src: Reg):
    """ADC AX, src: 64-bit addition with carry (2 cycles)."""
    _validate_src64(src)
    hw.clock.tick(2)
    cin = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0
    src_bytes = hw.reg.get(src)
    src_l, src_h = src_bytes[0:4], src_bytes[4:8]

    # Cycle 1: Low word add with initial carry
    al = hw.reg.get(Reg.AL)
    res_l, cout_l, zf_l, _, _ = adder_core(al, src_l, cin=cin, sub=False)

    # Cycle 2: High word add with carry
    ah = hw.reg.get(Reg.AH)
    res_h, cf, zf_h, sf, vf = adder_core(ah, src_h, cin=(1 if cout_l else 0), sub=False)

    hw.reg.set(Reg.AX, res_l + res_h)
    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


def sub64(hw: Hardware, src: Reg):
    """SUB AX, src: 64-bit subtraction without borrow (2 cycles)."""
    _validate_src64(src)
    hw.clock.tick(2)
    src_bytes = hw.reg.get(src)
    src_l, src_h = src_bytes[0:4], src_bytes[4:8]

    # Cycle 1: Low word subtract
    al = hw.reg.get(Reg.AL)
    res_l, bout_l, zf_l, _, _ = adder_core(al, src_l, cin=0, sub=True)

    # Cycle 2: High word subtract with borrow
    ah = hw.reg.get(Reg.AH)
    res_h, cf, zf_h, sf, vf = adder_core(ah, src_h, cin=(1 if bout_l else 0), sub=True)

    hw.reg.set(Reg.AX, res_l + res_h)
    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


def sbb64(hw: Hardware, src: Reg):
    """SBB AX, src: 64-bit subtraction with borrow (2 cycles)."""
    _validate_src64(src)
    hw.clock.tick(2)
    borrow_in = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0
    src_bytes = hw.reg.get(src)
    src_l, src_h = src_bytes[0:4], src_bytes[4:8]

    # Cycle 1: Low word subtract with initial borrow
    al = hw.reg.get(Reg.AL)
    res_l, bout_l, zf_l, _, _ = adder_core(al, src_l, cin=borrow_in, sub=True)

    # Cycle 2: High word subtract with borrow
    ah = hw.reg.get(Reg.AH)
    res_h, cf, zf_h, sf, vf = adder_core(ah, src_h, cin=(1 if bout_l else 0), sub=True)

    hw.reg.set(Reg.AX, res_l + res_h)
    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


def cmp64(hw: Hardware, src: Reg):
    """CMP AX, src: 64-bit compare AX - src without modifying AX (2 cycles)."""
    _validate_src64(src)
    hw.clock.tick(2)
    src_bytes = hw.reg.get(src)
    src_l, src_h = src_bytes[0:4], src_bytes[4:8]

    al = hw.reg.get(Reg.AL)
    _, bout_l, zf_l, _, _ = adder_core(al, src_l, cin=0, sub=True)

    ah = hw.reg.get(Reg.AH)
    _, cf, zf_h, sf, vf = adder_core(ah, src_h, cin=(1 if bout_l else 0), sub=True)

    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------
def _validate_src32(src: Reg):
    if not isinstance(src, Reg) or src not in VALID_32BIT_SRCS:
        raise ValueError(f"Invalid 32-bit source register: {src}")


def _validate_src64(src: Reg):
    if not isinstance(src, Reg) or src not in VALID_64BIT_SRCS:
        raise ValueError(f"Invalid 64-bit source register: {src}")


def _set_flags(hw: Hardware, cf: bool, zf: bool, sf: bool, vf: bool):
    hw.reg.set_flag(StatusFlag.CARRY, cf)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
    hw.reg.set_flag(StatusFlag.OVERFLOW, vf)
