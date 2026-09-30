"""Floating-point natural logarithm (LN) ALU module.

Implements range reduction and high-precision evaluation for IEEE-754 F32 and F64:
    ln(x) = ln(M * 2^E) = E * ln(2) + ln(M)
where M in [1.0, 2.0) and E is the unbiased exponent.

Hardware registers and ROM table (FLASH_LN_BASE = 0x1200) are modeled.
Zero Python `math` module; all arithmetic is performed via synthesizable ALU primitives.
"""

from fpu_emu.alu.fp_mul_div import add_f32, sub_f32, mul_f32, div_f32, add_f64, sub_f64, mul_f64, div_f64
from fpu_emu.alu.lzc import lzc32, lzc64
from fpu_emu.alu.shifter import lsl32, lsr32, lsl64, lsr64
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag

LN2_F32 = 0x3F317218
LN2_F64 = 0x3FE62E42FEFA39EF
ONE_F32 = 0x3F800000
ONE_F64 = 0x3FF0000000000000
NAN_F32 = 0x7FC00000
NAN_F64 = 0x7FF8000000000000
NEG_INF_F32 = 0xFF800000
NEG_INF_F64 = 0xFFF0000000000000

# Pre-encoded IEEE-754 odd integer denominators: (2k + 1)
DENOMS_F32 = [
    0x40400000,  # 3.0
    0x40A00000,  # 5.0
    0x40E00000,  # 7.0
    0x41100000,  # 9.0
    0x41300000,  # 11.0
    0x41500000,  # 13.0
    0x41700000,  # 15.0
]

DENOMS_F64 = [
    0x4008000000000000,  # 3.0
    0x4014000000000000,  # 5.0
    0x401C000000000000,  # 7.0
    0x4022000000000000,  # 9.0
    0x4026000000000000,  # 11.0
    0x402A000000000000,  # 13.0
    0x402E000000000000,  # 15.0
    0x4031000000000000,  # 17.0
    0x4033000000000000,  # 19.0
    0x4035000000000000,  # 21.0
    0x4037000000000000,  # 23.0
    0x4039000000000000,  # 25.0
    0x403B000000000000,  # 27.0
    0x403D000000000000,  # 29.0
]


def _int_to_f32(hw: Hardware, val: int) -> int:
    """Converts a signed integer to IEEE-754 single precision bit pattern using LZC and Shifter."""
    if val == 0:
        return 0
    sign = 1 if val < 0 else 0
    abs_val = (-val if val < 0 else val) & 0xFFFFFFFF

    hw.reg.testharness_set(Reg.AL, Registers.from_int(abs_val, 4))
    lz_count = lzc32(hw, Reg.AL)
    msb_pos = 31 - lz_count

    if msb_pos >= 23:
        shift = msb_pos - 23
        lsr32(hw, shift=shift, reg=Reg.AL)
    else:
        shift = 23 - msb_pos
        lsl32(hw, shift=shift, reg=Reg.AL)

    mant = Registers.to_int(hw.reg.get(Reg.AL)) & 0x7FFFFF
    exp = 127 + msb_pos
    return (sign << 31) | (exp << 23) | mant


def _int_to_f64(hw: Hardware, val: int) -> int:
    """Converts a signed integer to IEEE-754 double precision bit pattern using LZC and Shifter."""
    if val == 0:
        return 0
    sign = 1 if val < 0 else 0
    abs_val = (-val if val < 0 else val) & 0xFFFFFFFFFFFFFFFF

    hw.reg.testharness_set(Reg.AX, Registers.from_int(abs_val, 8))
    lz_count = lzc64(hw, Reg.AX)
    msb_pos = 63 - lz_count

    if msb_pos >= 52:
        shift = msb_pos - 52
        lsr64(hw, shift=shift, reg=Reg.AX)
    else:
        shift = 52 - msb_pos
        lsl64(hw, shift=shift, reg=Reg.AX)

    mant = Registers.to_int(hw.reg.get(Reg.AX)) & 0x000FFFFFFFFFFFFF
    exp = 1023 + msb_pos
    return (sign << 63) | (exp << 52) | mant



def ln_seed_index_f32(mantissa_u32: int) -> int:
    """Extracts top 8 fraction bits (AL[30:23]) for ROM LN seed lookup."""
    return (mantissa_u32 >> 23) & 0xFF


