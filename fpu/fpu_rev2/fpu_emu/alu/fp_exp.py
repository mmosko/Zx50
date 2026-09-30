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


def _read32(hw: Hardware, reg: Reg) -> int:
    return Registers.to_int(getattr(hw.reg, f"_{reg.name.lower()}"))


def _read64(hw: Hardware, reg: Reg) -> int:
    lo = getattr(hw.reg, f"_{reg.name[0].lower()}l")
    hi = getattr(hw.reg, f"_{reg.name[0].lower()}h")
    return Registers.to_int(bytearray(lo) + bytearray(hi))


def _write32(hw: Hardware, reg: Reg, val: int) -> None:
    hw.clock.tick(1)
    hw.reg.set_res_bus(reg, Registers.from_int(val & 0xFFFFFFFF, 4))


def _write64(hw: Hardware, reg: Reg, val: int) -> None:
    hw.clock.tick(1)
    lo_name = reg.name[0] + "L"
    hi_name = reg.name[0] + "H"
    hw.reg.set_res_bus(Reg[lo_name], Registers.from_int(val & 0xFFFFFFFF, 4))
    hw.clock.tick(1)
    hw.reg.set_res_bus(Reg[hi_name], Registers.from_int((val >> 32) & 0xFFFFFFFF, 4))


def _int_to_f32(hw: Hardware, val: int) -> int:
    """Converts a signed integer to IEEE-754 single precision bit pattern using LZC and Shifter."""
    if val == 0:
        return 0
    sign = 1 if val < 0 else 0
    abs_val = (-val if val < 0 else val) & 0xFFFFFFFF

    _write32(hw, Reg.AL, abs_val)
    lz_count = lzc32(hw, Reg.AL)
    msb_pos = 31 - lz_count

    if msb_pos >= 23:
        shift = msb_pos - 23
        lsr32(hw, shift=shift, reg=Reg.AL)
    else:
        shift = 23 - msb_pos
        lsl32(hw, shift=shift, reg=Reg.AL)

    mant = _read32(hw, Reg.AL) & 0x7FFFFF
    exp = 127 + msb_pos
    return (sign << 31) | (exp << 23) | mant


def _int_to_f64(hw: Hardware, val: int) -> int:
    """Converts a signed integer to IEEE-754 double precision bit pattern using LZC and Shifter."""
    if val == 0:
        return 0
    sign = 1 if val < 0 else 0
    abs_val = (-val if val < 0 else val) & 0xFFFFFFFFFFFFFFFF

    _write64(hw, Reg.AX, abs_val)
    lz_count = lzc64(hw, Reg.AX)
    msb_pos = 63 - lz_count

    if msb_pos >= 52:
        shift = msb_pos - 52
        lsr64(hw, shift=shift, reg=Reg.AX)
    else:
        shift = 52 - msb_pos
        lsl64(hw, shift=shift, reg=Reg.AX)

    mant = _read64(hw, Reg.AX) & 0x000FFFFFFFFFFFFF
    exp = 1023 + msb_pos
    return (sign << 63) | (exp << 52) | mant


def _eval_exp_frac_f32(hw: Hardware, f_raw: int) -> int:
    """Evaluates 2^f = exp(f * ln(2)) via ALU primitives (32-bit)."""
    _write32(hw, Reg.AL, f_raw)
    _write32(hw, Reg.BL, LN2_F32)
    mul_f32(hw, Reg.AL, Reg.BL)
    u_raw = _read32(hw, Reg.AL)

    term_raw = ONE_F32
    acc_raw = ONE_F32
    for n_raw in FACTS_F32:
        _write32(hw, Reg.AL, term_raw)
        _write32(hw, Reg.BL, u_raw)
        mul_f32(hw, Reg.AL, Reg.BL)

        _write32(hw, Reg.BL, n_raw)
        div_f32(hw, Reg.AL, Reg.BL)
        term_raw = _read32(hw, Reg.AL)

        _write32(hw, Reg.BL, acc_raw)
        add_f32(hw, Reg.AL, Reg.BL)
        acc_raw = _read32(hw, Reg.AL)

    return acc_raw


