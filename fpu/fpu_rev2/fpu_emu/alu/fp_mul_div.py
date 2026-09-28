"""Floating-point multiplication and division ALU primitives.

Supports IEEE-754 single (f32) and double (f64) precision.
"""

import math
import struct
from typing import Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers, StatusFlag

F32_EXP_MASK = 0x7F800000
F32_SIGN_MASK = 0x80000000
F64_EXP_MASK = 0x7FF0000000000000
F64_SIGN_MASK = 0x8000000000000000


def mul_f32(hw: Hardware, dst: Reg = Reg.AL, src: Reg = Reg.BL):
    """Multiplies two IEEE-754 single-precision floats: dst <- dst * src.

    Takes 16 clock cycles (Booth multiplier datapath).
    """
    hw.clock.tick(16)
    a_bytes = hw.reg.get(dst)
    b_bytes = hw.reg.get(src)

    a_f = Registers.to_f32(a_bytes)
    b_f = Registers.to_f32(b_bytes)

    res_f = a_f * b_f
    try:
        res_bytes = Registers.from_f32(res_f)
        raw_int = struct.unpack("<I", res_bytes)[0]
        hw.reg.set(dst, res_bytes)
        hw.reg.set_flag(StatusFlag.ZERO, res_f == 0.0)
        hw.reg.set_flag(StatusFlag.SIGN, bool(raw_int & F32_SIGN_MASK))
    except OverflowError:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    if math.isinf(res_f) or math.isnan(res_f):
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
    else:
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)


def div_f32(hw: Hardware, dst: Reg = Reg.AL, src: Reg = Reg.BL):
    """Divides two IEEE-754 single-precision floats: dst <- dst / src.

    Takes 16 clock cycles. Sets OVERFLOW and ERR on division by zero.
    """
    hw.clock.tick(16)
    a_bytes = hw.reg.get(dst)
    b_bytes = hw.reg.get(src)

    a_f = Registers.to_f32(a_bytes)
    b_f = Registers.to_f32(b_bytes)

    if b_f == 0.0:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    res_f = a_f / b_f
    try:
        res_bytes = Registers.from_f32(res_f)
        raw_int = struct.unpack("<I", res_bytes)[0]
        hw.reg.set(dst, res_bytes)
        hw.reg.set_flag(StatusFlag.ZERO, res_f == 0.0)
        hw.reg.set_flag(StatusFlag.SIGN, bool(raw_int & F32_SIGN_MASK))
    except OverflowError:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    if math.isinf(res_f) or math.isnan(res_f):
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
    else:
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)


def mul_f64(hw: Hardware, dst: Reg = Reg.AX, src: Reg = Reg.BX):
    """Multiplies two IEEE-754 double-precision floats: dst <- dst * src.

    Takes 32 clock cycles.
    """
    hw.clock.tick(32)
    a_bytes = hw.reg.get(dst)
    b_bytes = hw.reg.get(src)

    a_f = Registers.to_f64(a_bytes)
    b_f = Registers.to_f64(b_bytes)

    res_f = a_f * b_f
    res_bytes = Registers.from_f64(res_f)
    raw_int = struct.unpack("<Q", res_bytes)[0]
    hw.reg.set(dst, res_bytes)
    hw.reg.set_flag(StatusFlag.ZERO, res_f == 0.0)
    hw.reg.set_flag(StatusFlag.SIGN, bool(raw_int & F64_SIGN_MASK))

    if math.isinf(res_f) or math.isnan(res_f):
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
    else:
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)


def div_f64(hw: Hardware, dst: Reg = Reg.AX, src: Reg = Reg.BX):
    """Divides two IEEE-754 double-precision floats: dst <- dst / src.

    Takes 32 clock cycles. Sets OVERFLOW and ERR on division by zero.
    """
    hw.clock.tick(32)
    a_bytes = hw.reg.get(dst)
    b_bytes = hw.reg.get(src)

    a_f = Registers.to_f64(a_bytes)
    b_f = Registers.to_f64(b_bytes)

    if b_f == 0.0:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    res_f = a_f / b_f
    res_bytes = Registers.from_f64(res_f)
    raw_int = struct.unpack("<Q", res_bytes)[0]
    hw.reg.set(dst, res_bytes)
    hw.reg.set_flag(StatusFlag.ZERO, res_f == 0.0)
    hw.reg.set_flag(StatusFlag.SIGN, bool(raw_int & F64_SIGN_MASK))

    if math.isinf(res_f) or math.isnan(res_f):
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
    else:
        hw.reg.set_flag(StatusFlag.OVERFLOW, False)
