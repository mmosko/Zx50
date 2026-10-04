"""Radix-4 Modified Booth Multiplier primitive (alu_booth_mul).

Per SystemDesign.md Section 3.6, Section 3.8, and Section 4:
- Hardware 2's complement multiplication retiring 2 bits per clock cycle.
- Inputs:
  * Multiplicand M: BL (32-bit) or BX (64-bit)
  * Multiplier Q: AL (32-bit) or AX (64-bit)
- Execution cycles:
  * 32-bit: 16 clock cycles -> produces 64-bit product in AX = {AH, AL}
  * 64-bit: 32 clock cycles -> produces 128-bit product in {DX, AX} = {DH, DL, AH, AL}
- Flag updates:
  * ZF: Set to 1 if entire product is 0, cleared otherwise
  * SF: Set to 1 if MSB of product is 1, cleared otherwise
  * CF: Cleared to 0
  * VF: Set to 1 if product overflows the source integer width
        (high half is not sign extension of low half)

VERILOG SYNTHESIS SPEC (MachXO2 LCMXO2-2000HC):
- Module: alu_booth_mul (iterative state machine)
- Architecture:
  * MachXO2-2000 has ZERO DSP slices / hard multipliers; multiplication is synthesized entirely in PFU logic.
  * Radix-4 Booth recoder (retires 2 bits per cycle).
  * Multiplicand selector (0, +/- M, +/- 2M) via 5:1 MUX.
  * Partial-product accumulator adder using dedicated MachXO2 CCU2C fast carry-chains.
  * Internal combined shift-right register {Accumulator P, Multiplier Q, Q_prev}.
    When multiplication finishes, shift clock-enable is deactivated. The 64-bit (or 128-bit)
    product remains latched in these internal FFs throughout the writeback phase.
  * 32-bit Output Multiplexer (booth_out_sel):
    Gates one 32-bit slice of {P, Q} onto the 32-bit RES_BUS[31:0] per clock cycle.
    Because {P, Q} are dedicated internal FFs, modifying target registers in the register file
    (AL, AH, DL, DH) introduces ZERO combinational feedback into the multiplier.
- Inputs:
  * Multiplier Q: Connected to HA_BUS[31:0] (from HA 2:1 selector: AL or AH)
  * Multiplicand M: Connected to HB_BUS[31:0] (from HB 8:1 selector: BL, BH, DL, DH, FL, FH, AL, AH)
  * Note: Input selection MUXes reside in the shared bus infrastructure (80 LUT4s total).
- Output Destination:
  * Drives RES_BUS[31:0] -> Latching steered to AL, AH, DL, DH via Clock Enables (WE_AL, WE_AH, WE_DL, WE_DH)
  * Flags: ZF, SF, VF latched into STATUS register (3 FFs)
- Hardware Resources (MachXO2-2000):
  * 32-Bit Booth Core:
    - 66-bit shift register {P[32:0], Q[31:0], q_-1}: 66 FFs
    - 34-bit CCU2C adder: 17 slices
    - Booth recoder & MUX logic: ~57 LUT4s
    - 32-bit 2:1 output MUX (booth_out_sel): 16 LUT4s
    - Cycle counter & flags: 9 FFs, 4 LUT4s
    - Total 32-bit: ~77 LUT4s, 17 CCU2C slices, 75 FFs
  * 64-Bit Booth Core:
    - 130-bit shift register {P[64:0], Q[63:0], q_-1}: 130 FFs
    - 66-bit CCU2C adder: 33 slices
    - Booth recoder & MUX logic: ~105 LUT4s
    - 32-bit 4:1 output MUX (booth_out_sel): 32 LUT4s
    - Cycle counter & flags: 10 FFs, 4 LUT4s
    - Total 64-bit: ~141 LUT4s, 33 CCU2C slices, 140 FFs
  * EBR Blocks: 0
  * DSP Multipliers: 0 (pure LUT-based synthesis)
- Critical Path & Timing:
  * HA/HB bus setup (1.5 ns) + Booth recode (0.8 ns) + CCU2C adder (1.9 ns) + setup (0.5 ns) = 4.7 ns
  * 32-bit multiply latency: 16 clock cycles (14 compute + 2 writeback: AL, AH)
  * 64-bit multiply latency: 32 clock cycles (2 read + 26 compute + 4 writeback: AL, AH, DL, DH)
"""

