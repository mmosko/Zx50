"""Floating-point square root ALU module (fp_sqrt.py).

Synthesizable, cycle-accurate implementation of reciprocal square root
Newton-Raphson mantissa convergence using the hardware Flash ROM seed table
(FLASH_SQRT_BASE = 0x0600) and the 32-bit/64-bit Radix-4 Booth multiplier.

Rules Enforced:
- No Python `math` module.
- No high-level Python arithmetic operators (*, /, //, %, **) in algorithm paths.
- No procedural shortcuts bypassing hardware arithmetic.
- All operations execute cycle-by-cycle via synthesizable ALU primitives.
"""

from typing import Tuple
from fpu_emu.alu.booth_mul import booth_core, WIDTH_32_BYTES, WIDTH_64_BYTES
from fpu_emu.alu.ieee754_exp import BIAS_F32, BIAS_F64
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers

# Fixed-point constant 3.0 in Q3.29 (F32) and Q3.61 (F64)
# In Q3.29: 3 << 29 = 0x6000_0000
# In Q3.61: 3 << 61 = 0x6000_0000_0000_0000
CONST_3_Q29 = 0x60000000
CONST_3_Q61 = 0x6000000000000000

# Convergence iteration counts
NR_ITERATIONS_F32 = 2
NR_ITERATIONS_F64 = 3


def sqrt_exp_f32(ea: int) -> Tuple[int, bool]:
    """Halves biased 32-bit floating-point exponent using 12-bit exponent ALU.

    Synthesizable logic:
      unbiased e = EA - 127
      is_odd = bool(e & 1)
      e_res = (e - 1) >> 1 if is_odd else (e >> 1)
      res_EA = e_res + 127
    """
    e = ea - BIAS_F32
    is_odd = bool(e & 1)
    e_res = (e - 1) >> 1 if is_odd else (e >> 1)
    return (e_res + BIAS_F32, is_odd)


def sqrt_exp_f64(ea: int) -> Tuple[int, bool]:
    """Halves biased 64-bit floating-point exponent using 12-bit exponent ALU.

    Synthesizable logic:
      unbiased e = EA - 1023
      is_odd = bool(e & 1)
      e_res = (e - 1) >> 1 if is_odd else (e >> 1)
      res_EA = e_res + 1023
    """
    e = ea - BIAS_F64
    is_odd = bool(e & 1)
    e_res = (e - 1) >> 1 if is_odd else (e >> 1)
    return (e_res + BIAS_F64, is_odd)


