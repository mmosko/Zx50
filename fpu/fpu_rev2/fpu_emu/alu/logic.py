"""32-bit and 64-bit Bitwise Logic & Sign Manipulator (alu_logic).

Per SystemDesign.md Section 3.4 and Section 4:
- Target: Accumulator A (AL for 32-bit, AX for 64-bit).
- Source selects from {BL, DL, FL, BH, DH, FH} for 32-bit, and {BX, DX, FX} for 64-bit.
- Operations:
  * AND: AL <- AL & src (1 cycle) / AX <- AX & src (2 cycles)
  * OR:  AL <- AL | src (1 cycle) / AX <- AX | src (2 cycles)
  * XOR: AL <- AL ^ src (1 cycle) / AX <- AX ^ src (2 cycles)
  * NOT: AL <- ~AL      (1 cycle) / AX <- ~AX      (2 cycles)
  * CHS: AH[31] <- ~AH[31], sets SF <- AH[31] (1 cycle)
  * ABS: AH[31] <- 0, clears SF <- 0          (1 cycle)
- Flag updates for AND/OR/XOR/NOT:
  * ZF: Set if result is 0, cleared otherwise
  * SF: Set if MSB of result is 1, cleared otherwise
  * CF: Always cleared to 0
  * VF: Always cleared to 0
- Flag updates for CHS/ABS:
  * SF: Set to sign bit of register
  * ZF, CF, VF, UF, ERR: Unaffected

VERILOG SYNTHESIS SPEC (MachXO2 LCMXO2-2000HC):
- Module: alu_logic32 (time-multiplexed for 64-bit operations)
- Architecture:
  * 32 parallel 4-LUT function generators (A, B, op[1:0]) implementing AND/OR/XOR/NOT in 1 LUT layer
  * 32-bit Zero Flag evaluation NOR tree (6 LUT4s)
  * Single-bit XOR/inverter for sign bit toggle (CHS) or clear (ABS)
- Inputs:
  * Operand 1: Connected to HA_BUS[31:0] (from HA 2:1 selector: AL or AH)
  * Operand 2: Connected to HB_BUS[31:0] (from HB 8:1 selector: BL, BH, DL, DH, FL, FH, AL, AH; unused for unary NOT/CHS/ABS)
  * Note: Input selection MUXes reside in the shared bus infrastructure (80 LUT4s total).
- Output Destination:
  * Drives RES_BUS[31:0] -> Latching steered to AL (Cycle 1) or AH (Cycle 2) via Clock Enables (WE_AL, WE_AH)
  * Status flags: ZF, SF latched into STATUS register (2 FFs).
- Hardware Resources (MachXO2-2000, standalone logic core):
  * Total LUT4s: ~38 (32 bitwise function generators + 6 ZF NOR tree)
  * Total CCU2C Carry Slices: 0 (pure boolean logic)
  * Flip-Flops (FF): 2 (status flags ZF, SF)
  * EBR Blocks: 0
  * DSP Multipliers: 0
- Critical Path & Timing:
  * HA/HB bus setup (1.5 ns) + LUT4 boolean gate (0.6 ns) + ZF NOR tree (1.0 ns) = 3.1 ns
  * 32-bit logic: 1 clock cycle (20 ns at 50 MHz)
  * 64-bit compound logic: 2 clock cycles (Cycle 1: AL=AL op XL, Cycle 2: AH=AH op XH)
"""

from enum import Enum, auto
from typing import Optional, Set, Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import HalfSelect, Reg, StatusFlag, Registers
from fpu_emu.fpga_resource import fpga_resource

# Supported width constants
WIDTH_32_BYTES = 4
WIDTH_64_BYTES = 8
BITS_PER_BYTE = 8

# Allowed source registers
VALID_SRC_32: Set[Reg] = {Reg.BL, Reg.DL, Reg.FL, Reg.BH, Reg.DH, Reg.FH}
VALID_SRC_64: Set[Reg] = {Reg.BX, Reg.DX, Reg.FX}


class LogicOp(Enum):
    """Bitwise logic operations."""

    AND = auto()
    OR = auto()
    XOR = auto()
    NOT = auto()


