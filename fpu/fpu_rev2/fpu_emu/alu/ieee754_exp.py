"""12-Bit Exponent ALU (alu_exp12 / ieee754_exp).

Per SystemDesign.md Section 3.5, Section 4, and Section 7.2:
- Inputs:
  * Primary exponent: EA[11:0]
  * Secondary exponent: EB[11:0]
  * Counter: C[5:0] (for shift count / leading zeros)
  * Hardwired Biases: BIAS_F32 = 127, BIAS_F64 = 1023
- Supported operations:
  * EXP_ADD: EA <- EA + EB (12-bit signed addition, sets V if > +1023, U if < -1022)
  * EXP_SUB: EA <- EA - EB (12-bit signed subtraction, sets V if > +1023, U if < -1022)
  * Mantissa Alignment Exponent Difference:
    C <- min(|EA - EB|, 63), sets CF if EA < EB
  * Multiplication Exponent Addition:
    EA <- EA + EB - BIAS (flags OVERFLOW/ERR if > max_exp, UNDERFLOW if <= 0)
  * Division Exponent Subtraction:
    EA <- EA - EB + BIAS (flags OVERFLOW/ERR if > max_exp, UNDERFLOW if <= 0)
  * Post-Normalization Exponent Update:
    EA <- EA - C (flags UNDERFLOW if <= 0)
  * Single-increment / decrement:
    EA <- EA + 1, EA <- EA - 1
  * IEEE-754 unpack / pack helpers for f32 and f64 mantissa and exponent registers.

VERILOG SYNTHESIS SPEC (MachXO2 LCMXO2-2000HC):
- Module: alu_exp12
- Architecture:
  * 12-bit signed fast carry chain (6 CCU2C dual-ripple slices)
  * Secondary stage for bias addition/subtraction (6 CCU2C slices)
  * Exponent range comparator (> +1023 or < -1022) for overflow/underflow flags
- Fixed Inputs:
  * Primary Operand: Hardwired to EA[11:0] register output (12 bits, NO input MUX)
- Dynamic Inputs:
  * Secondary Operand: 4-to-1 12-bit MUX selecting from [EB[11:0], {6'b0, C[5:0]}, BIAS (127/1023), 12'd1]
  * MUX Hardware Cost: 12 LUT4s (1 LUT4/bit * 12 bits)
- Output Destination:
  * Latched into EA register (12 FFs), or alignment difference latched into C[5:0] (6 FFs)
  * Flags: VF (overflow), UF (underflow), CF latched into STATUS register (3 FFs)
- Hardware Resources (MachXO2-2000):
  * Total LUT4s: ~40 (28 arithmetic/comparator + 12 secondary input MUX)
  * Total CCU2C Carry Slices: 12
  * Flip-Flops (FF): 21 (12 in EA + 6 in C + 3 flags)
  * EBR Blocks: 0
  * DSP Multipliers: 0
- Critical Path & Timing:
  * MUX (0.8 ns) + 2 carry stages (1.2 ns) + comparator (0.8 ns) = 2.8 ns
  * Latency: 1 clock cycle (20 ns at 50 MHz)
"""

from typing import Optional, Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers, HalfSelect
from fpu_emu.fpga_resource import fpga_resource

# 12-bit constants
MASK_12BIT = 0x0FFF
SIGN_12BIT = 0x0800
MOD_12BIT = 0x1000

# IEEE-754 Biases
BIAS_F32 = 127
BIAS_F64 = 1023

# IEEE-754 Maximum Biased Exponents (before Inf/NaN)
MAX_EXP_F32 = 254
MAX_EXP_F64 = 2046

# IEEE Exponent Limits for 12-bit bounds checking
LIMIT_EXP_MAX = 1023
LIMIT_EXP_MIN = -1022

# Counter max limit (6 bits)
MAX_C_SHIFT = 63


def to_signed_12(val: int) -> int:
    """Converts a 12-bit unsigned representation to a Python signed integer."""
    val &= MASK_12BIT
    if val & SIGN_12BIT:
        return val - MOD_12BIT
    return val


def from_signed_12(val: int) -> int:
    """Masks a Python signed integer into a 12-bit unsigned representation."""
    return val & MASK_12BIT


