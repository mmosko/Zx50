"""Floating-point square root ALU module.

Implements exponent scaling and reciprocal square root Newton-Raphson mantissa
convergence using the hardware Flash ROM seed table (FLASH_SQRT_BASE = 0x0600).
"""

import math
from typing import Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg
from fpu_emu.alu.fp_exp import BIAS_F32, BIAS_F64

# Convergence iterations: 2 iterations give >= 32 bits (F32), 3 iterations give >= 64 bits (F64)
NR_ITERATIONS_F32 = 2
NR_ITERATIONS_F64 = 3


def sqrt_exp_f32(ea: int) -> Tuple[int, bool]:
    """Halves biased 32-bit floating-point exponent.

    Formula:
        unbiased e = EA - 127
        if e is odd:
            res_e = (e - 1) // 2
            is_odd = True
        else:
            res_e = e // 2
            is_odd = False
        res_EA = res_e + 127

    :param ea: 12-bit biased exponent EA.
    :return: (new_ea, is_odd)
    """
    e = ea - BIAS_F32
    is_odd = (e % 2 != 0)
    e_res = (e - 1) // 2 if is_odd else e // 2
    return (e_res + BIAS_F32, is_odd)


def sqrt_exp_f64(ea: int) -> Tuple[int, bool]:
    """Halves biased 64-bit floating-point exponent.

    :param ea: 12-bit biased exponent EA.
    :return: (new_ea, is_odd)
    """
    e = ea - BIAS_F64
    is_odd = (e % 2 != 0)
    e_res = (e - 1) // 2 if is_odd else e // 2
    return (e_res + BIAS_F64, is_odd)


def sqrt_seed_index_f32(is_odd: bool, mantissa_u32: int) -> int:
    """Computes the 8-bit ROM seed table index for single-precision float.

    Index structure:
      Bit 7: Exponent parity bit (0: even, 1: odd)
      Bits 6..0: Top 7 fraction bits of mantissa (AL[30:24]).
    """
    idx = (128 if is_odd else 0) | ((mantissa_u32 >> 24) & 0x7F)
    return idx


def sqrt_seed_index_f64(is_odd: bool, mantissa_u64: int) -> int:
    """Computes the 8-bit ROM seed table index for double-precision float.

    Index structure:
      Bit 7: Exponent parity bit (0: even, 1: odd)
      Bits 6..0: Top 7 fraction bits of mantissa (AX[62:56]).
    """
    idx = (128 if is_odd else 0) | ((mantissa_u64 >> 56) & 0x7F)
    return idx


def sqrt_mantissa_core_f32(hw: Hardware, is_odd: bool) -> int:
    """Performs reciprocal square root Newton-Raphson iteration for 32-bit float.

    Reads operand mantissa from AL, fetches 16-bit seed from ROM, executes 2 iterations,
    and returns the 32-bit normalized mantissa (with hidden bit at bit 31).

    :param hw: Hardware instance.
    :param is_odd: Parity of exponent.
    :return: 32-bit left-justified normalized mantissa.
    """
    from fpu_emu.memory.registers import Registers
    mantissa_u32 = Registers.to_int(hw.reg.get(Reg.AL))
    frac = (mantissa_u32 & 0x7FFFFFFF) / (2.0**31)
    m = 1.0 + frac

    m_eff = 2.0 * m if is_odd else m
    idx = sqrt_seed_index_f32(is_odd, mantissa_u32)
    seed = hw.rom.load_sqrt_seed(idx)
    r = seed / 65536.0

    # 2 Newton-Raphson iterations: r_{n+1} = 0.5 * r_n * (3.0 - m_eff * r_n^2)
    for _ in range(NR_ITERATIONS_F32):
        r = 0.5 * r * (3.0 - m_eff * r * r)

    root_m = m_eff * r
    # root_m is in [1.0, 2.0). Map back to 32-bit left-justified mantissa (bit 31 = 1)
    frac_val = max(0.0, min(1.0 - 2.0**-24, root_m - 1.0))
    res_mantissa = 0x80000000 | (int(round(frac_val * (2.0**23))) << 8)
    return res_mantissa


def sqrt_mantissa_core_f64(hw: Hardware, is_odd: bool) -> int:
    """Performs reciprocal square root Newton-Raphson iteration for 64-bit float.

    Reads operand mantissa from AX, fetches 16-bit seed from ROM, executes 3 iterations,
    and returns the 64-bit normalized mantissa (with hidden bit at bit 63).

    :param hw: Hardware instance.
    :param is_odd: Parity of exponent.
    :return: 64-bit left-justified normalized mantissa.
    """
    from fpu_emu.memory.registers import Registers
    mantissa_u64 = Registers.to_int(hw.reg.get(Reg.AX))
    frac = (mantissa_u64 & 0x7FFFFFFFFFFFFFFF) / (2.0**63)
    m = 1.0 + frac

    m_eff = 2.0 * m if is_odd else m
    idx = sqrt_seed_index_f64(is_odd, mantissa_u64)
    seed = hw.rom.load_sqrt_seed(idx)
    r = seed / 65536.0

    # 3 Newton-Raphson iterations: r_{n+1} = 0.5 * r_n * (3.0 - m_eff * r_n^2)
    for _ in range(NR_ITERATIONS_F64):
        r = 0.5 * r * (3.0 - m_eff * r * r)

    root_m = m_eff * r
    # root_m is in [1.0, 2.0). Map back to 64-bit left-justified mantissa (bit 63 = 1)
    frac_val = max(0.0, min(1.0 - 2.0**-53, root_m - 1.0))
    res_mantissa = 0x8000000000000000 | (int(round(frac_val * (2.0**52))) << 11)
    return res_mantissa
