"""Floating-point exponential (EXP / e^x) ALU module.

Implements range reduction and high-precision evaluation for IEEE-754 F32 and F64:
    e^x = 2^(x * log2(e)) = 2^k * 2^f
where k = floor(x * log2(e)) is the integer exponent shift,
and f in [0.0, 1.0) is evaluated via synthesizable Taylor polynomial convergence:
    2^f = exp(f * ln(2)).

Zero Python `math` module; all arithmetic is performed via synthesizable ALU primitives.
"""

from fpu_emu.alu.fp_mul_div import add_f32, sub_f32, mul_f32, div_f32, add_f64, sub_f64, mul_f64, div_f64
from fpu_emu.alu.lzc import lzc32, lzc64
from fpu_emu.alu.shifter import lsl32, lsr32, lsl64, lsr64
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag

LOG2E_F32 = 0x3FB8AA3B
LOG2E_F64 = 0x3FF71547652B82FE
LN2_F32 = 0x3F317218
LN2_F64 = 0x3FE62E42FEFA39EF
ONE_F32 = 0x3F800000
ONE_F64 = 0x3FF0000000000000
NAN_F32 = 0x7FC00000
NAN_F64 = 0x7FF8000000000000
POS_INF_F32 = 0x7F800000
POS_INF_F64 = 0x7FF0000000000000

# Pre-encoded IEEE-754 integer constants for n = 1 .. 11 (F32) and n = 1 .. 18 (F64)
FACTS_F32 = [
    0x3F800000,  # 1.0
    0x40000000,  # 2.0
    0x40400000,  # 3.0
    0x40800000,  # 4.0
    0x40A00000,  # 5.0
    0x40C00000,  # 6.0
    0x40E00000,  # 7.0
    0x41000000,  # 8.0
    0x41100000,  # 9.0
    0x41200000,  # 10.0
    0x41300000,  # 11.0
]