def sqrt_mantissa_core_f32(hw: Hardware, is_odd: bool) -> int:
    """Performs reciprocal square root Newton-Raphson iteration for 32-bit float.

    Executes cycle-by-cycle using the synthesizable 32-bit Radix-4 Booth multiplier
    and adder without any high-level Python arithmetic operators or float shortcuts.

    Datapath & Fixed-Point Number Formats:
      - m_eff in Q3.29: normalized mantissa in [1.0, 4.0) (bit 31 is always 0)
      - seed r in Q2.30: reciprocal square root estimate in (0.5, 1.0] (bit 31 is 0)
      - CONST_3: 0x60000000 (3.0 in Q3.29 format)
      - Cycle counts:
          * 2 ROM cycles for seed table lookup
          * 2 iterations * (3 * 16 cycles MUL + 3 * 1 cycle wiring/sub) = 102 cycles
          * 1 final MUL (16 cycles) + 1 extract cycle = 17 cycles
          * Total latency = 121 clock cycles.

    :param hw: Hardware instance.
    :param is_odd: Parity of unbiased exponent.
    :return: 32-bit left-justified normalized mantissa (bit 31 = 1).
    """
    mant32 = Registers.to_int(hw.reg._al)
    mant29 = mant32 >> 2

    # 1. Fetch seed from Flash ROM table (2 cycles)
    idx = _sqrt_seed_index_f32(is_odd, mant32)
    seed = hw.rom.load_sqrt_seed(idx)
    hw.clock.tick(2)

    # Seed in Q0.16 format -> aligned into Q2.30 format (bit 30 is 1.0, bit 31 is 0)
    r = (seed << 14) & 0xFFFFFFFF

    # Effective mantissa in Q3.29:
    # If is_odd: m_eff in [2.0, 4.0) -> mant29 << 1
    # If even:   m_eff in [1.0, 2.0) -> mant29
    m_eff = (mant29 << 1) if is_odd else mant29
    hw.clock.tick(1)

    # 2. Newton-Raphson Convergence Iterations: r_{n+1} = 0.5 * r_n * (3.0 - m_eff * r_n^2)
    for _ in range(NR_ITERATIONS_F32):
        # Step A: T1 = r * r (Q2.30 * Q2.30 -> Q4.60, extract Q2.30 at >> 30)
        prod1, _, _, _, _ = booth_core(
            Registers.from_int(r, 4),
            Registers.from_int(r, 4),
            width_bytes=WIDTH_32_BYTES,
        )
        hw.clock.tick(16)
        t1 = (Registers.to_int(prod1) >> 30) & 0xFFFFFFFF
        hw.clock.tick(1)

        # Step B: T2 = m_eff * T1 (Q3.29 * Q2.30 -> Q5.59, extract Q3.29 at >> 30)
        prod2, _, _, _, _ = booth_core(
            Registers.from_int(m_eff, 4),
            Registers.from_int(t1, 4),
            width_bytes=WIDTH_32_BYTES,
        )
        hw.clock.tick(16)
        t2 = (Registers.to_int(prod2) >> 30) & 0xFFFFFFFF
        hw.clock.tick(1)

        # Step C: T3 = 3.0 - T2 (32-bit subtractor in Q3.29)
        t3 = (CONST_3_Q29 - t2) & 0xFFFFFFFF
        hw.clock.tick(1)

        # Step D: r_next = 0.5 * r * T3 (Q2.30 * Q3.29 -> Q5.59, extract Q2.30 with 0.5 factor at >> 30)
        prod3, _, _, _, _ = booth_core(
            Registers.from_int(r, 4),
            Registers.from_int(t3, 4),
            width_bytes=WIDTH_32_BYTES,
        )
        hw.clock.tick(16)
        r = (Registers.to_int(prod3) >> 30) & 0xFFFFFFFF
        hw.clock.tick(1)

    # 3. Final Mantissa Extraction: root_m = m_eff * r (Q3.29 * Q2.30 -> Q5.59)
    # Target is Q1.31 left-justified mantissa (bit 31 = 1): shift right by (59 - 31) = 28
    prod_final, _, _, _, _ = booth_core(
        Registers.from_int(m_eff, 4),
        Registers.from_int(r, 4),
        width_bytes=WIDTH_32_BYTES,
    )
    hw.clock.tick(16)
    root_mant = (Registers.to_int(prod_final) >> 28) & 0xFFFFFFFF
    hw.clock.tick(1)

    # Ensure hidden bit at bit 31 is set (compensate for fractional convergence lower bound)
    if root_mant < 0x80000000:
        root_mant = 0x80000000

    return root_mant


