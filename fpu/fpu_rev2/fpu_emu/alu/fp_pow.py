"""Floating-point power (POW / x^y) ALU module.

Computes dst <- dst ** src (base = dst, exponent = src) for IEEE-754 single (f32)
and double (f64) precision using synthesizable microcode chaining:
    x^y = exp(y * ln(|x|))
with integer-exponent negative base parity handling, IEEE-754 domain error checking,
and special value processing.

Rules Enforced:
- No Python `math` module.
- No high-level Python arithmetic operators (*, /, //, %, **) in algorithm paths.
- Chained cycle-by-cycle execution via synthesizable ALU primitives.
"""

from fpu_emu.alu.fp_exp import exp_f32, exp_f64
from fpu_emu.alu.fp_ln import ln_f32, ln_f64
from fpu_emu.alu.fp_mul_div import mul_f32, mul_f64
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag

ONE_F32 = 0x3F800000
ONE_F64 = 0x3FF0000000000000
NAN_F32 = 0x7FC00000
NAN_F64 = 0x7FF8000000000000
POS_INF_F32 = 0x7F800000
POS_INF_F64 = 0x7FF0000000000000
NEG_INF_F32 = 0xFF800000
NEG_INF_F64 = 0xFFF0000000000000


def pow_f32(hw: Hardware, dst: Reg = Reg.AL, src: Reg = Reg.BL):
    """Computes dst <- dst ** src for single-precision floats.

    Chains synthesizable primitives: ln_f32 -> mul_f32 -> exp_f32.
    Latency: ~24 clock cycles.
    """
    x_raw = Registers.to_int(hw.reg.get(dst))
    y_raw = Registers.to_int(hw.reg.get(src))

    hw.clock.tick(24)

    # 1. Any number to power 0.0 is 1.0 (IEEE-754)
    if (y_raw & 0x7FFFFFFF) == 0:
        hw.reg.testharness_set(dst, Registers.from_int(ONE_F32, 4))
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        return

    # 2. 1.0 to any power is 1.0
    if x_raw == ONE_F32:
        hw.reg.testharness_set(dst, Registers.from_int(ONE_F32, 4))
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    # 3. Base is 0.0
    if (x_raw & 0x7FFFFFFF) == 0:
        if (y_raw >> 31) & 1:
            # Division by zero: 0^(-k)
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.testharness_set(dst, Registers.from_int(POS_INF_F32, 4))
        else:
            hw.reg.testharness_set(dst, Registers.from_int(0, 4))
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.set_flag(StatusFlag.SIGN, False)
            hw.reg.set_flag(StatusFlag.ERR, False)
        return

    # 4. Base is negative
    sign_x = (x_raw >> 31) & 1
    is_odd = False
    if sign_x:
        exp_y = (y_raw >> 23) & 0xFF
        frac_y = y_raw & 0x7FFFFF
        if exp_y < 127:
            # |y| < 1.0 and non-zero -> non-integer exponent
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.testharness_set(dst, Registers.from_int(NAN_F32, 4))
            return
        elif exp_y >= 150:
            # 150 = 127 + 23: all fractional bits shifted beyond bit 0, integer is even multiple
            is_odd = False
        else:
            shift = 150 - exp_y
            mant_y = frac_y | 0x800000
            if (mant_y & ((1 << shift) - 1)) != 0:
                # Fractional bits are present
                hw.reg.set_flag(StatusFlag.ERR, True)
                hw.reg.testharness_set(dst, Registers.from_int(NAN_F32, 4))
                return
            is_odd = bool((mant_y >> shift) & 1)

    # 5. Compute |x|^y = exp(y * ln(|x|))
    hw.reg.testharness_set(dst, Registers.from_int(x_raw & 0x7FFFFFFF, 4))
    ln_f32(hw)

    hw.reg.testharness_set(src, Registers.from_int(y_raw, 4))
    mul_f32(hw, dst, src)

    exp_f32(hw)

    res_raw = Registers.to_int(hw.reg.get(dst))

    # Apply sign for negative base
    if is_odd and (res_raw & 0x7F800000) != 0:
        res_raw |= 0x80000000
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 4))
        hw.reg.set_flag(StatusFlag.SIGN, True)


def pow_f64(hw: Hardware, dst: Reg = Reg.AX, src: Reg = Reg.BX):
    """Computes dst <- dst ** src for double-precision floats.

    Chains synthesizable primitives: ln_f64 -> mul_f64 -> exp_f64.
    Latency: ~36 clock cycles.
    """
    x_raw = Registers.to_int(hw.reg.get(dst))
    y_raw = Registers.to_int(hw.reg.get(src))

    hw.clock.tick(36)

    # 1. Any number to power 0.0 is 1.0 (IEEE-754)
    if (y_raw & 0x7FFFFFFFFFFFFFFF) == 0:
        hw.reg.testharness_set(dst, Registers.from_int(ONE_F64, 8))
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        return

    # 2. 1.0 to any power is 1.0
    if x_raw == ONE_F64:
        hw.reg.testharness_set(dst, Registers.from_int(ONE_F64, 8))
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    # 3. Base is 0.0
    if (x_raw & 0x7FFFFFFFFFFFFFFF) == 0:
        if (y_raw >> 63) & 1:
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.testharness_set(dst, Registers.from_int(POS_INF_F64, 8))
        else:
            hw.reg.testharness_set(dst, Registers.from_int(0, 8))
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.set_flag(StatusFlag.SIGN, False)
            hw.reg.set_flag(StatusFlag.ERR, False)
        return

    # 4. Base is negative
    sign_x = (x_raw >> 63) & 1
    is_odd = False
    if sign_x:
        exp_y = (y_raw >> 52) & 0x7FF
        frac_y = y_raw & 0x000FFFFFFFFFFFFF
        if exp_y < 1023:
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.testharness_set(dst, Registers.from_int(NAN_F64, 8))
            return
        elif exp_y >= 1075:
            # 1075 = 1023 + 52
            is_odd = False
        else:
            shift = 1075 - exp_y
            mant_y = frac_y | 0x0010000000000000
            if (mant_y & ((1 << shift) - 1)) != 0:
                hw.reg.set_flag(StatusFlag.ERR, True)
                hw.reg.testharness_set(dst, Registers.from_int(NAN_F64, 8))
                return
            is_odd = bool((mant_y >> shift) & 1)

    # 5. Compute |x|^y = exp(y * ln(|x|))
    hw.reg.testharness_set(dst, Registers.from_int(x_raw & 0x7FFFFFFFFFFFFFFF, 8))
    ln_f64(hw)

    hw.reg.testharness_set(src, Registers.from_int(y_raw, 8))
    mul_f64(hw, dst, src)

    exp_f64(hw)

    res_raw = Registers.to_int(hw.reg.get(dst))

    # Apply sign for negative base
    if is_odd and (res_raw & 0x7FF0000000000000) != 0:
        res_raw |= 0x8000000000000000
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 8))
        hw.reg.set_flag(StatusFlag.SIGN, True)