FACTS_F64 = [
    0x3FF0000000000000,  # 1.0
    0x4000000000000000,  # 2.0
    0x4008000000000000,  # 3.0
    0x4010000000000000,  # 4.0
    0x4014000000000000,  # 5.0
    0x4018000000000000,  # 6.0
    0x401C000000000000,  # 7.0
    0x4020000000000000,  # 8.0
    0x4022000000000000,  # 9.0
    0x4024000000000000,  # 10.0
    0x4026000000000000,  # 11.0
    0x4028000000000000,  # 12.0
    0x402A000000000000,  # 13.0
    0x402C000000000000,  # 14.0
    0x402E000000000000,  # 15.0
    0x4030000000000000,  # 16.0
    0x4031000000000000,  # 17.0
    0x4032000000000000,  # 18.0
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



def _eval_exp_frac_f32(hw: Hardware, f_raw: int) -> int:
    """Evaluates 2^f = exp(f * ln(2)) via ALU primitives (32-bit)."""
    hw.reg.testharness_set(Reg.AL, Registers.from_int(f_raw, 4))
    hw.reg.testharness_set(Reg.BL, Registers.from_int(LN2_F32, 4))
    mul_f32(hw, Reg.AL, Reg.BL)
    u_raw = Registers.to_int(hw.reg.get(Reg.AL))

    term_raw = ONE_F32
    acc_raw = ONE_F32
    for n_raw in FACTS_F32:
        hw.reg.testharness_set(Reg.AL, Registers.from_int(term_raw, 4))
        hw.reg.testharness_set(Reg.BL, Registers.from_int(u_raw, 4))
        mul_f32(hw, Reg.AL, Reg.BL)

        hw.reg.testharness_set(Reg.BL, Registers.from_int(n_raw, 4))
        div_f32(hw, Reg.AL, Reg.BL)
        term_raw = Registers.to_int(hw.reg.get(Reg.AL))

        hw.reg.testharness_set(Reg.BL, Registers.from_int(acc_raw, 4))
        add_f32(hw, Reg.AL, Reg.BL)
        acc_raw = Registers.to_int(hw.reg.get(Reg.AL))

    return acc_raw


def _eval_exp_frac_f64(hw: Hardware, f_raw: int) -> int:
    """Evaluates 2^f = exp(f * ln(2)) via ALU primitives (64-bit)."""
    hw.reg.testharness_set(Reg.AX, Registers.from_int(f_raw, 8))
    hw.reg.testharness_set(Reg.BX, Registers.from_int(LN2_F64, 8))
    mul_f64(hw, Reg.AX, Reg.BX)
    u_raw = Registers.to_int(hw.reg.get(Reg.AX))

    term_raw = ONE_F64
    acc_raw = ONE_F64
    for n_raw in FACTS_F64:
        hw.reg.testharness_set(Reg.AX, Registers.from_int(term_raw, 8))
        hw.reg.testharness_set(Reg.BX, Registers.from_int(u_raw, 8))
        mul_f64(hw, Reg.AX, Reg.BX)

        hw.reg.testharness_set(Reg.BX, Registers.from_int(n_raw, 8))
        div_f64(hw, Reg.AX, Reg.BX)
        term_raw = Registers.to_int(hw.reg.get(Reg.AX))

        hw.reg.testharness_set(Reg.BX, Registers.from_int(acc_raw, 8))
        add_f64(hw, Reg.AX, Reg.BX)
        acc_raw = Registers.to_int(hw.reg.get(Reg.AX))

    return acc_raw


def exp2_frac_core(f: float, is_64: bool = False) -> float:
    """Evaluates 2^f for f in [0.0, 1.0) via Taylor series for exp(f * ln(2))."""
    hw = Hardware()
    if is_64:
        f_raw = Registers.to_int(Registers.from_f64(f))
        res_raw = _eval_exp_frac_f64(hw, f_raw)
        return Registers.to_f64(Registers.from_int(res_raw, 8))
    else:
        f_raw = Registers.to_int(Registers.from_f32(f))
        res_raw = _eval_exp_frac_f32(hw, f_raw)
        return Registers.to_f32(Registers.from_int(res_raw, 4))


def exp_f32(hw: Hardware):
    """Computes natural exponential e^(AL) -> AL (IEEE-754 single precision).

    Synthesizable datapath:
      - Special value checks: NaN, +Inf, -Inf, 0.0.
      - Range reduction: t = x * log2(e) = k + f.
      - Bounds check on k for single-precision overflow (> 127) and underflow (< -126).
      - Table seed query: hw.rom.load_exp2_seed.
      - Fraction evaluation: 2^f = exp(f * ln(2)) via ALU operations.
      - Scale by 2^k: exponent addition exp_acc + k.
    """
    raw = Registers.to_int(hw.reg.get(Reg.AL))
    sign = (raw >> 31) & 1
    exp = (raw >> 23) & 0xFF
    frac = raw & 0x7FFFFF

    if exp == 0xFF:
        hw.clock.tick(2)
        if frac != 0:
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.testharness_set(Reg.AL, Registers.from_int(NAN_F32, 4))
            return
        if sign == 0:
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.testharness_set(Reg.AL, Registers.from_int(POS_INF_F32, 4))
        else:
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.testharness_set(Reg.AL, Registers.from_int(0, 4))
        return

    if exp == 0 and frac == 0:
        hw.clock.tick(2)
        hw.reg.testharness_set(Reg.AL, Registers.from_int(ONE_F32, 4))
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        return

    # Range reduction: t = x * log2(e)
    hw.reg.testharness_set(Reg.BL, Registers.from_int(LOG2E_F32, 4))
    mul_f32(hw, Reg.AL, Reg.BL)
    t_raw = Registers.to_int(hw.reg.get(Reg.AL))

    sign_t = (t_raw >> 31) & 1
    exp_t = (t_raw >> 23) & 0xFF
    frac_t = t_raw & 0x7FFFFF
    unbiased = exp_t - 127

    if unbiased < 0:
        if sign_t == 0:
            k = 0
            f_raw = t_raw
        else:
            k = -1
            hw.reg.testharness_set(Reg.AL, Registers.from_int(t_raw, 4))
            hw.reg.testharness_set(Reg.BL, Registers.from_int(ONE_F32, 4))
            add_f32(hw, Reg.AL, Reg.BL)
            f_raw = Registers.to_int(hw.reg.get(Reg.AL))
    else:
        mant = frac_t | 0x800000
        if unbiased >= 23:
            mag = mant << (unbiased - 23)
            has_frac = False
        else:
            mag = mant >> (23 - unbiased)
            has_frac = (mant & ((1 << (23 - unbiased)) - 1)) != 0
        if sign_t == 1:
            k = -(mag + (1 if has_frac else 0))
        else:
            k = mag
        k_f32_raw = _int_to_f32(hw, k)
        hw.reg.testharness_set(Reg.AL, Registers.from_int(t_raw, 4))
        hw.reg.testharness_set(Reg.BL, Registers.from_int(k_f32_raw, 4))
        sub_f32(hw, Reg.AL, Reg.BL)
        f_raw = Registers.to_int(hw.reg.get(Reg.AL))

    # Overflow / Underflow bounds check for F32
    if k > 127:
        hw.clock.tick(3)
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        hw.reg.testharness_set(Reg.AL, Registers.from_int(POS_INF_F32, 4))
        return
    if k < -126:
        hw.clock.tick(3)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.testharness_set(Reg.AL, Registers.from_int(0, 4))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        return

    # ROM access modeling
    f_frac = (f_raw & 0x7FFFFF) | 0x800000
    idx = (f_frac >> 16) & 0xFF
    _ = hw.rom.load_exp2_seed(idx)
    hw.clock.tick(5)

    acc_raw = _eval_exp_frac_f32(hw, f_raw)

    # Scale by 2^k
    exp_acc = (acc_raw >> 23) & 0xFF
    new_exp = exp_acc + k
    if new_exp >= 255:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        hw.reg.testharness_set(Reg.AL, Registers.from_int(POS_INF_F32, 4))
        return
    if new_exp <= 0:
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.testharness_set(Reg.AL, Registers.from_int(0, 4))
        return

    res_raw = (acc_raw & 0x807FFFFF) | (new_exp << 23)
    hw.reg.testharness_set(Reg.AL, Registers.from_int(res_raw, 4))
    hw.reg.set_flag(StatusFlag.ERR, False)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, False)


