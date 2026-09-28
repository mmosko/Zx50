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
"""

from enum import Enum, auto
from typing import Optional, Set, Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers

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


def _apply_logic32(hw: Hardware, op: LogicOp, src: Optional[Reg], dst: Reg):
    """Executes a 32-bit bitwise logic operation taking 1 clock cycle."""
    hw.clock.tick(1)
    if op != LogicOp.NOT:
        if src is None or src not in VALID_SRC_32:
            raise ValueError(f"Invalid 32-bit logic source register: {src}")
        b_bytes = hw.reg.get(src)
    else:
        b_bytes = None

    a_bytes = hw.reg.get(dst)
    res_bytes, zf, sf = logic_core(a_bytes, b_bytes, op, width_bytes=WIDTH_32_BYTES)

    hw.reg.set(dst, res_bytes)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
    hw.reg.set_flag(StatusFlag.CARRY, False)
    hw.reg.set_flag(StatusFlag.OVERFLOW, False)


def _apply_logic64(hw: Hardware, op: LogicOp, src: Optional[Reg], dst: Reg):
    """Executes a 64-bit bitwise logic operation taking 2 clock cycles."""
    hw.clock.tick(2)
    if op != LogicOp.NOT:
        if src is None or src not in VALID_SRC_64:
            raise ValueError(f"Invalid 64-bit logic source register: {src}")
        b_bytes = hw.reg.get(src)
    else:
        b_bytes = None

    a_bytes = hw.reg.get(dst)
    res_bytes, zf, sf = logic_core(a_bytes, b_bytes, op, width_bytes=WIDTH_64_BYTES)

    hw.reg.set(dst, res_bytes)
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, sf)
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
        hw.clock.tick(2)
        val = Registers.to_int(hw.reg.get(reg))
        val ^= (1 << 63)
        hw.reg.set(reg, Registers.from_int(val, 8))
        hw.reg.set_flag(StatusFlag.SIGN, bool(val & (1 << 63)))
    else:
        hw.clock.tick(1)
        val = Registers.to_int(hw.reg.get(reg))
        val ^= 0x80000000
        hw.reg.set(reg, Registers.from_int(val, 4))
        hw.reg.set_flag(StatusFlag.SIGN, bool(val & 0x80000000))


def abs_val(hw: Hardware, reg: Reg = Reg.AH):
    """ABS — Absolute Value (1 cycle for 32-bit, 2 cycles for 64-bit).

    Clears sign bit (bit 31 for 32-bit, bit 63 for 64-bit) of reg.
    Clears SF <- 0.
    """
    if reg in (Reg.AX, Reg.BX, Reg.DX, Reg.FX):
        hw.clock.tick(2)
        val = Registers.to_int(hw.reg.get(reg))
        val &= 0x7FFFFFFFFFFFFFFF
        hw.reg.set(reg, Registers.from_int(val, 8))
        hw.reg.set_flag(StatusFlag.SIGN, False)
    else:
        hw.clock.tick(1)
        val = Registers.to_int(hw.reg.get(reg))
        val &= 0x7FFFFFFF
        hw.reg.set(reg, Registers.from_int(val, 4))
        hw.reg.set_flag(StatusFlag.SIGN, False)


def abs_int32(hw: Hardware, reg: Reg = Reg.AL):
    """ABS_I32 — 32-bit Two's Complement Integer Absolute Value (1 cycle).

    If val < 0, computes -val. If val == 0x80000000 (-2147483648), sets OVERFLOW = 1.
    """
    hw.clock.tick(1)
    val = Registers.to_int(hw.reg.get(reg))
    if val & 0x80000000:
        if val == 0x80000000:
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.SIGN, True)
        else:
            val = ((~val) + 1) & 0xFFFFFFFF
            hw.reg.set(reg, Registers.from_int(val, 4))
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
    hw.clock.tick(2)
    val = Registers.to_int(hw.reg.get(reg))
    if val & (1 << 63):
        if val == (1 << 63):
            hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            hw.reg.set_flag(StatusFlag.SIGN, True)
        else:
            val = ((~val) + 1) & 0xFFFFFFFFFFFFFFFF
            hw.reg.set(reg, Registers.from_int(val, 8))
            hw.reg.set_flag(StatusFlag.OVERFLOW, False)
            hw.reg.set_flag(StatusFlag.SIGN, False)
    else:
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
        hw.reg.set_flag(StatusFlag.SIGN, False)

    hw.reg.set_flag(StatusFlag.ZERO, val == 0)
    hw.reg.set_flag(StatusFlag.CARRY, False)