# =============================================================================
# Pure Functional Core Implementations
# =============================================================================
@fpga_resource(
    approach="12-bit Exponent Adder/Subtractor with CCU2C carry chain",
    luts=45,
    slices_ccu2c=6,
    ffs=14,
    delay_ns=2.8,
    cycles=1,
    shared_unit="alu_exp12",
)
def exp_core_add(ea_raw: int, eb_raw: int) -> Tuple[int, bool, bool]:
    """12-bit signed addition EA + EB with IEEE overflow/underflow checks.

    :return: (result_12bit, overflow, underflow)
    """
    ea_s = to_signed_12(ea_raw)
    eb_s = to_signed_12(eb_raw)
    res_s = ea_s + eb_s

    ovf = res_s > LIMIT_EXP_MAX
    uf = res_s < LIMIT_EXP_MIN

    return from_signed_12(res_s), ovf, uf


def exp_core_sub(ea_raw: int, eb_raw: int) -> Tuple[int, bool, bool]:
    """12-bit signed subtraction EA - EB with IEEE overflow/underflow checks.

    :return: (result_12bit, overflow, underflow)
    """
    ea_s = to_signed_12(ea_raw)
    eb_s = to_signed_12(eb_raw)
    res_s = ea_s - eb_s

    ovf = res_s > LIMIT_EXP_MAX
    uf = res_s < LIMIT_EXP_MIN

    return from_signed_12(res_s), ovf, uf


def exp_core_diff(ea_raw: int, eb_raw: int) -> Tuple[int, int, bool]:
    """Exponent difference for mantissa alignment.

    Computes delta = EA - EB.
    :return: (delta_12bit, shift_count, borrow)
      where shift_count = min(|EA - EB|, 63)
      and borrow = True (CF=1) if EA < EB
    """
    ea = ea_raw & MASK_12BIT
    eb = eb_raw & MASK_12BIT
    delta = ea - eb
    borrow = delta < 0
    shift_count = min(abs(delta), MAX_C_SHIFT)

    return from_signed_12(delta), shift_count, borrow


def exp_core_add_mul(
    ea_raw: int, eb_raw: int, bias: int = BIAS_F32
) -> Tuple[int, bool, bool, bool]:
    """Multiplication exponent calculation: EA + EB - BIAS.

    :return: (res_12bit, ovf, uf, err)
    """
    res = (ea_raw & MASK_12BIT) + (eb_raw & MASK_12BIT) - bias
    max_exp = MAX_EXP_F32 if bias == BIAS_F32 else MAX_EXP_F64

    ovf = res > max_exp
    uf = res <= 0
    err = ovf

    return from_signed_12(res), ovf, uf, err


def exp_core_sub_div(
    ea_raw: int, eb_raw: int, bias: int = BIAS_F32
) -> Tuple[int, bool, bool, bool]:
    """Division exponent calculation: EA - EB + BIAS.

    :return: (res_12bit, ovf, uf, err)
    """
    res = (ea_raw & MASK_12BIT) - (eb_raw & MASK_12BIT) + bias
    max_exp = MAX_EXP_F32 if bias == BIAS_F32 else MAX_EXP_F64

    ovf = res > max_exp
    uf = res <= 0
    err = ovf

    return from_signed_12(res), ovf, uf, err


def exp_core_adj_norm(ea_raw: int, shift_count: int) -> Tuple[int, bool]:
    """Post-normalization exponent adjustment: EA - shift_count.

    :return: (res_12bit, uf)
    """
    ea_s = to_signed_12(ea_raw)
    res = ea_s - shift_count
    uf = res <= 0
    return from_signed_12(res), uf


# =============================================================================
# Hardware-Mutating Operations (1 clock cycle latency)
# =============================================================================
def exp_add(hw: Hardware):
    """EXP_ADD: EA <- EA + EB (1 clock cycle)."""
    hw.clock.tick(1)
    res, ovf, uf = exp_core_add(hw.reg.ea, hw.reg.eb)
    hw.reg.ea = res
    hw.reg.set_flag(StatusFlag.OVERFLOW, ovf)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, uf)


def exp_sub(hw: Hardware):
    """EXP_SUB: EA <- EA - EB (1 clock cycle)."""
    hw.clock.tick(1)
    res, ovf, uf = exp_core_sub(hw.reg.ea, hw.reg.eb)
    hw.reg.ea = res
    hw.reg.set_flag(StatusFlag.OVERFLOW, ovf)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, uf)


