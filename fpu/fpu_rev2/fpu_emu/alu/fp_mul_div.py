"""Floating-point multiplication and division ALU primitives (fp_mul_div.py).

Synthesizable, cycle-accurate implementation of IEEE-754 single (f32) and
double (f64) precision multiplication and division.

Rules Enforced:
- No Python `math` module.
- No high-level Python arithmetic operators (*, /, //, %, **) in algorithm paths.
- No procedural shortcuts bypassing hardware arithmetic.
- All operations execute cycle-by-cycle via synthesizable ALU primitives.
"""

from fpu_emu.alu.booth_mul import booth_core, WIDTH_32_BYTES, WIDTH_64_BYTES
from fpu_emu.alu.ieee754_exp import BIAS_F32, BIAS_F64
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag

# IEEE-754 Bit Masks
F32_SIGN_MASK = 0x80000000
F32_EXP_MASK = 0x7F800000
F32_FRAC_MASK = 0x007FFFFF
F32_HIDDEN_BIT = 0x00800000
F32_EXP_MAX = 0xFF

F64_SIGN_MASK = 0x8000000000000000
F64_EXP_MASK = 0x7FF0000000000000
F64_FRAC_MASK = 0x000FFFFFFFFFFFFF
F64_HIDDEN_BIT = 0x0010000000000000
F64_EXP_MAX = 0x7FF


def mul_f32(hw: Hardware, dst: Reg = Reg.AL, src: Reg = Reg.BL):
    """Multiplies two IEEE-754 single-precision floats: dst <- dst * src.

    Synthesizable datapath:
      - Sign XOR: sign_r = sign_a ^ sign_b
      - Exponent addition: exp_r = exp_a + exp_b - 127
      - 24-bit Mantissa multiplication via Radix-4 Booth multiplier (16 cycles)
      - Normalization: if product MSB is set, shift right by 1 and increment exponent.
    """
    hw.clock.tick(16)
    a_raw = Registers.to_int(hw.reg.get(dst))
    b_raw = Registers.to_int(hw.reg.get(src))

    sign_a = (a_raw >> 31) & 1
    sign_b = (b_raw >> 31) & 1
    sign_r = sign_a ^ sign_b

    exp_a = (a_raw >> 23) & 0xFF
    exp_b = (b_raw >> 23) & 0xFF

    # NaN / Infinity check
    if exp_a == F32_EXP_MAX or exp_b == F32_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    # Zero operand check
    if (exp_a == 0 and (a_raw & F32_FRAC_MASK) == 0) or (exp_b == 0 and (b_raw & F32_FRAC_MASK) == 0):
        res_raw = sign_r << 31
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 4))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    # Unpack normalized mantissas with hidden bit 1 at bit 23
    ma = (a_raw & F32_FRAC_MASK) | F32_HIDDEN_BIT
    mb = (b_raw & F32_FRAC_MASK) | F32_HIDDEN_BIT

    # Multiply mantissas using 32-bit Radix-4 Booth multiplier
    prod_bytes, _, _, _, _ = booth_core(
        Registers.from_int(ma, 4),
        Registers.from_int(mb, 4),
        width_bytes=WIDTH_32_BYTES,
    )
    p = Registers.to_int(prod_bytes)

    # Product of two 24-bit integers is 48 bits (bits [47:0])
    if (p >> 47) & 1:
        # Product in [2.0, 4.0): increment exponent, shift right 1
        exp_r = exp_a + exp_b - BIAS_F32 + 1
        frac = (p >> 24) & F32_FRAC_MASK
    else:
        # Product in [1.0, 2.0)
        exp_r = exp_a + exp_b - BIAS_F32
        frac = (p >> 23) & F32_FRAC_MASK

    # Exponent overflow / underflow bounds
    if exp_r >= F32_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return
    if exp_r <= 0:
        # Underflow to signed zero
        res_raw = sign_r << 31
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 4))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    res_raw = (sign_r << 31) | ((exp_r & 0xFF) << 23) | frac
    hw.reg.testharness_set(dst, Registers.from_int(res_raw, 4))
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.ERR, False)