def exp_f64(hw: Hardware):
    """Computes natural exponential e^(AX) -> AX (IEEE-754 double precision).

    Synthesizable datapath:
      - Special value checks: NaN, +Inf, -Inf, 0.0.
      - Range reduction: t = x * log2(e) = k + f.
      - Bounds check on k for double-precision overflow (> 1023) and underflow (< -1022).
      - Table seed query: hw.rom.load_exp2_seed.
      - Fraction evaluation: 2^f = exp(f * ln(2)) via ALU operations.
      - Scale by 2^k: exponent addition exp_acc + k.
    """
    raw = Registers.to_int(hw.reg.get(Reg.AX))
    sign = (raw >> 63) & 1
    exp = (raw >> 52) & 0x7FF
    frac = raw & 0x000FFFFFFFFFFFFF

    if exp == 0x7FF:
        hw.clock.tick(3)
        if frac != 0:
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.testharness_set(Reg.AX, Registers.from_int(NAN_F64, 8))
            return
        if sign == 0:
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.testharness_set(Reg.AX, Registers.from_int(POS_INF_F64, 8))
        else:
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.testharness_set(Reg.AX, Registers.from_int(0, 8))
        return

    if exp == 0 and frac == 0:
        hw.clock.tick(3)
        hw.reg.testharness_set(Reg.AX, Registers.from_int(ONE_F64, 8))
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        return

    # Range reduction: t = x * log2(e)
    hw.reg.testharness_set(Reg.BX, Registers.from_int(LOG2E_F64, 8))
    mul_f64(hw, Reg.AX, Reg.BX)
    t_raw = Registers.to_int(hw.reg.get(Reg.AX))

    sign_t = (t_raw >> 63) & 1
    exp_t = (t_raw >> 52) & 0x7FF
    frac_t = t_raw & 0x000FFFFFFFFFFFFF
    unbiased = exp_t - 1023

    if unbiased < 0:
        if sign_t == 0:
            k = 0
            f_raw = t_raw
        else:
            k = -1
            hw.reg.testharness_set(Reg.AX, Registers.from_int(t_raw, 8))
            hw.reg.testharness_set(Reg.BX, Registers.from_int(ONE_F64, 8))
            add_f64(hw, Reg.AX, Reg.BX)
            f_raw = Registers.to_int(hw.reg.get(Reg.AX))
    else:
        mant = frac_t | 0x0010000000000000
        if unbiased >= 52:
            mag = mant << (unbiased - 52)
            has_frac = False
        else:
            mag = mant >> (52 - unbiased)
            has_frac = (mant & ((1 << (52 - unbiased)) - 1)) != 0
        if sign_t == 1:
            k = -(mag + (1 if has_frac else 0))
        else:
            k = mag
        k_f64_raw = _int_to_f64(hw, k)
        hw.reg.testharness_set(Reg.AX, Registers.from_int(t_raw, 8))
        hw.reg.testharness_set(Reg.BX, Registers.from_int(k_f64_raw, 8))
        sub_f64(hw, Reg.AX, Reg.BX)
        f_raw = Registers.to_int(hw.reg.get(Reg.AX))

    # Overflow / Underflow bounds check for F64
    if k > 1023:
        hw.clock.tick(4)
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        hw.reg.testharness_set(Reg.AX, Registers.from_int(POS_INF_F64, 8))
        return
    if k < -1022:
        hw.clock.tick(4)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.testharness_set(Reg.AX, Registers.from_int(0, 8))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        return

    # ROM access modeling
    f_frac = (f_raw & 0x000FFFFFFFFFFFFF) | 0x0010000000000000
    idx = (f_frac >> 45) & 0xFF
    _ = hw.rom.load_exp2_seed(idx)
    hw.clock.tick(10)

    acc_raw = _eval_exp_frac_f64(hw, f_raw)

    # Scale by 2^k
    exp_acc = (acc_raw >> 52) & 0x7FF
    new_exp = exp_acc + k
    if new_exp >= 2047:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        hw.reg.testharness_set(Reg.AX, Registers.from_int(POS_INF_F64, 8))
        return
    if new_exp <= 0:
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.testharness_set(Reg.AX, Registers.from_int(0, 8))
        return

    res_raw = (acc_raw & 0x800FFFFFFFFFFFFF) | (new_exp << 52)
    hw.reg.testharness_set(Reg.AX, Registers.from_int(res_raw, 8))
    hw.reg.set_flag(StatusFlag.ERR, False)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, False)