def exp_diff(hw: Hardware, reg: Reg = Reg.AL):
    """Exponent difference for mantissa alignment: C <- min(|EA - EB|, 63), CF <- (EA < EB or (EA == EB and mant_a < mant_b)), SF <- (sign_a ^ sign_b)."""
    hw.clock.tick(1)
    _, shift_count, borrow = exp_core_diff(hw.reg.ea, hw.reg.eb)
    if hw.reg.ea == hw.reg.eb:
        reg_b = Reg.BX if reg in (Reg.AX, Reg.BX) else Reg.BL
        reg_a = Reg.AX if reg in (Reg.AX, Reg.BX) else Reg.AL
        if reg_a == Reg.AX:
            val_a = Registers.to_int(bytearray(hw.reg._al) + bytearray(hw.reg._ah))
            val_b = Registers.to_int(bytearray(hw.reg._bl) + bytearray(hw.reg._bh))
        else:
            val_a = Registers.to_int(bytearray(hw.reg._al))
            val_b = Registers.to_int(bytearray(hw.reg._bl))
        borrow = val_a < val_b
    hw.reg.c = shift_count
    hw.reg.set_flag(StatusFlag.CARRY, borrow)
    hw.reg.set_flag(StatusFlag.DIFF_SIGN, bool(hw.reg.sign_a ^ hw.reg.sign_b))
    hw.reg.set_flag(StatusFlag.SIGN, bool(hw.reg.sign_a ^ hw.reg.sign_b))


def exp_add_mul(hw: Hardware, bias: int = BIAS_F32):
    """Multiplication exponent addition: EA <- EA + EB - BIAS (1 cycle)."""
    hw.clock.tick(1)
    res, ovf, uf, err = exp_core_add_mul(hw.reg.ea, hw.reg.eb, bias=bias)
    hw.reg.ea = res
    hw.reg.set_flag(StatusFlag.OVERFLOW, ovf)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, uf)
    if err:
        hw.reg.set_flag(StatusFlag.ERR, True)


def exp_sub_div(hw: Hardware, bias: int = BIAS_F32):
    """Division exponent subtraction: EA <- EA - EB + BIAS (1 cycle)."""
    hw.clock.tick(1)
    res, ovf, uf, err = exp_core_sub_div(hw.reg.ea, hw.reg.eb, bias=bias)
    hw.reg.ea = res
    hw.reg.set_flag(StatusFlag.OVERFLOW, ovf)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, uf)
    if err:
        hw.reg.set_flag(StatusFlag.ERR, True)


def exp_adj_norm(hw: Hardware, shift_count: Optional[int] = None):
    """Post-normalization exponent adjustment: EA <- EA - (shift_count or C) (1 cycle)."""
    hw.clock.tick(1)
    count = shift_count if shift_count is not None else hw.reg.c
    res, uf = exp_core_adj_norm(hw.reg.ea, count)
    hw.reg.ea = res
    if uf:
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)


def exp_inc(hw: Hardware):
    """Increments EA by 1 (e.g. On mantissa addition overflow shift-right) (1 cycle)."""
    hw.clock.tick(1)
    hw.reg.ea = (hw.reg.ea + 1) & MASK_12BIT


def exp_dec(hw: Hardware):
    """Decrements EA by 1 (1 cycle)."""
    hw.clock.tick(1)
    hw.reg.ea = (hw.reg.ea - 1) & MASK_12BIT


# =============================================================================
# IEEE-754 Unpack / Pack Primitives
# =============================================================================
def unpack_f32(
    hw: Hardware,
    src: Reg = Reg.AL,
    dst_mantissa: Reg = Reg.AL,
    dst_exp: Reg = Reg.EA,
) -> int:
    """Unpacks IEEE-754 single-precision float from `src` register (1 cycle).

    Extracts:
    - 8-bit exponent into `dst_exp` (EA or EB)
    - 24-bit mantissa left-justified into `dst_mantissa` (AL or BL) with hidden 1 at bit 31
    - Latches sign bit into hw.reg.sign_a (if AL) or hw.reg.sign_b (if BL)
    :return: Sign bit (0 for positive, 1 for negative)
    """
    hw.clock.tick(1)
    if src == Reg.AL:
        hw.reg.set_ha_bus_mux(HalfSelect.LO)
        raw_bytes = hw.reg.read_ha_bus()
    elif src == Reg.AH:
        hw.reg.set_ha_bus_mux(HalfSelect.HI)
        raw_bytes = hw.reg.read_ha_bus()
    else:
        hw.reg.set_hb_bus_mux(HalfSelect.LO, src)
        raw_bytes = hw.reg.read_hb_bus()

    raw_val = Registers.to_int(raw_bytes)
    sign = (raw_val >> 31) & 1
    exp = (raw_val >> 23) & 0xFF
    mantissa = raw_val & 0x007FFFFF

    if exp != 0:
        # Normalized: insert hidden 1 at bit 23 and left-justify to bit 31
        mantissa = (mantissa | (1 << 23)) << 8
    else:
        # Denormal or zero
        mantissa = mantissa << 8

    if dst_exp == Reg.EA:
        hw.reg.ea = exp
    elif dst_exp == Reg.EB:
        hw.reg.eb = exp
    else:
        raise ValueError(f"Invalid destination exponent register: {dst_exp}")

    is_zero = (exp == 0 and mantissa == 0)
    if src == Reg.AL or dst_mantissa == Reg.AL:
        hw.reg.sign_a = sign
        hw.reg.set_flag(StatusFlag.SIGN, sign == 1)
        hw.reg.set_flag(StatusFlag.ZERO, is_zero)
    elif src == Reg.BL or dst_mantissa == Reg.BL:
        hw.reg.sign_b = sign

    hw.reg.set_res_bus(dst_mantissa, Registers.from_int(mantissa, 4))
    return sign