def ln_seed_index_f64(mantissa_u64: int) -> int:
    """Extracts top 8 fraction bits (AX[62:55]) for ROM LN seed lookup."""
    return (mantissa_u64 >> 55) & 0xFF


def _eval_ln_m_f32(hw: Hardware, m_raw: int) -> int:
    """Evaluates ln(M) for M in [1.0, 2.0) via ALU primitives (32-bit)."""
    hw.reg.testharness_set(Reg.AL, Registers.from_int(m_raw, 4))
    hw.reg.testharness_set(Reg.BL, Registers.from_int(ONE_F32, 4))
    sub_f32(hw, Reg.AL, Reg.BL)
    num_raw = Registers.to_int(hw.reg.get(Reg.AL))

    hw.reg.testharness_set(Reg.AL, Registers.from_int(m_raw, 4))
    hw.reg.testharness_set(Reg.BL, Registers.from_int(ONE_F32, 4))
    add_f32(hw, Reg.AL, Reg.BL)
    den_raw = Registers.to_int(hw.reg.get(Reg.AL))

    hw.reg.testharness_set(Reg.AL, Registers.from_int(num_raw, 4))
    hw.reg.testharness_set(Reg.BL, Registers.from_int(den_raw, 4))
    div_f32(hw, Reg.AL, Reg.BL)
    z_raw = Registers.to_int(hw.reg.get(Reg.AL))

    hw.reg.testharness_set(Reg.AL, Registers.from_int(z_raw, 4))
    hw.reg.testharness_set(Reg.BL, Registers.from_int(z_raw, 4))
    mul_f32(hw, Reg.AL, Reg.BL)
    z2_raw = Registers.to_int(hw.reg.get(Reg.AL))

    term_raw = z_raw
    acc_raw = z_raw
    for d_raw in DENOMS_F32:
        hw.reg.testharness_set(Reg.AL, Registers.from_int(term_raw, 4))
        hw.reg.testharness_set(Reg.BL, Registers.from_int(z2_raw, 4))
        mul_f32(hw, Reg.AL, Reg.BL)
        term_raw = Registers.to_int(hw.reg.get(Reg.AL))

        hw.reg.testharness_set(Reg.AL, Registers.from_int(term_raw, 4))
        hw.reg.testharness_set(Reg.BL, Registers.from_int(d_raw, 4))
        div_f32(hw, Reg.AL, Reg.BL)
        term_k_raw = Registers.to_int(hw.reg.get(Reg.AL))

        hw.reg.testharness_set(Reg.AL, Registers.from_int(acc_raw, 4))
        hw.reg.testharness_set(Reg.BL, Registers.from_int(term_k_raw, 4))
        add_f32(hw, Reg.AL, Reg.BL)
        acc_raw = Registers.to_int(hw.reg.get(Reg.AL))

    if acc_raw != 0:
        exp_acc = (acc_raw >> 23) & 0xFF
        acc_raw = (acc_raw & 0x807FFFFF) | ((exp_acc + 1) << 23)
    return acc_raw


def _eval_ln_m_f64(hw: Hardware, m_raw: int) -> int:
    """Evaluates ln(M) for M in [1.0, 2.0) via ALU primitives (64-bit)."""
    hw.reg.testharness_set(Reg.AX, Registers.from_int(m_raw, 8))
    hw.reg.testharness_set(Reg.BX, Registers.from_int(ONE_F64, 8))
    sub_f64(hw, Reg.AX, Reg.BX)
    num_raw = Registers.to_int(hw.reg.get(Reg.AX))

    hw.reg.testharness_set(Reg.AX, Registers.from_int(m_raw, 8))
    hw.reg.testharness_set(Reg.BX, Registers.from_int(ONE_F64, 8))
    add_f64(hw, Reg.AX, Reg.BX)
    den_raw = Registers.to_int(hw.reg.get(Reg.AX))

    hw.reg.testharness_set(Reg.AX, Registers.from_int(num_raw, 8))
    hw.reg.testharness_set(Reg.BX, Registers.from_int(den_raw, 8))
    div_f64(hw, Reg.AX, Reg.BX)
    z_raw = Registers.to_int(hw.reg.get(Reg.AX))

    hw.reg.testharness_set(Reg.AX, Registers.from_int(z_raw, 8))
    hw.reg.testharness_set(Reg.BX, Registers.from_int(z_raw, 8))
    mul_f64(hw, Reg.AX, Reg.BX)
    z2_raw = Registers.to_int(hw.reg.get(Reg.AX))

    term_raw = z_raw
    acc_raw = z_raw
    for d_raw in DENOMS_F64:
        hw.reg.testharness_set(Reg.AX, Registers.from_int(term_raw, 8))
        hw.reg.testharness_set(Reg.BX, Registers.from_int(z2_raw, 8))
        mul_f64(hw, Reg.AX, Reg.BX)
        term_raw = Registers.to_int(hw.reg.get(Reg.AX))

        hw.reg.testharness_set(Reg.AX, Registers.from_int(term_raw, 8))
        hw.reg.testharness_set(Reg.BX, Registers.from_int(d_raw, 8))
        div_f64(hw, Reg.AX, Reg.BX)
        term_k_raw = Registers.to_int(hw.reg.get(Reg.AX))

        hw.reg.testharness_set(Reg.AX, Registers.from_int(acc_raw, 8))
        hw.reg.testharness_set(Reg.BX, Registers.from_int(term_k_raw, 8))
        add_f64(hw, Reg.AX, Reg.BX)
        acc_raw = Registers.to_int(hw.reg.get(Reg.AX))

    if acc_raw != 0:
        exp_acc = (acc_raw >> 52) & 0x7FF
        acc_raw = (acc_raw & 0x800FFFFFFFFFFFFF) | ((exp_acc + 1) << 52)
    return acc_raw