@fpga_resource(
    approach="Bitwise 32-bit logic using 4-input LUTs",
    luts=38,
    ffs=0,
    delay_ns=2.1,
    cycles=1,
    shared_unit="alu_logic32",
)
def logic_core(
    a_bytes: bytearray,
    b_bytes: Optional[bytearray],
    op: LogicOp,
    width_bytes: int = WIDTH_32_BYTES,
) -> Tuple[bytearray, bool, bool]:
    """Pure functional bitwise boolean logic.

    :param a_bytes: First operand as Little-Endian bytearray.
    :param b_bytes: Second operand as Little-Endian bytearray (None for unary NOT).
    :param op: LogicOp (AND, OR, XOR, NOT).
    :param width_bytes: 4 (32-bit) or 8 (64-bit).
    :return: (result_bytes, zf, sf)
    """
    if width_bytes not in (WIDTH_32_BYTES, WIDTH_64_BYTES):
        raise ValueError(f"Unsupported logic operation width: {width_bytes} bytes")

    total_bits = width_bytes * BITS_PER_BYTE
    mask = (1 << total_bits) - 1
    sign_mask = 1 << (total_bits - 1)

    a = Registers.to_int(a_bytes)

    if op == LogicOp.NOT:
        res = (~a) & mask
    else:
        if b_bytes is None:
            raise ValueError(f"Operation {op} requires a second operand")
        b = Registers.to_int(b_bytes)
        if op == LogicOp.AND:
            res = a & b
        elif op == LogicOp.OR:
            res = a | b
        elif op == LogicOp.XOR:
            res = a ^ b
        else:
            raise ValueError(f"Unknown logic operation: {op}")

    zf = res == 0
    sf = bool(res & sign_mask)

    return Registers.from_int(res, width_bytes), zf, sf


def _select_hb(hw: Hardware, src: Reg, half: Optional[HalfSelect] = None):
    if src in (Reg.BX, Reg.DX, Reg.FX):
        if half is None:
            raise ValueError(f"64-bit source {src} requires half selection")
        hw.reg.set_hb_bus_mux(half, src)
    elif src in (Reg.BL, Reg.DL, Reg.FL):
        hw.reg.set_hb_bus_mux(HalfSelect.LO, src)
    elif src in (Reg.BH, Reg.DH, Reg.FH):
        hw.reg.set_hb_bus_mux(HalfSelect.HI, src)
    else:
        raise ValueError(f"Invalid source register for HB_BUS: {src}")


def _apply_logic32(hw: Hardware, op: LogicOp, src: Optional[Reg], dst: Reg):
    """Executes a 32-bit bitwise logic operation taking 1 clock cycle."""
    if dst == Reg.AL:
        ha_half = HalfSelect.LO
    elif dst == Reg.AH:
        ha_half = HalfSelect.HI
    else:
        raise ValueError(f"Invalid 32-bit logic destination register: {dst}")

    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(ha_half)
    a_bytes = hw.reg.read_ha_bus()

    if op != LogicOp.NOT:
        if src is None or src not in VALID_SRC_32:
            raise ValueError(f"Invalid 32-bit logic source register: {src}")
        _select_hb(hw, src)
        b_bytes = hw.reg.read_hb_bus()
    else:
        b_bytes = None

    res_bytes, zf, sf = logic_core(a_bytes, b_bytes, op, width_bytes=WIDTH_32_BYTES)

    hw.reg.set_res_bus(dst, res_bytes)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
    hw.reg.set_flag(StatusFlag.CARRY, False)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)


def _apply_logic64(hw: Hardware, op: LogicOp, src: Optional[Reg], dst: Reg):
    """Executes a 64-bit bitwise logic operation taking 2 clock cycles."""
    if dst != Reg.AX:
        raise ValueError(f"Invalid 64-bit logic destination register: {dst}")
    if op != LogicOp.NOT and (src is None or src not in VALID_SRC_64):
        raise ValueError(f"Invalid 64-bit logic source register: {src}")

    # Cycle 1: AL = AL op src_lo
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    a_lo = hw.reg.read_ha_bus()
    if op != LogicOp.NOT and src is not None:
        _select_hb(hw, src, HalfSelect.LO)
        b_lo = hw.reg.read_hb_bus()
    else:
        b_lo = None
    res_lo, zf_lo, _ = logic_core(a_lo, b_lo, op, width_bytes=WIDTH_32_BYTES)
    hw.reg.set_res_bus(Reg.AL, res_lo)

    # Cycle 2: AH = AH op src_hi
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.HI)
    a_hi = hw.reg.read_ha_bus()
    if op != LogicOp.NOT and src is not None:
        _select_hb(hw, src, HalfSelect.HI)
        b_hi = hw.reg.read_hb_bus()
    else:
        b_hi = None
    res_hi, zf_hi, sf_hi = logic_core(a_hi, b_hi, op, width_bytes=WIDTH_32_BYTES)
    hw.reg.set_res_bus(Reg.AH, res_hi)

    hw.reg.set_flag(StatusFlag.ZERO, zf_lo and zf_hi)
    hw.reg.set_flag(StatusFlag.SIGN, sf_hi)
    hw.reg.set_flag(StatusFlag.CARRY, False)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)