def pack_f32(
    hw: Hardware,
    sign: Optional[int] = None,
    src_mantissa: Reg = Reg.AL,
    src_exp: Reg = Reg.EA,
    dst: Reg = Reg.AL,
):
    """Packs sign, exponent, and mantissa into IEEE-754 single-precision float in `dst` (1 cycle)."""
    hw.clock.tick(1)
    exp = hw.reg.ea if src_exp == Reg.EA else hw.reg.eb
    if src_mantissa == Reg.AL:
        hw.reg.set_ha_bus_mux(HalfSelect.LO)
        mant_bytes = hw.reg.read_ha_bus()
    elif src_mantissa == Reg.AH:
        hw.reg.set_ha_bus_mux(HalfSelect.HI)
        mant_bytes = hw.reg.read_ha_bus()
    else:
        hw.reg.set_hb_bus_mux(HalfSelect.LO, src_mantissa)
        mant_bytes = hw.reg.read_hb_bus()
    mantissa_raw = Registers.to_int(mant_bytes)

    # Determine sign: explicit argument, sign_a, or sign_res
    sign_val = sign if sign is not None else (hw.reg.sign_a if hw.reg.sign_res == 0 else hw.reg.sign_res)

    if exp <= 0 or mantissa_raw == 0:
        hw.reg.set_res_bus(dst, Registers.from_int(0, 4))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        hw.reg.set_flag(StatusFlag.CARRY, False)
        return

    # Strip hidden 1 (at bit 31) and extract 23 fraction bits (bits 30:8)
    mantissa = (mantissa_raw >> 8) & 0x007FFFFF
    exp_clamped = exp & 0xFF
    sign_bit = (sign_val & 1) << 31

    packed = sign_bit | (exp_clamped << 23) | mantissa
    hw.reg.set_res_bus(dst, Registers.from_int(packed, 4))
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, bool(sign_val & 1))
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
    hw.reg.set_flag(StatusFlag.CARRY, False)


def unpack_f64(
    hw: Hardware,
    src: Reg = Reg.AX,
    dst_mantissa: Reg = Reg.AX,
    dst_exp: Reg = Reg.EA,
) -> int:
    """Unpacks IEEE-754 double-precision float from 64-bit `src` compound register (2 cycles).

    Extracts:
    - 11-bit exponent into `dst_exp` (EA or EB)
    - 53-bit mantissa left-justified into `dst_mantissa` (AX or BX) with hidden 1 at bit 63
    :return: Sign bit (0 for positive, 1 for negative)
    """
    hw.clock.tick(1)
    if src == Reg.AX:
        raw_lo = Registers.to_int(hw.reg._al)
        raw_hi = Registers.to_int(hw.reg._ah)
    elif src == Reg.BX:
        raw_lo = Registers.to_int(hw.reg._bl)
        raw_hi = Registers.to_int(hw.reg._bh)
    else:
        raw_lo, raw_hi = 0, 0

    raw_val = raw_lo | (raw_hi << 32)
    sign = (raw_val >> 63) & 1
    exp = (raw_val >> 52) & 0x7FF
    mantissa = raw_val & 0x000FFFFFFFFFFFFF

    if exp != 0:
        # Normalized: insert hidden 1 at bit 52 and left-justify to bit 63
        mantissa = (mantissa | (1 << 52)) << 11
    else:
        mantissa = mantissa << 11

    if dst_exp == Reg.EA:
        hw.reg.ea = exp
    elif dst_exp == Reg.EB:
        hw.reg.eb = exp
    else:
        raise ValueError(f"Invalid destination exponent register: {dst_exp}")

    is_zero = (exp == 0 and mantissa == 0)
    if src == Reg.AX or dst_mantissa == Reg.AX:
        hw.reg.sign_a = sign
        hw.reg.set_flag(StatusFlag.SIGN, sign == 1)
        hw.reg.set_flag(StatusFlag.ZERO, is_zero)
    elif src == Reg.BX or dst_mantissa == Reg.BX:
        hw.reg.sign_b = sign

    mant_bytes = Registers.from_int(mantissa, 8)
    dst_lo = Reg.AL if dst_mantissa == Reg.AX else Reg.BL
    dst_hi = Reg.AH if dst_mantissa == Reg.AX else Reg.BH
    hw.reg.set_res_bus(dst_lo, mant_bytes[0:4])
    hw.clock.tick(1)
    hw.reg.set_res_bus(dst_hi, mant_bytes[4:8])
    return sign