from typing import Set, Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.hardware.registers import HalfSelect, Reg, StatusFlag, Registers
from fpu_emu.fpga_resource import fpga_resource

# Width constants
WIDTH_32_BYTES = 4
WIDTH_64_BYTES = 8
BITS_PER_BYTE = 8

# Execution cycles
CYCLES_32 = 16
CYCLES_64 = 32

# Permitted source registers
VALID_32BIT_SRCS: Set[Reg] = {Reg.BL, Reg.DL, Reg.FL, Reg.BH, Reg.DH, Reg.FH}
VALID_64BIT_SRCS: Set[Reg] = {Reg.BX, Reg.DX, Reg.FX}


def _to_signed(val: int, bits: int) -> int:
    """Converts an unsigned integer of bit length `bits` to signed two's complement."""
    if val & (1 << (bits - 1)):
        return val - (1 << bits)
    return val


@fpga_resource(
    approach="Radix-4 Booth Multiplier with CCU2C carry-chains, internal {P, Q} FFs, and RES_BUS MUX",
    luts=77,
    slices_ccu2c=17,
    ffs=75,
    delay_ns=4.7,
    cycles=16,
    shared_unit="alu_booth_mul",
)
def booth_core(
    m_bytes: bytearray,
    q_bytes: bytearray,
    width_bytes: int = WIDTH_32_BYTES,
) -> Tuple[bytearray, bool, bool, bool, bool]:
    """Pure functional Radix-4 Modified Booth multiplication datapath.

    Simulates the step-by-step Radix-4 Booth iteration:
    - 3-bit window {Q[1:0], q_{-1}}
    - Partial product P addition/subtraction
    - Combined arithmetic right shift of {P, Q} by 2 bits.

    :param m_bytes: Multiplicand as Little-Endian bytearray (4 or 8 bytes).
    :param q_bytes: Multiplier as Little-Endian bytearray (4 or 8 bytes).
    :param width_bytes: 4 (32-bit) or 8 (64-bit).
    :return: (product_bytes, cf, zf, sf, vf)
    """
    if width_bytes not in (WIDTH_32_BYTES, WIDTH_64_BYTES):
        raise ValueError(f"Unsupported Booth multiplier width: {width_bytes} bytes")

    total_bits = width_bytes * BITS_PER_BYTE
    steps = total_bits // 2

    m_raw = Registers.to_int(m_bytes)
    q_raw = Registers.to_int(q_bytes)

    m_signed = _to_signed(m_raw, total_bits)
    q = q_raw
    p = 0
    q_minus_1 = 0

    for _ in range(steps):
        # 3-bit inspection window {Q[1:0], q_{-1}}
        window = ((q & 0x03) << 1) | q_minus_1

        match window:
            case 1 | 2:
                p += m_signed
            case 3:
                p += m_signed << 1
            case 4:
                p -= m_signed << 1
            case 5 | 6:
                p -= m_signed
            case _:
                pass  # Window 0 (000) or 7 (111): +0

        # Next booth bit q_{-1} is Q[1]
        q_minus_1 = (q >> 1) & 1

        # Arithmetic right shift of combined {P, Q} by 2 bits
        q = ((p & 0x03) << (total_bits - 2)) | (q >> 2)
        p >>= 2

    # Assemble 2N-bit product bytes
    low_half = q & ((1 << total_bits) - 1)
    high_half = p & ((1 << total_bits) - 1)

    low_bytes = Registers.from_int(low_half, width_bytes)
    high_bytes = Registers.from_int(high_half, width_bytes)
    product_bytes = low_bytes + high_bytes

    # Flag calculation
    cf = False
    zf = all(b == 0 for b in product_bytes)
    sf = bool(high_bytes[-1] & 0x80)

    # Overflow: High word is not the sign extension of low word
    sign_ext_mask = ((1 << total_bits) - 1) if (low_bytes[-1] & 0x80) else 0
    vf = high_half != sign_ext_mask

    return product_bytes, cf, zf, sf, vf