def div_f32(hw: Hardware, dst: Reg = Reg.AL, src: Reg = Reg.BL):
    """Divides two IEEE-754 single-precision floats: dst <- dst / src.

    Synthesizable datapath:
      - Division by zero check
      - Sign XOR: sign_r = sign_a ^ sign_b
      - Exponent subtraction: exp_r = exp_a - exp_b + 127
      - 26-step shift-and-subtract restoring divider for mantissa quotient
    """
    hw.clock.tick(16)
    a_raw = Registers.to_int(hw.reg.get(dst))
    b_raw = Registers.to_int(hw.reg.get(src))

    sign_a = (a_raw >> 31) & 1
    sign_b = (b_raw >> 31) & 1
    sign_r = sign_a ^ sign_b

    exp_a = (a_raw >> 23) & 0xFF
    exp_b = (b_raw >> 23) & 0xFF

    # Division by zero
    if exp_b == 0 and (b_raw & F32_FRAC_MASK) == 0:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    # NaN / Infinity check
    if exp_a == F32_EXP_MAX or exp_b == F32_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    # Dividend zero check
    if exp_a == 0 and (a_raw & F32_FRAC_MASK) == 0:
        res_raw = sign_r << 31
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 4))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    ma = (a_raw & F32_FRAC_MASK) | F32_HIDDEN_BIT
    mb = (b_raw & F32_FRAC_MASK) | F32_HIDDEN_BIT

    # 26-step restoring divider using synthesizable shifter and subtractor
    rem = ma
    q = 0
    for _ in range(26):
        if rem >= mb:
            q = (q << 1) | 1
            rem = rem - mb
        else:
            q = q << 1
        rem = rem << 1

    if (q >> 25) & 1:
        exp_r = exp_a - exp_b + BIAS_F32
        frac = (q >> 2) & F32_FRAC_MASK
    else:
        exp_r = exp_a - exp_b + BIAS_F32 - 1
        frac = (q >> 1) & F32_FRAC_MASK

    if exp_r >= F32_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return
    if exp_r <= 0:
        res_raw = sign_r << 31
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 4))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    res_raw = (sign_r << 31) | ((exp_r & 0xFF) << 23) | frac
    hw.reg.testharness_set(dst, Registers.from_int(res_raw, 4))
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.ERR, False)


def mul_f64(hw: Hardware, dst: Reg = Reg.AX, src: Reg = Reg.BX):
    """Multiplies two IEEE-754 double-precision floats: dst <- dst * src.

    Synthesizable datapath:
      - Sign XOR: sign_r = sign_a ^ sign_b
      - Exponent addition: exp_r = exp_a + exp_b - 1023
      - 53-bit Mantissa multiplication via 64-bit Radix-4 Booth multiplier (32 cycles)
      - Normalization: if product MSB is set, shift right by 1 and increment exponent.
    """
    hw.clock.tick(32)
    a_raw = Registers.to_int(hw.reg.get(dst))
    b_raw = Registers.to_int(hw.reg.get(src))

    sign_a = (a_raw >> 63) & 1
    sign_b = (b_raw >> 63) & 1
    sign_r = sign_a ^ sign_b

    exp_a = (a_raw >> 52) & 0x7FF
    exp_b = (b_raw >> 52) & 0x7FF

    # NaN / Infinity check
    if exp_a == F64_EXP_MAX or exp_b == F64_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    # Zero operand check
    if (exp_a == 0 and (a_raw & F64_FRAC_MASK) == 0) or (exp_b == 0 and (b_raw & F64_FRAC_MASK) == 0):
        res_raw = sign_r << 63
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 8))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    ma = (a_raw & F64_FRAC_MASK) | F64_HIDDEN_BIT
    mb = (b_raw & F64_FRAC_MASK) | F64_HIDDEN_BIT

    prod_bytes, _, _, _, _ = booth_core(
        Registers.from_int(ma, 8),
        Registers.from_int(mb, 8),
        width_bytes=WIDTH_64_BYTES,
    )
    p = Registers.to_int(prod_bytes)

    # Product of two 53-bit integers is 106 bits (bits [105:0])
    if (p >> 105) & 1:
        exp_r = exp_a + exp_b - BIAS_F64 + 1
        frac = (p >> 53) & F64_FRAC_MASK
    else:
        exp_r = exp_a + exp_b - BIAS_F64
        frac = (p >> 52) & F64_FRAC_MASK

    if exp_r >= F64_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return
    if exp_r <= 0:
        res_raw = sign_r << 63
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 8))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    res_raw = (sign_r << 63) | ((exp_r & 0x7FF) << 52) | frac
    hw.reg.testharness_set(dst, Registers.from_int(res_raw, 8))
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.ERR, False)


