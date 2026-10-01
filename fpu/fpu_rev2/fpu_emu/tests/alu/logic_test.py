"""Comprehensive unit tests for 32/64-bit Bitwise Logic and Sign Manipulator (alu_logic)."""

import pytest
from typing import cast
from fpu_emu.alu.alu import Alu
from fpu_emu.alu.logic import (
    logic_core,
    LogicOp,
    and32,
    or32,
    xor32,
    not32,
    and64,
    or64,
    xor64,
    not64,
    chs,
    abs_val,
    abs_int32,
    abs_int64,
)
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers
from fpu_emu.tests.testharness import RegTestHarness


# =============================================================================
# 1. 32-Bit Core Logic Tests
# =============================================================================
@pytest.mark.parametrize(
    "a,b,op,expected_res,expected_zf,expected_sf,desc",
    [
        # AND
        (0xFFFFFFFF, 0x00000000, LogicOp.AND, 0x00000000, True, False, "AND with zero -> zero"),
        (0xAAAAAAAA, 0x55555555, LogicOp.AND, 0x00000000, True, False, "AND alternating bits -> zero"),
        (0xFFFFFFFF, 0x80000000, LogicOp.AND, 0x80000000, False, True, "AND sign bit set"),
        (0x12345678, 0x0000FFFF, LogicOp.AND, 0x00005678, False, False, "AND lower 16 bits"),
        # OR
        (0x00000000, 0x00000000, LogicOp.OR, 0x00000000, True, False, "OR zero with zero -> zero"),
        (0xAAAAAAAA, 0x55555555, LogicOp.OR, 0xFFFFFFFF, False, True, "OR alternating bits -> all ones"),
        (0x00000001, 0x80000000, LogicOp.OR, 0x80000001, False, True, "OR sign bit and LSB"),
        (0x12340000, 0x00005678, LogicOp.OR, 0x12345678, False, False, "OR combine halves"),
        # XOR
        (0xFFFFFFFF, 0xFFFFFFFF, LogicOp.XOR, 0x00000000, True, False, "XOR identical -> zero"),
        (0x12345678, 0x12345678, LogicOp.XOR, 0x00000000, True, False, "XOR identical word -> zero"),
        (0x00000000, 0x80000000, LogicOp.XOR, 0x80000000, False, True, "XOR toggle sign bit"),
        (0xFFFFFFFF, 0x7FFFFFFF, LogicOp.XOR, 0x80000000, False, True, "XOR bit 31 set"),
        # NOT
        (0x00000000, None, LogicOp.NOT, 0xFFFFFFFF, False, True, "NOT 0 -> 0xFFFFFFFF"),
        (0xFFFFFFFF, None, LogicOp.NOT, 0x00000000, True, False, "NOT 0xFFFFFFFF -> 0"),
        (0x7FFFFFFF, None, LogicOp.NOT, 0x80000000, False, True, "NOT pos max -> 0x80000000"),
        (0x80000000, None, LogicOp.NOT, 0x7FFFFFFF, False, False, "NOT sign bit set -> pos max"),
    ],
)
def test_logic_core_32(a, b, op, expected_res, expected_zf, expected_sf, desc):
    a_bytes = Registers.from_int(a, 4)
    b_bytes = Registers.from_int(b, 4) if b is not None else None
    res_bytes, zf, sf = logic_core(a_bytes, b_bytes, op, width_bytes=4)

    assert Registers.to_int(res_bytes) == expected_res, f"Failed {desc}: result mismatch"
    assert zf == expected_zf, f"Failed {desc}: ZF mismatch"
    assert sf == expected_sf, f"Failed {desc}: SF mismatch"


# =============================================================================
# 2. 64-Bit Core Logic Tests
# =============================================================================
@pytest.mark.parametrize(
    "a,b,op,expected_res,expected_zf,expected_sf,desc",
    [
        (0xFFFFFFFFFFFFFFFF, 0x0000000000000000, LogicOp.AND, 0x0, True, False, "AND64 zero"),
        (0x0000000000000000, 0x8000000000000000, LogicOp.OR, 0x8000000000000000, False, True, "OR64 sign bit"),
        (0x123456789ABCDEF0, 0x123456789ABCDEF0, LogicOp.XOR, 0x0, True, False, "XOR64 identical -> zero"),
        (0x0000000000000000, None, LogicOp.NOT, 0xFFFFFFFFFFFFFFFF, False, True, "NOT64 zero -> all ones"),
        (0xFFFFFFFFFFFFFFFF, None, LogicOp.NOT, 0x0000000000000000, True, False, "NOT64 all ones -> zero"),
    ],
)
def test_logic_core_64(a, b, op, expected_res, expected_zf, expected_sf, desc):
    a_bytes = Registers.from_int(a, 8)
    b_bytes = Registers.from_int(b, 8) if b is not None else None
    res_bytes, zf, sf = logic_core(a_bytes, b_bytes, op, width_bytes=8)

    assert Registers.to_int(res_bytes) == expected_res, f"Failed {desc}: result mismatch"
    assert zf == expected_zf, f"Failed {desc}: ZF mismatch"
    assert sf == expected_sf, f"Failed {desc}: SF mismatch"