def pack_f64(
    hw: Hardware,
    sign: Optional[int] = None,
    src_mantissa: Reg = Reg.AX,
    src_exp: Reg = Reg.EA,
    dst: Reg = Reg.AX,
):
    """Packs sign, exponent, and mantissa into IEEE-754 double-precision float in `dst` (2 cycles)."""
    hw.clock.tick(1)
    exp = hw.reg.ea if src_exp == Reg.EA else hw.reg.eb
    if src_mantissa == Reg.AX:
        mant_lo = Registers.to_int(hw.reg._al)
        mant_hi = Registers.to_int(hw.reg._ah)
    elif src_mantissa == Reg.BX:
        mant_lo = Registers.to_int(hw.reg._bl)
        mant_hi = Registers.to_int(hw.reg._bh)
    else:
        mant_lo, mant_hi = 0, 0
    mantissa_raw = mant_lo | (mant_hi << 32)

    sign_val = sign if sign is not None else (hw.reg.sign_a if hw.reg.sign_res == 0 else hw.reg.sign_res)

    dst_lo = Reg.AL if dst == Reg.AX else Reg.BL
    dst_hi = Reg.AH if dst == Reg.AX else Reg.BH

    if exp <= 0 or mantissa_raw == 0:
        hw.reg.set_res_bus(dst_lo, Registers.from_int(0, 4))
        hw.clock.tick(1)
        hw.reg.set_res_bus(dst_hi, Registers.from_int(0, 4))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
        hw.reg.set_flag(StatusFlag.CARRY, False)
        return

    # Strip hidden 1 (at bit 63) and extract 52 fraction bits (bits 62:11)
    mantissa = (mantissa_raw >> 11) & 0x000FFFFFFFFFFFFF
    exp_clamped = exp & 0x7FF
    sign_bit = (sign_val & 1) << 63

    packed = sign_bit | (exp_clamped << 52) | mantissa
    packed_bytes = Registers.from_int(packed, 8)
    hw.reg.set_res_bus(dst_lo, packed_bytes[0:4])
    hw.clock.tick(1)
    hw.reg.set_res_bus(dst_hi, packed_bytes[4:8])
    hw.reg.set_flag(StatusFlag.ZERO, False)
    hw.reg.set_flag(StatusFlag.SIGN, bool(sign_val & 1))
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
    hw.reg.set_flag(StatusFlag.CARRY, False)


def swap(hw: Hardware, reg_a: Reg, reg_b: Reg):
    """SWAP reg_a, reg_b: Exchanges two registers and corresponding sign latches."""
    if reg_a in (Reg.AX, Reg.BX, Reg.DX, Reg.FX):
        hw.clock.tick(2)
        if (reg_a == Reg.AX and reg_b == Reg.BX) or (reg_a == Reg.BX and reg_b == Reg.AX):
            hw.reg._al, hw.reg._bl = bytearray(hw.reg._bl), bytearray(hw.reg._al)
            hw.reg._ah, hw.reg._bh = bytearray(hw.reg._bh), bytearray(hw.reg._ah)
            hw.reg.sign_a, hw.reg.sign_b = hw.reg.sign_b, hw.reg.sign_a
    elif reg_a in (Reg.EA, Reg.EB) and reg_b in (Reg.EA, Reg.EB):
        hw.clock.tick(1)
        hw.reg.ea, hw.reg.eb = hw.reg.eb, hw.reg.ea
    else:
        hw.clock.tick(1)
        if (reg_a == Reg.AL and reg_b == Reg.BL) or (reg_a == Reg.BL and reg_b == Reg.AL):
            hw.reg._al, hw.reg._bl = bytearray(hw.reg._bl), bytearray(hw.reg._al)
            hw.reg.sign_a, hw.reg.sign_b = hw.reg.sign_b, hw.reg.sign_a
        elif (reg_a == Reg.AH and reg_b == Reg.BH) or (reg_a == Reg.BH and reg_b == Reg.AH):
            hw.reg._ah, hw.reg._bh = bytearray(hw.reg._bh), bytearray(hw.reg._ah)
