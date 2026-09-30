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


def pow_f32(hw: Hardware, dst: Reg = Reg.AL, src: Reg = Reg.BL):
    """Computes dst <- dst ** src for single-precision floats.

    Chains synthesizable primitives: ln_f32 -> mul_f32 -> exp_f32.
    Latency: ~24 clock cycles.
    """
    x_raw = _read32(hw, dst)
    y_raw = _read32(hw, src)

    hw.clock.tick(24)

    # 1. Any number to power 0.0 is 1.0 (IEEE-754)
    if (y_raw & 0x7FFFFFFF) == 0:
        _write32(hw, dst, ONE_F32)
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        return

    # 2. 1.0 to any power is 1.0
    if x_raw == ONE_F32:
        _write32(hw, dst, ONE_F32)
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
            _write32(hw, dst, POS_INF_F32)
        else:
            _write32(hw, dst, 0)
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
            _write32(hw, dst, NAN_F32)
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
                _write32(hw, dst, NAN_F32)
                return
            is_odd = bool((mant_y >> shift) & 1)

    # 5. Compute |x|^y = exp(y * ln(|x|))
    _write32(hw, dst, x_raw & 0x7FFFFFFF)
    ln_f32(hw)

    _write32(hw, src, y_raw)
    mul_f32(hw, dst, src)

    exp_f32(hw)

    res_raw = _read32(hw, dst)

    # Apply sign for negative base
    if is_odd and (res_raw & 0x7F800000) != 0:
        res_raw |= 0x80000000
        _write32(hw, dst, res_raw)
        hw.reg.set_flag(StatusFlag.SIGN, True)


def pow_f64(hw: Hardware, dst: Reg = Reg.AX, src: Reg = Reg.BX):
    """Computes dst <- dst ** src for double-precision floats.

    Chains synthesizable primitives: ln_f64 -> mul_f64 -> exp_f64.
    Latency: ~36 clock cycles.
    """
    x_raw = _read64(hw, dst)
    y_raw = _read64(hw, src)

    hw.clock.tick(36)

    # 1. Any number to power 0.0 is 1.0 (IEEE-754)
    if (y_raw & 0x7FFFFFFFFFFFFFFF) == 0:
        _write64(hw, dst, ONE_F64)
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        return

    # 2. 1.0 to any power is 1.0
    if x_raw == ONE_F64:
        _write64(hw, dst, ONE_F64)
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    # 3. Base is 0.0
    if (x_raw & 0x7FFFFFFFFFFFFFFF) == 0:
        if (y_raw >> 63) & 1:
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            _write64(hw, dst, POS_INF_F64)
        else:
            _write64(hw, dst, 0)
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
            _write64(hw, dst, NAN_F64)
            return
        elif exp_y >= 1075:
            # 1075 = 1023 + 52
            is_odd = False
        else:
            shift = 1075 - exp_y
            mant_y = frac_y | 0x0010000000000000
            if (mant_y & ((1 << shift) - 1)) != 0:
                hw.reg.set_flag(StatusFlag.ERR, True)
                _write64(hw, dst, NAN_F64)
                return
            is_odd = bool((mant_y >> shift) & 1)

    # 5. Compute |x|^y = exp(y * ln(|x|))
    _write64(hw, dst, x_raw & 0x7FFFFFFFFFFFFFFF)
    ln_f64(hw)

    _write64(hw, src, y_raw)
    mul_f64(hw, dst, src)

    exp_f64(hw)

    res_raw = _read64(hw, dst)

    # Apply sign for negative base
    if is_odd and (res_raw & 0x7FF0000000000000) != 0:
        res_raw |= 0x8000000000000000
        _write64(hw, dst, res_raw)
        hw.reg.set_flag(StatusFlag.SIGN, True)
