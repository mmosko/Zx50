"""32-bit and 64-bit parallel adder/subtractor ALU primitive (alu_adder).

Implements ADD, ADC, SUB, SBB, and CMP per SystemDesign.md Section 3.1.
Operates on the physical hardware register file and advances the system clock.

VERILOG SYNTHESIS SPEC (MachXO2 LCMXO2-2000HC):
- Module: alu_adder32 (time-multiplexed for 64-bit operations)
- Architecture:
  * 32-bit fast carry chain (16 CCU2C dual-ripple slices)
  * 32 XOR gates for B-operand complement on subtraction (16 LUT4s)
  * Dynamic carry-in (CIN mux selects 0, 1, or CF flip-flop)
  * 32-bit Zero Flag evaluation NOR tree (6 LUT4s)
  * Overflow evaluation (1 LUT4)
- Inputs:
  * Operand 1: Connected to HA_BUS[31:0] (from HA 2:1 selector: AL or AH)
  * Operand 2: Connected to HB_BUS[31:0] (from HB 8:1 selector: BL, BH, DL, DH, FL, FH, AL, AH)
  * Note: Input selection MUXes reside in the shared bus infrastructure (80 LUT4s total).
- Output Destination:
  * Drives RES_BUS[31:0] -> Latching steered to AL (Cycle 1) or AH (Cycle 2) via Clock Enables (WE_AL, WE_AH)
  * Status flags: CF, ZF, SF, VF latched into STATUS register FFs (4 FFs)
- Hardware Resources (MachXO2-2000, standalone adder core):
  * Total LUT4s: 23 (16 XORs + 6 ZF NOR tree + 1 VF)
  * Total CCU2C Carry Slices: 16 (32-bit carry chain)
  * Flip-Flops (FF): 4 (status flags CF, ZF, SF, VF; destination registers in PFU)
  * EBR Blocks: 0
  * DSP Multipliers: 0
- Critical Path & Timing:
  * HA/HB bus setup (1.5 ns) + CCU2C carry ripple (1.8 ns) + flag NOR tree (1.2 ns) = 4.5 ns
  * 32-bit operations: 1 clock cycle (20 ns at 50 MHz)
  * 64-bit compound operations: 2 clock cycles (Cycle 1: AL+XL, Cycle 2: AH+XH+CF)
"""

from typing import Optional, Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import HalfSelect, Reg, StatusFlag
from fpu_emu.fpga_resource import fpga_resource

# Permitted source registers
VALID_32BIT_SRCS = {
    Reg.BL, Reg.DL, Reg.FL, Reg.BH, Reg.DH, Reg.FH, Reg.AH, Reg.AL
}
VALID_64BIT_SRCS = {
    Reg.BX, Reg.DX, Reg.FX, Reg.AX
}


def _select_hb(hw: Hardware, src: Reg, half: Optional[HalfSelect] = None):
    """Sets the HB_BUS multiplexer according to the source register and half."""
    if half is not None:
        hw.reg.set_hb_mux(half, src)
    elif src in (Reg.AL, Reg.BL, Reg.DL, Reg.FL):
        hw.reg.set_hb_mux(HalfSelect.LO, src)
    elif src in (Reg.AH, Reg.BH, Reg.DH, Reg.FH):
        hw.reg.set_hb_mux(HalfSelect.HI, src)
    else:
        raise ValueError(f"Invalid source register for HB_BUS: {src}")


