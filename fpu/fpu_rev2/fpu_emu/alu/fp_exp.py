"""Floating-point exponential (EXP / e^x) ALU module.

Implements range reduction and high-precision evaluation for IEEE-754 F32 and F64:
    e^x = 2^(x * log2(e)) = 2^k * 2^f
where k = floor(x * log2(e)) is the integer exponent shift,
and f in [0.0, 1.0) is evaluated via the hardware ROM Exp2 table (FLASH_EXP2_BASE = 0x0800)
and Taylor polynomial convergence.
"""

import math
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag

LOG2E = 1.44269504088896340735992468100189
LN2 = 0.6931471805599453094172321214581765


def exp2_frac_core(f: float, is_64: bool = False) -> float:
    """Evaluates 2^f for f in [0.0, 1.0) via Taylor series for exp(f * ln(2))."""
    u = f * LN2
    term = 1.0
    acc = 1.0
    terms = 14 if is_64 else 7

    for n in range(1, terms):
        term = term * u / n
        acc += term

    return acc


def exp_f32(hw: Hardware):
    """Computes natural exponential e^(AL) -> AL (IEEE-754 single precision).

    Latency: ~8 clock cycles.
    """
    x = Registers.to_f32(hw.reg.get(Reg.AL))

    # Special values
    if math.isnan(x):
        hw.clock.tick(2)
        hw.reg.set_flag(StatusFlag.ERR, True)
        hw.reg.set(Reg.AL, Registers.from_f32(float("nan")))
        return
    if math.isinf(x):
        hw.clock.tick(2)
        if x > 0:
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.set(Reg.AL, Registers.from_f32(float("inf")))
        else:
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.set(Reg.AL, Registers.from_f32(0.0))
        return
    if x == 0.0:
        hw.clock.tick(2)
        hw.reg.set(Reg.AL, Registers.from_f32(1.0))
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    # Range reduction: t = x * log2(e) = k + f
    t = x * LOG2E
    k = math.floor(t)
    f = t - k

    # Overflow / Underflow bounds check for F32
    if k > 127:
        hw.clock.tick(3)
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        hw.reg.set(Reg.AL, Registers.from_f32(float("inf")))
        return
    if k < -126:
        hw.clock.tick(3)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set(Reg.AL, Registers.from_f32(0.0))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        return

    # ROM access modeling
    idx = int(f * 256.0) & 0xFF
    _ = hw.rom.load_exp2_seed(idx)
    hw.clock.tick(5)

    frac_part = exp2_frac_core(f, is_64=False)
    res = math.ldexp(frac_part, k)

    hw.reg.set(Reg.AL, Registers.from_f32(res))
    hw.reg.set_flag(StatusFlag.ERR, False)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
    hw.reg.set_flag(StatusFlag.ZERO, res == 0.0)
    hw.reg.set_flag(StatusFlag.SIGN, False)


def exp_f64(hw: Hardware):
    """Computes natural exponential e^(AX) -> AX (IEEE-754 double precision).

    Latency: ~14 clock cycles.
    """
    x = Registers.to_f64(hw.reg.get(Reg.AX))

    if math.isnan(x):
        hw.clock.tick(3)
        hw.reg.set_flag(StatusFlag.ERR, True)
        hw.reg.set(Reg.AX, Registers.from_f64(float("nan")))
        return
    if math.isinf(x):
        hw.clock.tick(3)
        if x > 0:
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.ERR, True)
            hw.reg.set(Reg.AX, Registers.from_f64(float("inf")))
        else:
            hw.reg.set_flag(StatusFlag.ZERO, True)
            hw.reg.set(Reg.AX, Registers.from_f64(0.0))
        return
    if x == 0.0:
        hw.clock.tick(3)
        hw.reg.set(Reg.AX, Registers.from_f64(1.0))
        hw.reg.set_flag(StatusFlag.ZERO, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)
        hw.reg.set_flag(StatusFlag.ERR, False)
        return

    t = x * LOG2E
    k = math.floor(t)
    f = t - k

    if k > 1023:
        hw.clock.tick(4)
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        hw.reg.set(Reg.AX, Registers.from_f64(float("inf")))
        return
    if k < -1022:
        hw.clock.tick(4)
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set(Reg.AX, Registers.from_f64(0.0))
        hw.reg.set_flag(StatusFlag.ZERO, True)
        return

    idx = int(f * 256.0) & 0xFF
    _ = hw.rom.load_exp2_seed(idx)
    hw.clock.tick(10)

    frac_part = exp2_frac_core(f, is_64=True)
    res = math.ldexp(frac_part, k)

    hw.reg.set(Reg.AX, Registers.from_f64(res))
    hw.reg.set_flag(StatusFlag.ERR, False)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)
    hw.reg.set_flag(StatusFlag.UNDERFLOW, False)
    hw.reg.set_flag(StatusFlag.ZERO, res == 0.0)
    hw.reg.set_flag(StatusFlag.SIGN, False)