def ln_mantissa_core(m: float, is_64: bool = False) -> float:
    """Evaluates ln(M) for M in [1.0, 2.0) using ALU operations."""
    hw = Hardware()
    if is_64:
        m_raw = Registers.to_int(Registers.from_f64(m))
        res_raw = _eval_ln_m_f64(hw, m_raw)
        return Registers.to_f64(Registers.from_int(res_raw, 8))
    else:
        m_raw = Registers.to_int(Registers.from_f32(m))
        res_raw = _eval_ln_m_f32(hw, m_raw)
        return Registers.to_f32(Registers.from_int(res_raw, 4))


def ln_f32(hw: Hardware):
    """Computes natural logarithm ln(AL) -> AL (IEEE-754 single precision).

    Synthesizable datapath:
      - Domain error checks: x <= 0 produces -inf / NaN with ERR=True.
      - Special case: ln(1.0) = 0.0 with ZERO=True.
      - Range reduction: x = M * 2^E, with M in [1.0, 2.0).
      - Table seed query: hw.rom.load_ln_seed.
      - ln(M) evaluation via area hyperbolic tangent series using ALU primitives.
      - E * ln(2) + ln(M) combined via float multiply and add.
    """
    raw = Registers.to_int(hw.reg.get(Reg.AL))
    sign = (raw >> 31) & 1
    exp = (raw >> 23) & 0xFF
    frac = raw & 0x7FFFFF

    if sign == 1 or (exp == 0 and frac == 0):
        hw.clock.tick(2)
        hw.reg.set_flag(StatusFlag.ERR, True)
        if exp == 0 and frac == 0:
            hw.reg.testharness_set(Reg.AL, Registers.from_int(NEG_INF_F32, 4))
            hw.reg.set_flag(StatusFlag.SIGN, True)
            hw.reg.set_flag(StatusFlag.ZERO, False)
        else:
            hw.reg.testharness_set(Reg.AL, Registers.from_int(NAN_F32, 4))
            hw.reg.set_flag(StatusFlag.SIGN, False)
            hw.reg.set_flag(StatusFlag.ZERO, False)
        return

    if raw == ONE_F32:
        hw.clock.tick(2)
        hw.reg.testharness_set(Reg.AL, Registers.from_int(0, 4))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    # ROM access modeling
    idx = ln_seed_index_f32(frac | 0x800000)
    _ = hw.rom.load_ln_seed(idx)
    hw.clock.tick(6)

    # Range reduction: x = M * 2^E
    e_int = exp - 127
    m_raw = 0x3F800000 | frac  # 1.0 + frac

    # Evaluate ln(M)
    ln_m_raw = _eval_ln_m_f32(hw, m_raw)

    if e_int != 0:
        e_f32_raw = _int_to_f32(hw, e_int)
        hw.reg.testharness_set(Reg.AL, Registers.from_int(e_f32_raw, 4))
        hw.reg.testharness_set(Reg.BL, Registers.from_int(LN2_F32, 4))
        mul_f32(hw, Reg.AL, Reg.BL)
        e_ln2_raw = Registers.to_int(hw.reg.get(Reg.AL))

        hw.reg.testharness_set(Reg.AL, Registers.from_int(e_ln2_raw, 4))
        hw.reg.testharness_set(Reg.BL, Registers.from_int(ln_m_raw, 4))
        add_f32(hw, Reg.AL, Reg.BL)
        res_raw = Registers.to_int(hw.reg.get(Reg.AL))
    else:
        res_raw = ln_m_raw

    hw.reg.testharness_set(Reg.AL, Registers.from_int(res_raw, 4))
    res_sign = (res_raw >> 31) & 1
    res_exp = (res_raw >> 23) & 0xFF
    res_frac = res_raw & 0x7FFFFF
    is_zero = (res_exp == 0 and res_frac == 0)
    hw.reg.set_flag(StatusFlag.ERR, False)
    hw.reg.set_flag(StatusFlag.ZERO, is_zero)
    hw.reg.set_flag(StatusFlag.SIGN, res_sign == 1)