@fpga_resource(
    approach="32 XOR gates + MachXO2 CCU2C fast carry-chain",
    luts=23,
    slices_ccu2c=16,
    ffs=4,
    delay_ns=3.9,
    cycles=1,
    shared_unit="alu_adder32",
)
def adder_core(
    hw: Hardware,
    cin: int = 0,
    sub: bool = False
) -> Tuple[bytearray, bool, bool, bool, bool]:
    """Pure 32-bit carry-lookahead/ripple adder-subtractor core.

    Models MachXO2 CCU2C dedicated carry chains connected directly to HA_BUS and HB_BUS.

    :param hw: Hardware instance holding registers and datapath buses
    :param cin: Carry-in (0 or 1) for addition; Borrow-in (0 or 1) for subtraction
    :param sub: True for subtraction (HA - HB - cin), False for addition (HA + HB + cin)
    :return: (result, carry_borrow_out, zf, sf, vf)
    """
    a = hw.reg.read_ha_bus()
    b = hw.reg.read_hb_bus()

    if len(a) != 4 or len(b) != 4:
        raise ValueError(f"Operands must be 4 bytes each, got len(a)={len(a)}, len(b)={len(b)}")

    res = bytearray(4)

    # In two's-complement subtraction: A - B - borrow = A + (~B) + (1 - borrow)
    carry = (0 if cin else 1) if sub else cin

    for i in range(4):
        b_val = (b[i] ^ 0xFF) if sub else b[i]
        temp = a[i] + b_val + carry
        res[i] = temp & 0xFF
        carry = (temp >> 8) & 1

    # Zero flag: all 32 bits are 0
    zf = (res == b"\x00\x00\x00\x00")

    # Sign flag: bit 31 of result is 1
    sf = bool(res[3] & 0x80)

    a_msb = bool(a[3] & 0x80)
    b_msb = bool(b[3] & 0x80)
    r_msb = sf

    if sub:
        # Borrow out: carry == 0 means borrow occurred (A < B + borrow_in)
        cf = (carry == 0)
        # Two's complement signed overflow on subtraction:
        # Occurs when operands have different signs and result sign differs from A
        vf = (a_msb != b_msb) and (a_msb != r_msb)
    else:
        # Unsigned carry out of MSB
        cf = bool(carry)
        # Two's complement signed overflow on addition:
        # Occurs when operands have same sign and result sign differs from inputs
        vf = (a_msb == b_msb) and (a_msb != r_msb)

    return res, cf, zf, sf, vf


# -----------------------------------------------------------------------------
# 32-Bit Micro-Operations (1 cycle execution)
# -----------------------------------------------------------------------------
def add32(hw: Hardware, src: Reg):
    """ADD AL, src: 32-bit addition without carry (1 cycle)."""
    _validate_src32(src)
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src)
    res, cf, zf, sf, vf = adder_core(hw, cin=0, sub=False)
    hw.reg.set_res_bus(Reg.AL, res)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def adc32(hw: Hardware, src: Reg):
    """ADC AL, src: 32-bit addition with carry (1 cycle)."""
    _validate_src32(src)
    cin = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src)
    res, cf, zf, sf, vf = adder_core(hw, cin=cin, sub=False)
    hw.reg.set_res_bus(Reg.AL, res)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def sub32(hw: Hardware, src: Reg):
    """SUB AL, src: 32-bit subtraction without borrow (1 cycle)."""
    _validate_src32(src)
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src)
    res, cf, zf, sf, vf = adder_core(hw, cin=0, sub=True)
    hw.reg.set_res_bus(Reg.AL, res)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def sbb32(hw: Hardware, src: Reg):
    """SBB AL, src: 32-bit subtraction with borrow (1 cycle)."""
    _validate_src32(src)
    borrow_in = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src)
    res, cf, zf, sf, vf = adder_core(hw, cin=borrow_in, sub=True)
    hw.reg.set_res_bus(Reg.AL, res)
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


def cmp32(hw: Hardware, src: Reg):
    """CMP AL, src: 32-bit compare AL - src without modifying AL (1 cycle)."""
    _validate_src32(src)
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src)
    _, cf, zf, sf, vf = adder_core(hw, cin=0, sub=True)
    # Latching disabled: WE_AL = 0
    _set_flags(hw, cf=cf, zf=zf, sf=sf, vf=vf)