# -----------------------------------------------------------------------------
# 32-Bit Micro-Operations (1 cycle)
# -----------------------------------------------------------------------------
def and32(hw: Hardware, src: Reg, dst: Reg = Reg.AL):
    """AND AL, src (1 cycle)."""
    _apply_logic32(hw, LogicOp.AND, src, dst)


def or32(hw: Hardware, src: Reg, dst: Reg = Reg.AL):
    """OR AL, src (1 cycle)."""
    _apply_logic32(hw, LogicOp.OR, src, dst)


def xor32(hw: Hardware, src: Reg, dst: Reg = Reg.AL):
    """XOR AL, src (1 cycle)."""
    _apply_logic32(hw, LogicOp.XOR, src, dst)


def not32(hw: Hardware, dst: Reg = Reg.AL):
    """NOT AL (1 cycle)."""
    _apply_logic32(hw, LogicOp.NOT, None, dst)


# -----------------------------------------------------------------------------
# 64-Bit Micro-Operations (2 cycles)
# -----------------------------------------------------------------------------
def and64(hw: Hardware, src: Reg, dst: Reg = Reg.AX):
    """AND AX, src (2 cycles)."""
    _apply_logic64(hw, LogicOp.AND, src, dst)


def or64(hw: Hardware, src: Reg, dst: Reg = Reg.AX):
    """OR AX, src (2 cycles)."""
    _apply_logic64(hw, LogicOp.OR, src, dst)


def xor64(hw: Hardware, src: Reg, dst: Reg = Reg.AX):
    """XOR AX, src (2 cycles)."""
    _apply_logic64(hw, LogicOp.XOR, src, dst)


def not64(hw: Hardware, dst: Reg = Reg.AX):
    """NOT AX (2 cycles)."""
    _apply_logic64(hw, LogicOp.NOT, None, dst)


# -----------------------------------------------------------------------------
# Floating-Point Sign Manipulation (1 cycle)
# -----------------------------------------------------------------------------
def chs(hw: Hardware, reg: Reg = Reg.AH):
    """CHS — Change Sign (1 cycle for 32-bit, 2 cycles for 64-bit).

    Toggles sign bit (bit 31 for 32-bit, bit 63 for 64-bit) of reg.
    Sets SF <- sign bit.
    """
    if reg in (Reg.AX, Reg.BX, Reg.DX, Reg.FX):
        hw.clock.tick(1)
        hw.clock.tick(1)
        if reg == Reg.AX:
            hw.reg.set_ha_bus_mux(HalfSelect.HI)
            val_bytes = hw.reg.read_ha_bus()
            hi_reg = Reg.AH
        else:
            hw.reg.set_hb_bus_mux(HalfSelect.HI, reg)
            val_bytes = hw.reg.read_hb_bus()
            hi_reg = Reg.BH if reg == Reg.BX else (Reg.DH if reg == Reg.DX else Reg.FH)
        val = Registers.to_int(val_bytes) ^ 0x80000000
        hw.reg.set_res_bus(hi_reg, Registers.from_int(val, 4))
        hw.reg.set_flag(StatusFlag.SIGN, bool(val & 0x80000000))
    else:
        hw.clock.tick(1)
        if reg in (Reg.AL, Reg.AH):
            half = HalfSelect.LO if reg == Reg.AL else HalfSelect.HI
            hw.reg.set_ha_bus_mux(half)
            val_bytes = hw.reg.read_ha_bus()
        else:
            half = HalfSelect.LO if reg in (Reg.BL, Reg.DL, Reg.FL) else HalfSelect.HI
            hw.reg.set_hb_bus_mux(half, reg)
            val_bytes = hw.reg.read_hb_bus()
        val = Registers.to_int(val_bytes) ^ 0x80000000
        hw.reg.set_res_bus(reg, Registers.from_int(val, 4))
        hw.reg.set_flag(StatusFlag.SIGN, bool(val & 0x80000000))


