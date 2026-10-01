"""32-bit and 64-bit bidirectional barrel shifter primitive (alu_shifter).

Per SystemDesign.md Section 3.2 and Section 4:
- Executes single-cycle shifts on AL (32-bit, 1 cycle)
- Executes compound shifts on AX = {AH, AL} (64-bit, 2 cycles)
- Shift count controlled by register C (C[4:0] for 32-bit, C[5:0] for 64-bit) or immediate
- Supported operations:
  * LSL: Logical Shift Left (zero-fill on right, MSB out to CF)
  * LSR: Logical Shift Right (zero-fill on left, LSB out to CF)
  * ASR: Arithmetic Shift Right (sign-extend, LSB out to CF)
- Flag updates:
  * ZF: Result is zero
  * SF: Result MSB is 1
  * CF: Last bit shifted out (or False if shift count == 0)
  * VF: Always cleared to 0

VERILOG SYNTHESIS SPEC (MachXO2 LCMXO2-2000HC):
- Module: alu_shifter32 (time-multiplexed for 64-bit operations)
- Architecture:
  * 5-stage logarithmic multiplexer tree (shift by 16, 8, 4, 2, 1)
  * Bidirectional sharing: Bit-reversal on input and output for Left Shift (LSL),
    sharing the same physical right-shift multiplexer tree for LSR and ASR.
  * Arithmetic sign-extension fill logic (controlled by opcode bit).
- Fixed Inputs:
  * Operand: Hardwired to AL register output (32 bits, NO input register MUX!)
- Dynamic Inputs:
  * Shift Count: 2:1 5-bit MUX selecting between C[4:0] and instruction immediate imm[4:0] (3 LUT4s)
- Output Destination:
  * Latched into AL (32 FFs) on posedge clk.
  * Status flags: CF, ZF, SF latched into STATUS register (3 FFs).
- Hardware Resources (MachXO2-2000):
  * Total LUT4s: ~104 (5 stages * 16 LUT4s + 16 reversal LUT4s + 8 sign/flag logic)
  * Total CCU2C Carry Slices: 0 (pure multiplexer logic)
  * Flip-Flops (FF): 35 (32 destination + 3 flags)
  * EBR Blocks: 0
  * DSP Multipliers: 0
- Critical Path & Timing:
  * 5 MUX levels * 0.6 ns/level + routing = 3.8 ns
  * 32-bit shift: 1 clock cycle (20 ns at 50 MHz)
  * 64-bit compound shift: 2 clock cycles
"""

from enum import Enum, auto
from typing import Optional, Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import HalfSelect, Reg, StatusFlag, Registers
from fpu_emu.fpga_resource import fpga_resource


class ShiftOp(Enum):
    """Barrel shifter operation types."""

    LSL = auto()  # Logical Shift Left
    LSR = auto()  # Logical Shift Right
    ASR = auto()  # Arithmetic Shift Right


@fpga_resource(
    approach="5-stage logarithmic bidirectional barrel shifter",
    luts=104,
    ffs=0,
    delay_ns=4.1,
    cycles=1,
    shared_unit="alu_shifter32",
)
def shifter_core(
    val_bytes: bytearray,
    shift_count: int,
    op: ShiftOp,
    width_bytes: int = 4,
) -> Tuple[bytearray, bool, bool, bool, bool]:
    """Pure functional barrel shifter datapath logic.

    :param val_bytes: Input data as Little-Endian bytearray (4 or 8 bytes).
    :param shift_count: Raw shift count from register C or immediate.
    :param op: ShiftOp (LSL, LSR, ASR).
    :param width_bytes: 4 (32-bit) or 8 (64-bit).
    :return: (result_bytes, cf, zf, sf, vf)
    """
    if width_bytes not in (4, 8):
        raise ValueError(f"Unsupported shifter width: {width_bytes} bytes")

    total_bits = width_bytes * 8
    bit_mask = (1 << total_bits) - 1
    sign_mask = 1 << (total_bits - 1)
    shift_mask = 0x1F if width_bytes == 4 else 0x3F
    count = shift_count & shift_mask

    val = Registers.to_int(val_bytes)

    if count == 0:
        cf = False
        res = val
    elif op == ShiftOp.LSL:
        cf = bool((val >> (total_bits - count)) & 1)
        res = (val << count) & bit_mask
    elif op == ShiftOp.LSR:
        cf = bool((val >> (count - 1)) & 1)
        res = (val >> count) & bit_mask
    elif op == ShiftOp.ASR:
        cf = bool((val >> (count - 1)) & 1)
        is_negative = bool(val & sign_mask)
        res = val >> count
        if is_negative:
            fill_mask = (bit_mask << (total_bits - count)) & bit_mask
            res |= fill_mask
        res &= bit_mask
    else:
        raise ValueError(f"Unknown shift operation: {op}")

    zf = res == 0
    sf = bool(res & sign_mask)
    vf = False

    return Registers.from_int(res, width_bytes), cf, zf, sf, vf