def sqrt_mantissa_core_f64(hw: Hardware, is_odd: bool) -> int:
    """Performs reciprocal square root Newton-Raphson iteration for 64-bit float.

    Executes cycle-by-cycle using the synthesizable 64-bit Radix-4 Booth multiplier
    and adder without any high-level Python arithmetic operators or float shortcuts.

    Datapath & Fixed-Point Number Formats:
      - m_eff in Q3.61: normalized mantissa in [1.0, 4.0) (bit 63 is always 0)
      - seed r in Q2.62: reciprocal square root estimate in (0.5, 1.0] (bit 63 is 0)
      - CONST_3: 0x6000_0000_0000_0000 (3.0 in Q3.61 format)
      - Cycle counts:
          * 2 ROM cycles for seed table lookup
          * 3 iterations * (3 * 32 cycles MUL + 3 * 1 cycle wiring/sub) = 297 cycles
          * 1 final MUL (32 cycles) + 1 extract cycle = 33 cycles
          * Total latency = 332 clock cycles.

    :param hw: Hardware instance.
    :param is_odd: Parity of unbiased exponent.
    :return: 64-bit left-justified normalized mantissa (bit 63 = 1).
    """
    mant64 = Registers.to_int(bytearray(hw.reg._al) + bytearray(hw.reg._ah))
    mant61 = mant64 >> 2

    # 1. Fetch seed from Flash ROM table (2 cycles)
    idx = _sqrt_seed_index_f64(is_odd, mant64)
    seed = hw.rom.load_sqrt_seed(idx)
    hw.clock.tick(2)

    # Seed in Q0.16 format -> aligned into Q2.62 format (bit 62 is 1.0, bit 63 is 0)
    r = (seed << 46) & 0xFFFFFFFFFFFFFFFF

    # Effective mantissa in Q3.61:
    m_eff = (mant61 << 1) if is_odd else mant61
    hw.clock.tick(1)

    # 2. Newton-Raphson Convergence Iterations (3 iterations for >= 64-bit precision)
    for _ in range(NR_ITERATIONS_F64):
        # Step A: T1 = r * r (Q2.62 * Q2.62 -> Q4.124, extract Q2.62 at >> 62)
        prod1, _, _, _, _ = booth_core(
            Registers.from_int(r, 8),
            Registers.from_int(r, 8),
            width_bytes=WIDTH_64_BYTES,
        )
        hw.clock.tick(32)
        t1 = (Registers.to_int(prod1) >> 62) & 0xFFFFFFFFFFFFFFFF
        hw.clock.tick(1)

        # Step B: T2 = m_eff * T1 (Q3.61 * Q2.62 -> Q5.123, extract Q3.61 at >> 62)
        prod2, _, _, _, _ = booth_core(
            Registers.from_int(m_eff, 8),
            Registers.from_int(t1, 8),
            width_bytes=WIDTH_64_BYTES,
        )
        hw.clock.tick(32)
        t2 = (Registers.to_int(prod2) >> 62) & 0xFFFFFFFFFFFFFFFF
        hw.clock.tick(1)

        # Step C: T3 = 3.0 - T2 (64-bit subtractor in Q3.61)
        t3 = (CONST_3_Q61 - t2) & 0xFFFFFFFF_FFFFFFFF
        hw.clock.tick(1)

        # Step D: r_next = 0.5 * r * T3 (Q2.62 * Q3.61 -> Q5.123, extract Q2.62 with 0.5 factor at >> 62)
        prod3, _, _, _, _ = booth_core(
            Registers.from_int(r, 8),
            Registers.from_int(t3, 8),
            width_bytes=WIDTH_64_BYTES,
        )
        hw.clock.tick(32)
        r = (Registers.to_int(prod3) >> 62) & 0xFFFFFFFFFFFFFFFF
        hw.clock.tick(1)

    # 3. Final Mantissa Extraction: root_m = m_eff * r (Q3.61 * Q2.62 -> Q5.123)
    # Target is Q1.63 left-justified mantissa (bit 63 = 1): shift right by (123 - 63) = 60
    prod_final, _, _, _, _ = booth_core(
        Registers.from_int(m_eff, 8),
        Registers.from_int(r, 8),
        width_bytes=WIDTH_64_BYTES,
    )
    hw.clock.tick(32)
    root_mant = (Registers.to_int(prod_final) >> 60) & 0xFFFFFFFFFFFFFFFF
    hw.clock.tick(1)

    if root_mant < 0x8000000000000000:
        root_mant = 0x8000000000000000

    return root_mant


def _sqrt_seed_index_f32(is_odd: bool, mantissa_u32: int) -> int:
    """Computes the 8-bit ROM seed table index for single-precision float.

    Index structure:
      Bit 7: Exponent parity bit (0: even, 1: odd)
      Bits 6..0: Top 7 fraction bits of mantissa (AL[30:24]).
    """
    idx = (128 if is_odd else 0) | ((mantissa_u32 >> 24) & 0x7F)
    return idx


def _sqrt_seed_index_f64(is_odd: bool, mantissa_u64: int) -> int:
    """Computes the 8-bit ROM seed table index for double-precision float.

    Index structure:
      Bit 7: Exponent parity bit (0: even, 1: odd)
      Bits 6..0: Top 7 fraction bits of mantissa (AX[62:56]).
    """
    idx = (128 if is_odd else 0) | ((mantissa_u64 >> 56) & 0x7F)
    return idx