def abs_val(hw: Hardware, reg: Reg = Reg.AH):
    """ABS — Absolute Value (1 cycle for 32-bit, 2 cycles for 64-bit).

    Clears sign bit (bit 31 for 32-bit, bit 63 for 64-bit) of reg.
    Clears SF <- 0.
    """
    if reg in (Reg.AX, Reg.BX, Reg.DX, Reg.FX):
        hw.clock.tick(1)
        hw.clock.tick(1)
        if reg == Reg.AX:
            hw.reg.set_ha_bus_mux(HalfSelect.HI)
            val_bytes = hw.reg.read_ha_bus()
            hi_reg = Reg.AH
        else:
            hw.reg.set_hb_bus_mux(HalfSelect.HI, reg)
            val_bytes = hw.reg.read_hb_bus()
            hi_reg = Reg.BH if reg == Reg.BX else (Reg.DH if reg == Reg.DX else Reg.FH)
        val = Registers.to_int(val_bytes) & 0x7FFFFFFF
        hw.reg.set_res_bus(hi_reg, Registers.from_int(val, 4))
        hw.reg.set_flag(StatusFlag.SIGN, False)
    else:
        hw.clock.tick(1)
        if reg in (Reg.AL, Reg.AH):
            half = HalfSelect.LO if reg == Reg.AL else HalfSelect.HI
            hw.reg.set_ha_bus_mux(half)
            val_bytes = hw.reg.read_ha_bus()
        else:
            half = HalfSelect.LO if reg in (Reg.BL, Reg.DL, Reg.FL) else HalfSelect.HI
            hw.reg.set_hb_bus_mux(half, reg)
            val_bytes = hw.reg.read_hb_bus()
        val = Registers.to_int(val_bytes) & 0x7FFFFFFF
        hw.reg.set_res_bus(reg, Registers.from_int(val, 4))
        hw.reg.set_flag(StatusFlag.SIGN, False)


def abs_int32(hw: Hardware, reg: Reg = Reg.AL):
    """ABS_I32 — 32-bit Two's Complement Integer Absolute Value (1 cycle).

    If val < 0, computes -val. If val == 0x80000000 (-2147483648), sets OVERFLOW = 1.
    """
    hw.clock.tick(1)
    if reg in (Reg.AL, Reg.AH):
        half = HalfSelect.LO if reg == Reg.AL else HalfSelect.HI
        hw.reg.set_ha_bus_mux(half)
        val_bytes = hw.reg.read_ha_bus()
    else:
        half = HalfSelect.LO if reg in (Reg.BL, Reg.DL, Reg.FL) else HalfSelect.HI
        hw.reg.set_hb_bus_mux(half, reg)
        val_bytes = hw.reg.read_hb_bus()

    val = Registers.to_int(val_bytes)
    if val & 0x80000000:
        if val == 0x80000000:
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.SIGN, True)
        else:
            val = ((~val) + 1) & 0xFFFFFFFF
            hw.reg.set_res_bus(reg, Registers.from_int(val, 4))
            hw.reg.set_flag(StatusFlag.OVERFLOW, False)
            hw.reg.set_flag(StatusFlag.SIGN, False)
    else:
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)

    hw.reg.set_flag(StatusFlag.ZERO, val == 0)
    hw.reg.set_flag(StatusFlag.CARRY, False)


def abs_int64(hw: Hardware, reg: Reg = Reg.AX):
    """ABS_I64 — 64-bit Two's Complement Integer Absolute Value (2 cycles).

    If val < 0, computes -val. If val == 0x80000000_00000000, sets OVERFLOW = 1.
    """
    if reg != Reg.AX:
        raise ValueError(f"ABS_I64 only supported on Reg.AX per microcode ISA, got {reg}")

    # Cycle 1: Read inputs on HA_BUS (AL) and HB_BUS (AH)
    hw.clock.tick(1)
    hw.reg.set_ha_bus_mux(HalfSelect.LO)
    lo_bytes = hw.reg.read_ha_bus()
    hw.reg.set_hb_bus_mux(HalfSelect.HI, Reg.AX)
    hi_bytes = hw.reg.read_hb_bus()

    val = Registers.to_int(lo_bytes + hi_bytes)

    if val & (1 << 63):
        if val == (1 << 63):
            hw.clock.tick(1)
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.SIGN, True)
        else:
            neg_val = ((~val) + 1) & 0xFFFFFFFFFFFFFFFF
            res_bytes = Registers.from_int(neg_val, 8)
            # Cycle 1 writeback: AL
            hw.reg.set_res_bus(Reg.AL, res_bytes[:4])
            # Cycle 2 writeback: AH
            hw.clock.tick(1)
            hw.reg.set_res_bus(Reg.AH, res_bytes[4:])
            hw.reg.set_flag(StatusFlag.OVERFLOW, False)
            hw.reg.set_flag(StatusFlag.SIGN, False)
    else:
        # Cycle 2: No writeback needed
        hw.clock.tick(1)
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)

    hw.reg.set_flag(StatusFlag.ZERO, val == 0)
    hw.reg.set_flag(StatusFlag.CARRY, False)