# =============================================================================
# 3. 32-Bit Registered Logic Operations & Cycle Timing
# =============================================================================
@pytest.mark.parametrize("src", [Reg.BL, Reg.DL, Reg.FL, Reg.BH, Reg.DH, Reg.FH])
def test_and32_all_sources(src):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(0xFFFFFFFF, 4))
    reg.set(src, Registers.from_int(0x12345678, 4))

    and32(hw, src)

    assert Registers.to_int(reg.peek(Reg.AL)) == 0x12345678
    assert hw.clock.cycles == 1
    assert not reg.get_flag(StatusFlag.CARRY)
    assert not reg.get_flag(StatusFlag.OVERFLOW)


def test_or32_flags():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set_flag(StatusFlag.CARRY, True)
    reg.set_flag(StatusFlag.OVERFLOW, True)
    reg.set(Reg.AL, Registers.from_int(0x00000000, 4))
    reg.set(Reg.BL, Registers.from_int(0x80000000, 4))

    or32(hw, Reg.BL)

    assert Registers.to_int(reg.peek(Reg.AL)) == 0x80000000
    assert hw.clock.cycles == 1
    assert reg.get_flag(StatusFlag.SIGN) is True
    assert not reg.get_flag(StatusFlag.ZERO)
    assert not reg.get_flag(StatusFlag.CARRY)  # Cleared
    assert not reg.get_flag(StatusFlag.OVERFLOW)  # Cleared


def test_xor32_zero():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(0xABCD1234, 4))
    reg.set(Reg.BL, Registers.from_int(0xABCD1234, 4))

    xor32(hw, Reg.BL)

    assert Registers.to_int(reg.peek(Reg.AL)) == 0
    assert hw.clock.cycles == 1
    assert reg.get_flag(StatusFlag.ZERO) is True
    assert not reg.get_flag(StatusFlag.SIGN)


def test_not32():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(0x00000000, 4))

    not32(hw)

    assert Registers.to_int(reg.peek(Reg.AL)) == 0xFFFFFFFF
    assert hw.clock.cycles == 1
    assert reg.get_flag(StatusFlag.SIGN) is True
    assert not reg.get_flag(StatusFlag.ZERO)


# =============================================================================
# 4. 64-Bit Registered Logic Operations & 2-Cycle Timing
# =============================================================================
@pytest.mark.parametrize("src", [Reg.BX, Reg.DX, Reg.FX])
def test_and64_sources(src):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(0xFFFFFFFFFFFFFFFF, 8))
    reg.set(src, Registers.from_int(0x0123456789ABCDEF, 8))

    and64(hw, src)

    assert Registers.to_int(reg.peek(Reg.AX)) == 0x0123456789ABCDEF
    assert hw.clock.cycles == 2


def test_not64():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(0x0000000000000000, 8))

    not64(hw)

    assert Registers.to_int(reg.peek(Reg.AX)) == 0xFFFFFFFFFFFFFFFF
    assert hw.clock.cycles == 2
    assert reg.get_flag(StatusFlag.SIGN) is True


# =============================================================================
# 5. Sign Manipulation (CHS and ABS)
# =============================================================================
def test_chs_toggles_sign_bit():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    # AH = 0x3F800000 (positive float 1.0)
    reg.set(Reg.AH, Registers.from_int(0x3F800000, 4))
    reg.set(Reg.AL, Registers.from_int(0x11223344, 4))  # AL must be unmodified

    chs(hw, Reg.AH)

    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AH)) == 0xBF800000  # Sign bit toggled
    assert reg.get_flag(StatusFlag.SIGN) is True
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x11223344  # AL intact

    chs(hw, Reg.AH)
    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.AH)) == 0x3F800000  # Sign bit toggled back
    assert not reg.get_flag(StatusFlag.SIGN)


def test_abs_clears_sign_bit():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    # AH = 0xBF800000 (negative float -1.0)
    reg.set(Reg.AH, Registers.from_int(0xBF800000, 4))
    reg.set_flag(StatusFlag.SIGN, True)

    abs_val(hw, Reg.AH)

    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AH)) == 0x3F800000  # Sign cleared
    assert not reg.get_flag(StatusFlag.SIGN)

    # Calling ABS on already positive value
    abs_val(hw, Reg.AH)
    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.AH)) == 0x3F800000
    assert not reg.get_flag(StatusFlag.SIGN)