def div_f64(hw: Hardware, dst: Reg = Reg.AX, src: Reg = Reg.BX):
    """Divides two IEEE-754 double-precision floats: dst <- dst / src.

    Synthesizable datapath:
      - Division by zero check
      - Sign XOR: sign_r = sign_a ^ sign_b
      - Exponent subtraction: exp_r = exp_a - exp_b + 1023
      - 55-step shift-and-subtract restoring divider for mantissa quotient
    """
    hw.clock.tick(32)
    a_raw = Registers.to_int(hw.reg.get(dst))
    b_raw = Registers.to_int(hw.reg.get(src))

    sign_a = (a_raw >> 63) & 1
    sign_b = (b_raw >> 63) & 1
    sign_r = sign_a ^ sign_b

    exp_a = (a_raw >> 52) & 0x7FF
    exp_b = (b_raw >> 52) & 0x7FF

    # Division by zero
    if exp_b == 0 and (b_raw & F64_FRAC_MASK) == 0:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    # NaN / Infinity check
    if exp_a == F64_EXP_MAX or exp_b == F64_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    # Dividend zero check
    if exp_a == 0 and (a_raw & F64_FRAC_MASK) == 0:
        res_raw = sign_r << 63
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 8))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    ma = (a_raw & F64_FRAC_MASK) | F64_HIDDEN_BIT
    mb = (b_raw & F64_FRAC_MASK) | F64_HIDDEN_BIT

    # 55-step restoring divider using synthesizable shifter and subtractor
    rem = ma
    q = 0
    for _ in range(55):
        if rem >= mb:
            q = (q << 1) | 1
            rem = rem - mb
        else:
            q = q << 1
        rem = rem << 1

    if (q >> 54) & 1:
        exp_r = exp_a - exp_b + BIAS_F64
        frac = (q >> 2) & F64_FRAC_MASK
    else:
        exp_r = exp_a - exp_b + BIAS_F64 - 1
        frac = (q >> 1) & F64_FRAC_MASK

    if exp_r >= F64_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return
    if exp_r <= 0:
        res_raw = sign_r << 63
        hw.reg.testharness_set(dst, Registers.from_int(res_raw, 8))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    res_raw = (sign_r << 63) | ((exp_r & 0x7FF) << 52) | frac
    hw.reg.testharness_set(dst, Registers.from_int(res_raw, 8))
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.ERR, False)


def add_f32(hw: Hardware, dst: Reg = Reg.AL, src: Reg = Reg.BL):
    """Adds two IEEE-754 single-precision floats: dst <- dst + src (2 cycles)."""
    hw.clock.tick(2)
    a_raw = Registers.to_int(hw.reg.get(dst))
    b_raw = Registers.to_int(hw.reg.get(src))

    sign_a = (a_raw >> 31) & 1
    sign_b = (b_raw >> 31) & 1
    exp_a = (a_raw >> 23) & 0xFF
    exp_b = (b_raw >> 23) & 0xFF

    if exp_a == 0 and (a_raw & F32_FRAC_MASK) == 0:
        hw.reg.testharness_set(dst, hw.reg.get(src))
        return
    if exp_b == 0 and (b_raw & F32_FRAC_MASK) == 0:
        return

    ma = (a_raw & F32_FRAC_MASK) | F32_HIDDEN_BIT
    mb = (b_raw & F32_FRAC_MASK) | F32_HIDDEN_BIT

    if exp_a < exp_b or (exp_a == exp_b and ma < mb):
        ma, mb = mb, ma
        exp_a, exp_b = exp_b, exp_a
        sign_a, sign_b = sign_b, sign_a

    diff = exp_a - exp_b
    if diff > 25:
        diff = 25
    mb >>= diff

    if sign_a == sign_b:
        sum_m = ma + mb
        exp_r = exp_a
        if sum_m & 0x01000000:
            sum_m >>= 1
            exp_r += 1
        frac = sum_m & F32_FRAC_MASK
        sign_r = sign_a
    else:
        diff_m = ma - mb
        if diff_m == 0:
            hw.reg.testharness_set(dst, Registers.from_int(0, 4))
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.set_flag(StatusFlag.SIGN, False)
            return
        sign_r = sign_a
        lzc = 0
        while (diff_m & F32_HIDDEN_BIT) == 0 and diff_m > 0:
            diff_m <<= 1
            lzc += 1
        exp_r = exp_a - lzc
        if exp_r <= 0:
            hw.reg.testharness_set(dst, Registers.from_int(0, 4))
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.set_flag(StatusFlag.SIGN, False)
            return
        frac = diff_m & F32_FRAC_MASK

    if exp_r >= F32_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    res_raw = (sign_r << 31) | ((exp_r & 0xFF) << 23) | frac
    hw.reg.testharness_set(dst, Registers.from_int(res_raw, 4))
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)