# -----------------------------------------------------------------------------
# 64-Bit Compound Micro-Operations (2 cycle synthesized execution)
# -----------------------------------------------------------------------------
def add64(hw: Hardware, src: Reg):
    """ADD AX, src: 64-bit addition without carry (2 cycles)."""
    _validate_src64(src)

    # Cycle 1: Low word add
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src, HalfSelect.LO)
    res_l, cout_l, zf_l, _, _ = adder_core(hw, cin=0, sub=False)
    hw.reg.set_res_bus(Reg.AL, res_l)

    # Cycle 2: High word add with carry
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.HI)
    _select_hb(hw, src, HalfSelect.HI)
    res_h, cf, zf_h, sf, vf = adder_core(hw, cin=(1 if cout_l else 0), sub=False)
    hw.reg.set_res_bus(Reg.AH, res_h)

    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


def adc64(hw: Hardware, src: Reg):
    """ADC AX, src: 64-bit addition with carry (2 cycles)."""
    _validate_src64(src)
    cin = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0

    # Cycle 1: Low word add with initial carry
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src, HalfSelect.LO)
    res_l, cout_l, zf_l, _, _ = adder_core(hw, cin=cin, sub=False)
    hw.reg.set_res_bus(Reg.AL, res_l)

    # Cycle 2: High word add with carry
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.HI)
    _select_hb(hw, src, HalfSelect.HI)
    res_h, cf, zf_h, sf, vf = adder_core(hw, cin=(1 if cout_l else 0), sub=False)
    hw.reg.set_res_bus(Reg.AH, res_h)

    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


def sub64(hw: Hardware, src: Reg):
    """SUB AX, src: 64-bit subtraction without borrow (2 cycles)."""
    _validate_src64(src)

    # Cycle 1: Low word subtract
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src, HalfSelect.LO)
    res_l, bout_l, zf_l, _, _ = adder_core(hw, cin=0, sub=True)
    hw.reg.set_res_bus(Reg.AL, res_l)

    # Cycle 2: High word subtract with borrow
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.HI)
    _select_hb(hw, src, HalfSelect.HI)
    res_h, cf, zf_h, sf, vf = adder_core(hw, cin=(1 if bout_l else 0), sub=True)
    hw.reg.set_res_bus(Reg.AH, res_h)

    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


def sbb64(hw: Hardware, src: Reg):
    """SBB AX, src: 64-bit subtraction with borrow (2 cycles)."""
    _validate_src64(src)
    borrow_in = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0

    # Cycle 1: Low word subtract with initial borrow
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src, HalfSelect.LO)
    res_l, bout_l, zf_l, _, _ = adder_core(hw, cin=borrow_in, sub=True)
    hw.reg.set_res_bus(Reg.AL, res_l)

    # Cycle 2: High word subtract with borrow
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.HI)
    _select_hb(hw, src, HalfSelect.HI)
    res_h, cf, zf_h, sf, vf = adder_core(hw, cin=(1 if bout_l else 0), sub=True)
    hw.reg.set_res_bus(Reg.AH, res_h)

    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


def cmp64(hw: Hardware, src: Reg):
    """CMP AX, src: 64-bit compare AX - src without modifying AX (2 cycles)."""
    _validate_src64(src)

    # Cycle 1: Low word compare
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    _select_hb(hw, src, HalfSelect.LO)
    _, bout_l, zf_l, _, _ = adder_core(hw, cin=0, sub=True)

    # Cycle 2: High word compare
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.HI)
    _select_hb(hw, src, HalfSelect.HI)
    _, cf, zf_h, sf, vf = adder_core(hw, cin=(1 if bout_l else 0), sub=True)

    # Latching disabled: WE_AL = WE_AH = 0
    _set_flags(hw, cf=cf, zf=(zf_l and zf_h), sf=sf, vf=vf)


# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------
def _validate_src32(src: Reg):
    if not isinstance(src, Reg) or src not in VALID_32BIT_SRCS:
        raise ValueError(f"Invalid 32-bit source register: {src}")


def _validate_src64(src: Reg):
    if not isinstance(src, Reg) or src not in VALID_64BIT_SRCS:
        raise ValueError(f"Invalid 64-bit source register: {src}")


def _set_flags(hw: Hardware, cf: bool, zf: bool, sf: bool, vf: bool):
    hw.reg.set_flag(StatusFlag.CARRY, cf)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
    hw.reg.set_flag(StatusFlag.OVERFLOW, vf)