def test_chs_64bit_register():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.BX, Registers.from_int(0x3FF0000000000000, 8))  # +1.0 double
    chs(hw, reg=Reg.BX)
    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.BX)) == 0xBFF0000000000000  # -1.0 double
    assert reg.get_flag(StatusFlag.SIGN) is True

    chs(hw, reg=Reg.BX)
    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.BX)) == 0x3FF0000000000000  # +1.0 double
    assert not reg.get_flag(StatusFlag.SIGN)


def test_abs_64bit_register():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(0xBFF0000000000000, 8))  # -1.0 double
    abs_val(hw, reg=Reg.AX)
    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x3FF0000000000000  # +1.0 double
    assert not reg.get_flag(StatusFlag.SIGN)


# =============================================================================
# 6. Source Register Validation & ALU Delegation
# =============================================================================
def test_invalid_source_registers():
    hw = Hardware()
    with pytest.raises(ValueError):
        and32(hw, Reg.AX)  # 64-bit reg into 32-bit op
    with pytest.raises(ValueError):
        and64(hw, Reg.AL)  # 32-bit reg into 64-bit op


def test_alu_class_logic_delegation():
    hw = Hardware()
    alu = Alu(hw)
    reg = RegTestHarness(hw.reg)

    reg.set(Reg.AL, Registers.from_int(0x0F0F0F0F, 4))
    reg.set(Reg.BL, Registers.from_int(0xFF00FF00, 4))

    alu.and32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x0F000F00
    assert hw.clock.cycles == 1

    alu.chs(Reg.AH)
    assert hw.clock.cycles == 2


# =============================================================================
# 7. Integer Absolute Value (abs_int32 / abs_int64)
# =============================================================================


def test_abs_int32():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # Positive integer: unchanged
    reg.set(Reg.AL, Registers.from_int(42, 4))
    abs_int32(hw, Reg.AL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 42
    assert not reg.get_flag(StatusFlag.OVERFLOW)
    assert not reg.get_flag(StatusFlag.SIGN)
    assert not reg.get_flag(StatusFlag.ZERO)

    # Zero
    reg.set(Reg.AL, Registers.from_int(0, 4))
    abs_int32(hw, Reg.AL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 0
    assert reg.get_flag(StatusFlag.ZERO)

    # Negative integer (-42 -> 42)
    reg.set(Reg.AL, Registers.from_int(-42, 4, signed=True))
    abs_int32(hw, Reg.AL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 42
    assert not reg.get_flag(StatusFlag.OVERFLOW)
    assert not reg.get_flag(StatusFlag.SIGN)

    # Min int32: -2147483648 (0x80000000) -> OVERFLOW
    reg.set(Reg.AL, Registers.from_int(0x80000000, 4))
    abs_int32(hw, Reg.AL)
    assert reg.get_flag(StatusFlag.OVERFLOW)
    assert reg.get_flag(StatusFlag.SIGN)


def test_abs_int64():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)

    # Positive integer: unchanged
    reg.set(Reg.AX, Registers.from_int(123456789, 8))
    abs_int64(hw, Reg.AX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 123456789
    assert not reg.get_flag(StatusFlag.OVERFLOW)
    assert not reg.get_flag(StatusFlag.SIGN)
    assert not reg.get_flag(StatusFlag.ZERO)

    # Zero
    reg.set(Reg.AX, Registers.from_int(0, 8))
    abs_int64(hw, Reg.AX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0
    assert reg.get_flag(StatusFlag.ZERO)

    # Negative integer (-123456789 -> 123456789)
    reg.set(Reg.AX, Registers.from_int(-123456789, 8, signed=True))
    abs_int64(hw, Reg.AX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 123456789
    assert not reg.get_flag(StatusFlag.OVERFLOW)
    assert not reg.get_flag(StatusFlag.SIGN)

    # Min int64: (1 << 63) -> OVERFLOW
    reg.set(Reg.AX, Registers.from_int(1 << 63, 8))
    abs_int64(hw, Reg.AX)
    assert reg.get_flag(StatusFlag.OVERFLOW)
    assert reg.get_flag(StatusFlag.SIGN)


# =============================================================================
# 8. Logic Error Paths & 64-bit Micro-Ops
# =============================================================================
def test_logic_core_error_paths():
    with pytest.raises(ValueError, match="Unsupported logic operation width"):
        logic_core(bytearray(2), bytearray(2), LogicOp.AND, width_bytes=2)

    with pytest.raises(ValueError, match="requires a second operand"):
        logic_core(bytearray(4), None, LogicOp.AND, width_bytes=4)

    with pytest.raises(ValueError, match="Unknown logic operation"):
        logic_core(bytearray(4), bytearray(4), cast(LogicOp, "UNKNOWN"), width_bytes=4)


def test_or64_xor64_not64():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(0x00000000FFFFFFFF, 8))
    reg.set(Reg.BX, Registers.from_int(0xFFFFFFFF00000000, 8))

    or64(hw, src=Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0xFFFFFFFFFFFFFFFF

    xor64(hw, src=Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x00000000FFFFFFFF

    not64(hw)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0xFFFFFFFF00000000