def _eval_exp_frac_f64(hw: Hardware, f_raw: int) -> int:
    """Evaluates 2^f = exp(f * ln(2)) via ALU primitives (64-bit)."""
    _write64(hw, Reg.AX, f_raw)
    _write64(hw, Reg.BX, LN2_F64)
    mul_f64(hw, Reg.AX, Reg.BX)
    u_raw = _read64(hw, Reg.AX)

    term_raw = ONE_F64
    acc_raw = ONE_F64
    for n_raw in FACTS_F64:
        _write64(hw, Reg.AX, term_raw)
        _write64(hw, Reg.BX, u_raw)
        mul_f64(hw, Reg.AX, Reg.BX)

        _write64(hw, Reg.BX, n_raw)
        div_f64(hw, Reg.AX, Reg.BX)
        term_raw = _read64(hw, Reg.AX)

        _write64(hw, Reg.BX, acc_raw)
        add_f64(hw, Reg.AX, Reg.BX)
        acc_raw = _read64(hw, Reg.AX)

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
    raw = _read32(hw, Reg.AL)
    sign = (raw >> 31) & 1
    exp = (raw >> 23) & 0xFF
    frac = raw & 0x7FFFFF

    if exp == 0xFF:
        hw.clock.tick(2)
        if frac != 0:
            hw.reg.set_flag(StatusFlag.ERR, True)
            _write32(hw, Reg.AL, NAN_F32)
            return
        if sign == 0:
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.ERR, True)
            _write32(hw, Reg.AL, POS_INF_F32)
        else:
            hw.reg.set_flag(StatusFlag.ZERO, True)
            _write32(hw, Reg.AL, 0)
        return

    if exp == 0 and frac == 0:
        hw.clock.tick(2)
        _write32(hw, Reg.AL, ONE_F32)
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        return

    # Range reduction: t = x * log2(e)
    _write32(hw, Reg.BL, LOG2E_F32)
    mul_f32(hw, Reg.AL, Reg.BL)
    t_raw = _read32(hw, Reg.AL)

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
            _write32(hw, Reg.AL, t_raw)
            _write32(hw, Reg.BL, ONE_F32)
            add_f32(hw, Reg.AL, Reg.BL)
            f_raw = _read32(hw, Reg.AL)
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
        _write32(hw, Reg.AL, t_raw)
        _write32(hw, Reg.BL, k_f32_raw)
        sub_f32(hw, Reg.AL, Reg.BL)
        f_raw = _read32(hw, Reg.AL)

    # Overflow / Underflow bounds check for F32
    if k > 127:
        hw.clock.tick(3)
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        _write32(hw, Reg.AL, POS_INF_F32)
        return
    if k < -126:
        hw.clock.tick(3)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        _write32(hw, Reg.AL, 0)
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
        _write32(hw, Reg.AL, POS_INF_F32)
        return
    if new_exp <= 0:
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set_flag(StatusFlag.ZERO, True)
        _write32(hw, Reg.AL, 0)
        return

    res_raw = (acc_raw & 0x807FFFFF) | (new_exp << 23)
    _write32(hw, Reg.AL, res_raw)
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
    raw = _read64(hw, Reg.AX)
    sign = (raw >> 63) & 1
    exp = (raw >> 52) & 0x7FF
    frac = raw & 0x000FFFFFFFFFFFFF

    if exp == 0x7FF:
        hw.clock.tick(3)
        if frac != 0:
            hw.reg.set_flag(StatusFlag.ERR, True)
            _write64(hw, Reg.AX, NAN_F64)
            return
        if sign == 0:
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.ERR, True)
            _write64(hw, Reg.AX, POS_INF_F64)
        else:
            hw.reg.set_flag(StatusFlag.ZERO, True)
            _write64(hw, Reg.AX, 0)
        return

    if exp == 0 and frac == 0:
        hw.clock.tick(3)
        _write64(hw, Reg.AX, ONE_F64)
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        return

    # Range reduction: t = x * log2(e)
    _write64(hw, Reg.BX, LOG2E_F64)
    mul_f64(hw, Reg.AX, Reg.BX)
    t_raw = _read64(hw, Reg.AX)

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
            _write64(hw, Reg.AX, t_raw)
            _write64(hw, Reg.BX, ONE_F64)
            add_f64(hw, Reg.AX, Reg.BX)
            f_raw = _read64(hw, Reg.AX)
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
        _write64(hw, Reg.AX, t_raw)
        _write64(hw, Reg.BX, k_f64_raw)
        sub_f64(hw, Reg.AX, Reg.BX)
        f_raw = _read64(hw, Reg.AX)

    # Overflow / Underflow bounds check for F64
    if k > 1023:
        hw.clock.tick(4)
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        _write64(hw, Reg.AX, POS_INF_F64)
        return
    if k < -1022:
        hw.clock.tick(4)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        _write64(hw, Reg.AX, 0)
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
        _write64(hw, Reg.AX, POS_INF_F64)
        return
    if new_exp <= 0:
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set_flag(StatusFlag.ZERO, True)
        _write64(hw, Reg.AX, 0)
        return

    res_raw = (acc_raw & 0x800FFFFFFFFFFFFF) | (new_exp << 52)
    _write64(hw, Reg.AX, res_raw)
    hw.reg.set_flag(StatusFlag.ERR, False)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, False)