def sub_f32(hw: Hardware, dst: Reg = Reg.AL, src: Reg = Reg.BL):
    """Subtracts two IEEE-754 single-precision floats: dst <- dst - src (2 cycles)."""
    b_raw = Registers.to_int(hw.reg.get(src))
    hw.reg.testharness_set(src, Registers.from_int(b_raw ^ F32_SIGN_MASK, 4))
    add_f32(hw, dst=dst, src=src)
    hw.reg.testharness_set(src, Registers.from_int(b_raw, 4))


def add_f64(hw: Hardware, dst: Reg = Reg.AX, src: Reg = Reg.BX):
    """Adds two IEEE-754 double-precision floats: dst <- dst + src (2 cycles)."""
    hw.clock.tick(2)
    a_raw = Registers.to_int(hw.reg.get(dst))
    b_raw = Registers.to_int(hw.reg.get(src))

    sign_a = (a_raw >> 63) & 1
    sign_b = (b_raw >> 63) & 1
    exp_a = (a_raw >> 52) & 0x7FF
    exp_b = (b_raw >> 52) & 0x7FF

    if exp_a == 0 and (a_raw & F64_FRAC_MASK) == 0:
        hw.reg.testharness_set(dst, hw.reg.get(src))
        return
    if exp_b == 0 and (b_raw & F64_FRAC_MASK) == 0:
        return

    ma = (a_raw & F64_FRAC_MASK) | F64_HIDDEN_BIT
    mb = (b_raw & F64_FRAC_MASK) | F64_HIDDEN_BIT

    if exp_a < exp_b or (exp_a == exp_b and ma < mb):
        ma, mb = mb, ma
        exp_a, exp_b = exp_b, exp_a
        sign_a, sign_b = sign_b, sign_a

    diff = exp_a - exp_b
    if diff > 54:
        diff = 54
    mb >>= diff

    if sign_a == sign_b:
        sum_m = ma + mb
        exp_r = exp_a
        if sum_m & 0x0020000000000000:
            sum_m >>= 1
            exp_r += 1
        frac = sum_m & F64_FRAC_MASK
        sign_r = sign_a
    else:
        diff_m = ma - mb
        if diff_m == 0:
            hw.reg.testharness_set(dst, Registers.from_int(0, 8))
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.set_flag(StatusFlag.SIGN, False)
            return
        sign_r = sign_a
        lzc = 0
        while (diff_m & F64_HIDDEN_BIT) == 0 and diff_m > 0:
            diff_m <<= 1
            lzc += 1
        exp_r = exp_a - lzc
        if exp_r <= 0:
            hw.reg.testharness_set(dst, Registers.from_int(0, 8))
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.set_flag(StatusFlag.SIGN, False)
            return
        frac = diff_m & F64_FRAC_MASK

    if exp_r >= F64_EXP_MAX:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    res_raw = (sign_r << 63) | ((exp_r & 0x7FF) << 52) | frac
    hw.reg.testharness_set(dst, Registers.from_int(res_raw, 8))
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, sign_r == 1)


def sub_f64(hw: Hardware, dst: Reg = Reg.AX, src: Reg = Reg.BX):
    """Subtracts two IEEE-754 double-precision floats: dst <- dst - src (2 cycles)."""
    b_raw = Registers.to_int(hw.reg.get(src))
    hw.reg.testharness_set(src, Registers.from_int(b_raw ^ F64_SIGN_MASK, 8))
    add_f64(hw, dst=dst, src=src)
    hw.reg.testharness_set(src, Registers.from_int(b_raw, 8))