def ln_f64(hw: Hardware):
    """Computes natural logarithm ln(AX) -> AX (IEEE-754 double precision).

    Synthesizable datapath:
      - Domain error checks: x <= 0 produces -inf / NaN with ERR=True.
      - Special case: ln(1.0) = 0.0 with ZERO=True.
      - Range reduction: x = M * 2^E, with M in [1.0, 2.0).
      - Table seed query: hw.rom.load_ln_seed.
      - ln(M) evaluation via area hyperbolic tangent series using ALU primitives.
      - E * ln(2) + ln(M) combined via float multiply and add.
    """
    raw = Registers.to_int(hw.reg.get(Reg.AX))
    sign = (raw >> 63) & 1
    exp = (raw >> 52) & 0x7FF
    frac = raw & 0x000FFFFFFFFFFFFF

    if sign == 1 or (exp == 0 and frac == 0):
        hw.clock.tick(3)
        hw.reg.set_flag(StatusFlag.ERR, True)
        if exp == 0 and frac == 0:
            hw.reg.testharness_set(Reg.AX, Registers.from_int(NEG_INF_F64, 8))
            hw.reg.set_flag(StatusFlag.SIGN, True)
            hw.reg.set_flag(StatusFlag.ZERO, False)
        else:
            hw.reg.testharness_set(Reg.AX, Registers.from_int(NAN_F64, 8))
            hw.reg.set_flag(StatusFlag.SIGN, False)
            hw.reg.set_flag(StatusFlag.ZERO, False)
        return

    if raw == ONE_F64:
        hw.clock.tick(3)
        hw.reg.testharness_set(Reg.AX, Registers.from_int(0, 8))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    idx = ln_seed_index_f64(frac | 0x0010000000000000)
    _ = hw.rom.load_ln_seed(idx)
    hw.clock.tick(11)

    e_int = exp - 1023
    m_raw = 0x3FF0000000000000 | frac

    # Evaluate ln(M)
    ln_m_raw = _eval_ln_m_f64(hw, m_raw)

    if e_int != 0:
        e_f64_raw = _int_to_f64(hw, e_int)
        hw.reg.testharness_set(Reg.AX, Registers.from_int(e_f64_raw, 8))
        hw.reg.testharness_set(Reg.BX, Registers.from_int(LN2_F64, 8))
        mul_f64(hw, Reg.AX, Reg.BX)
        e_ln2_raw = Registers.to_int(hw.reg.get(Reg.AX))

        hw.reg.testharness_set(Reg.AX, Registers.from_int(e_ln2_raw, 8))
        hw.reg.testharness_set(Reg.BX, Registers.from_int(ln_m_raw, 8))
        add_f64(hw, Reg.AX, Reg.BX)
        res_raw = Registers.to_int(hw.reg.get(Reg.AX))
    else:
        res_raw = ln_m_raw

    hw.reg.testharness_set(Reg.AX, Registers.from_int(res_raw, 8))
    res_sign = (res_raw >> 63) & 1
    res_exp = (res_raw >> 52) & 0x7FF
    res_frac = res_raw & 0x000FFFFFFFFFFFFF
    is_zero = (res_exp == 0 and res_frac == 0)
    hw.reg.set_flag(StatusFlag.ERR, False)
    hw.reg.set_flag(StatusFlag.ZERO, is_zero)
    hw.reg.set_flag(StatusFlag.SIGN, res_sign == 1)