def _apply_shift32(hw: Hardware, op: ShiftOp, shift: Optional[int], reg: Reg):
    """Executes a 32-bit shift on `reg` (default AL) taking 1 clock cycle."""
    hw.clock.tick(1)
    if reg in (Reg.AL, Reg.AH):
        half = HalfSelect.LO if reg == Reg.AL else HalfSelect.HI
        hw.reg.set_ha_bus_mux(half)
        val_bytes = hw.reg.read_ha_bus()
    else:
        half = HalfSelect.LO if reg in (Reg.BL, Reg.DL, Reg.FL) else HalfSelect.HI
        hw.reg.set_hb_bus_mux(half, reg)
        val_bytes = hw.reg.read_hb_bus()

    shift_count = shift if shift is not None else hw.reg.c
    res_bytes, cf, zf, sf, vf = shifter_core(val_bytes, shift_count, op, width_bytes=4)

    hw.reg.set_res_bus(reg, res_bytes)
    hw.reg.set_flag(StatusFlag.CARRY, cf)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
    hw.reg.set_flag(StatusFlag.OVERFLOW, vf)


def _apply_shift64(hw: Hardware, op: ShiftOp, shift: Optional[int], reg: Reg):
    """Executes a 64-bit compound shift on `reg` (default AX) taking 2 clock cycles."""
    lo_reg = Reg.AL if reg == Reg.AX else (Reg.BL if reg == Reg.BX else (Reg.DL if reg == Reg.DX else Reg.FL))
    hi_reg = Reg.AH if reg == Reg.AX else (Reg.BH if reg == Reg.BX else (Reg.DH if reg == Reg.DX else Reg.FH))

    # Cycle 1:
    hw.clock.tick(1)
    if reg == Reg.AX:
        hw.reg.set_ha_bus_mux(HalfSelect.LO)
        lo_bytes = hw.reg.read_ha_bus()
        hw.reg.set_hb_bus_mux(HalfSelect.HI, Reg.AX)
        hi_bytes = hw.reg.read_hb_bus()
    else:
        # Read low half in cycle 1
        hw.reg.set_hb_bus_mux(HalfSelect.LO, reg)
        lo_bytes = hw.reg.read_hb_bus()
        # Read high half in cycle 2
        hw.clock.tick(1)
        hw.reg.set_hb_bus_mux(HalfSelect.HI, reg)
        hi_bytes = hw.reg.read_hb_bus()

    val_bytes = lo_bytes + hi_bytes
    shift_count = shift if shift is not None else hw.reg.c
    res_bytes, cf, zf, sf, vf = shifter_core(val_bytes, shift_count, op, width_bytes=8)

    if reg == Reg.AX:
        # Cycle 1 writeback: AL
        hw.reg.set_res_bus(Reg.AL, res_bytes[:4])
        # Cycle 2 writeback: AH
        hw.clock.tick(1)
        hw.reg.set_res_bus(Reg.AH, res_bytes[4:])
    else:
        # Cycle 2 writeback: LO half
        hw.reg.set_res_bus(lo_reg, res_bytes[:4])
        # Cycle 3 writeback: HI half
        hw.clock.tick(1)
        hw.reg.set_res_bus(hi_reg, res_bytes[4:])

    hw.reg.set_flag(StatusFlag.CARRY, cf)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
    hw.reg.set_flag(StatusFlag.OVERFLOW, vf)


def lsl32(hw: Hardware, shift: Optional[int] = None, reg: Reg = Reg.AL):
    """LSL AL, C — Logical Shift Left 32-bit (1 cycle)."""
    _apply_shift32(hw, ShiftOp.LSL, shift, reg)