def mul32(hw: Hardware, src: Reg = Reg.BL):
    """MUL AL, src — 32-bit signed multiply yielding 64-bit product in AX (16 cycles)."""
    _validate_src32(src)

    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    q_bytes = hw.reg.read_ha_bus()

    half = HalfSelect.LO if src in (Reg.BL, Reg.DL, Reg.FL) else HalfSelect.HI
    hw.reg.set_hb_bus_mux(half, src)
    m_bytes = hw.reg.read_hb_bus()

    prod_bytes, cf, zf, sf, vf = booth_core(m_bytes, q_bytes, width_bytes=WIDTH_32_BYTES)

    # Hardware Model: The 64-bit product is held in the multiplier's internal {P, Q}
    # shift-register flip-flops (66 FFs) and frozen at cycle 14 when calculation completes.
    # A 32-bit 2:1 multiplexer (booth_out_sel) gates 32 bits at a time onto RES_BUS[31:0].
    # There is zero combinational feedback from register writebacks into {P, Q}.
    prod_latch = prod_bytes

    # 16 cycles: 14 compute cycles + 2 writeback cycles (AL, AH)
    hw.clock.tick(CYCLES_32 - 2)

    # Cycle 15: booth_out_sel=0 -> RES_BUS[31:0] = prod_latch[31:0] -> WE_AL
    hw.clock.tick(1)
    hw.reg.set_res_bus(Reg.AL, prod_latch[0:4])

    # Cycle 16: booth_out_sel=1 -> RES_BUS[31:0] = prod_latch[63:32] -> WE_AH
    hw.clock.tick(1)
    hw.reg.set_res_bus(Reg.AH, prod_latch[4:8])

    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def mul64(hw: Hardware, src: Reg = Reg.BX):
    """MUL AX, src — 64-bit signed multiply yielding 128-bit product in {DX, AX} (32 cycles)."""
    _validate_src64(src)

    # Cycle 1: Read low words of Q (from AL) and M (from src LO)
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    q_lo = hw.reg.read_ha_bus()
    hw.reg.set_hb_bus_mux(HalfSelect.LO, src)
    m_lo = hw.reg.read_hb_bus()

    # Cycle 2: Read high words of Q (from AH) and M (from src HI)
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.HI)
    q_hi = hw.reg.read_ha_bus()
    hw.reg.set_hb_bus_mux(HalfSelect.HI, src)
    m_hi = hw.reg.read_hb_bus()

    q_bytes = q_lo + q_hi
    m_bytes = m_lo + m_hi

    prod_bytes, cf, zf, sf, vf = booth_core(m_bytes, q_bytes, width_bytes=WIDTH_64_BYTES)

    # Hardware Model: The 128-bit product is held in the multiplier's internal {P, Q}
    # shift-register flip-flops (130 FFs) and frozen at cycle 28 when calculation completes.
    # A 32-bit 4:1 multiplexer (booth_out_sel) gates 32 bits at a time onto RES_BUS[31:0].
    # There is zero combinational feedback from register writebacks into {P, Q}.
    prod_latch = prod_bytes

    # 32 cycles: 2 operand read cycles + 26 compute cycles + 4 writeback cycles (AL, AH, DL, DH)
    hw.clock.tick(CYCLES_64 - 4 - 2)

    # Cycle 29: booth_out_sel=00 -> RES_BUS[31:0] = prod_latch[31:0] -> WE_AL
    hw.clock.tick(1)
    hw.reg.set_res_bus(Reg.AL, prod_latch[0:4])

    # Cycle 30: booth_out_sel=01 -> RES_BUS[31:0] = prod_latch[63:32] -> WE_AH
    hw.clock.tick(1)
    hw.reg.set_res_bus(Reg.AH, prod_latch[4:8])

    # Cycle 31: booth_out_sel=10 -> RES_BUS[31:0] = prod_latch[95:64] -> WE_DL
    hw.clock.tick(1)
    hw.reg.set_res_bus(Reg.DL, prod_latch[8:12])

    # Cycle 32: booth_out_sel=11 -> RES_BUS[31:0] = prod_latch[127:96] -> WE_DH
    hw.clock.tick(1)
    hw.reg.set_res_bus(Reg.DH, prod_latch[12:16])

    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def _validate_src32(src: Reg):
    if not isinstance(src, Reg) or src not in VALID_32BIT_SRCS:
        raise ValueError(f"Invalid 32-bit Booth multiply source register: {src}")


def _validate_src64(src: Reg):
    if not isinstance(src, Reg) or src not in VALID_64BIT_SRCS:
        raise ValueError(f"Invalid 64-bit Booth multiply source register: {src}")


def _set_flags(hw: Hardware, cf: bool, zf: bool, sf: bool, vf: bool):
    hw.reg.set_flag(StatusFlag.CARRY, cf)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
    hw.reg.set_flag(StatusFlag.OVERFLOW, vf)