def lsr32(hw: Hardware, shift: Optional[int] = None, reg: Reg = Reg.AL):
    """LSR AL, C — Logical Shift Right 32-bit (1 cycle)."""
    _apply_shift32(hw, ShiftOp.LSR, shift, reg)


def asr32(hw: Hardware, shift: Optional[int] = None, reg: Reg = Reg.AL):
    """ASR AL, C — Arithmetic Shift Right 32-bit (1 cycle)."""
    _apply_shift32(hw, ShiftOp.ASR, shift, reg)


def lsl64(hw: Hardware, shift: Optional[int] = None, reg: Reg = Reg.AX):
    """LSL AX, C — Logical Shift Left 64-bit (2 cycles)."""
    _apply_shift64(hw, ShiftOp.LSL, shift, reg)


def lsr64(hw: Hardware, shift: Optional[int] = None, reg: Reg = Reg.AX):
    """LSR AX, C — Logical Shift Right 64-bit (2 cycles)."""
    _apply_shift64(hw, ShiftOp.LSR, shift, reg)


def asr64(hw: Hardware, shift: Optional[int] = None, reg: Reg = Reg.AX):
    """ASR AX, C — Arithmetic Shift Right 64-bit (2 cycles)."""
    _apply_shift64(hw, ShiftOp.ASR, shift, reg)


def rrc32(hw: Hardware, reg: Reg = Reg.AL):
    """RRC — Rotate Right through Carry 32-bit (1 cycle).

    Shifts reg right by 1 bit, with incoming CF shifting into bit 31.
    Sets outgoing CF <- reg[0].
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
    in_carry = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0
    out_carry = bool(val & 1)
    res = (in_carry << 31) | (val >> 1)
    hw.reg.set_res_bus(reg, Registers.from_int(res, 4))
    hw.reg.set_flag(StatusFlag.CARRY, out_carry)
    hw.reg.set_flag(StatusFlag.ZERO, res == 0)
    hw.reg.set_flag(StatusFlag.SIGN, bool(res & 0x80000000))


def rrc64(hw: Hardware, reg: Reg = Reg.AX):
    """RRC AX — Rotate Right through Carry 64-bit (2 cycles).

    Shifts 64-bit reg right by 1 bit, with incoming CF shifting into bit 63.
    Sets outgoing CF <- reg[0].
    """
    lo_reg = Reg.AL if reg == Reg.AX else (Reg.BL if reg == Reg.BX else (Reg.DL if reg == Reg.DX else Reg.FL))
    hi_reg = Reg.AH if reg == Reg.AX else (Reg.BH if reg == Reg.BX else (Reg.DH if reg == Reg.DX else Reg.FH))

    # Cycle 1:
    hw.clock.tick(1)
    if reg == Reg.AX:
        hw.reg.set_ha_bus_mux(HalfSelect.LO)
        lo_bytes = hw.reg.read_ha_bus()
        hw.reg.set_hb_bus_mux(HalfSelect.HI, Reg.AX)
        hi_bytes = hw.reg.read_hb_bus()
    else:
        hw.reg.set_hb_bus_mux(HalfSelect.LO, reg)
        lo_bytes = hw.reg.read_hb_bus()
        hw.clock.tick(1)
        hw.reg.set_hb_bus_mux(HalfSelect.HI, reg)
        hi_bytes = hw.reg.read_hb_bus()

    val = Registers.to_int(lo_bytes + hi_bytes)
    in_carry = 1 if hw.reg.get_flag(StatusFlag.CARRY) else 0
    out_carry = bool(val & 1)
    res = (in_carry << 63) | (val >> 1)
    res_bytes = Registers.from_int(res, 8)

    if reg == Reg.AX:
        # Cycle 1 writeback: AL
        hw.reg.set_res_bus(Reg.AL, res_bytes[:4])
        # Cycle 2 writeback: AH
        hw.clock.tick(1)
        hw.reg.set_res_bus(Reg.AH, res_bytes[4:])
    else:
        hw.reg.set_res_bus(lo_reg, res_bytes[:4])
        hw.clock.tick(1)
        hw.reg.set_res_bus(hi_reg, res_bytes[4:])

    hw.reg.set_flag(StatusFlag.CARRY, out_carry)
    hw.reg.set_flag(StatusFlag.ZERO, res == 0)
    hw.reg.set_flag(StatusFlag.SIGN, bool(res & 0x8000000000000000))
