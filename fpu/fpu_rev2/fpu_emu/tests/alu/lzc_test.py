"""Comprehensive unit tests for 32/64-bit Leading-Zero Counter (alu_lzc)."""

import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.alu.lzc import lzc_core, lzc32, lzc64
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers


# =============================================================================
# 1. 32-Bit Core LZC Tests
# =============================================================================
@pytest.mark.parametrize(
    "val,expected_count,expected_zf,desc",
    [
        (0x00000000, 32, True, "32-bit zero -> 32 zeros, ZF=True"),
        (0x80000000, 0, False, "MSB set -> 0 zeros"),
        (0x40000000, 1, False, "Bit 30 set -> 1 zero"),
        (0x20000000, 2, False, "Bit 29 set -> 2 zeros"),
        (0x00FF0000, 8, False, "Byte 2 set -> 8 zeros"),
        (0x0000FFFF, 16, False, "Low halfword set -> 16 zeros"),
        (0x00000080, 24, False, "Bit 7 set -> 24 zeros"),
        (0x00000002, 30, False, "Bit 1 set -> 30 zeros"),
        (0x00000001, 31, False, "Bit 0 set -> 31 zeros"),
        (0xFFFFFFFF, 0, False, "All bits set -> 0 zeros"),
    ],
)
def test_lzc_core_32(val, expected_count, expected_zf, desc):
    val_bytes = Registers.from_int(val, 4)
    count, zf = lzc_core(val_bytes, width_bytes=4)

    assert count == expected_count, f"Failed {desc}: count mismatch"
    assert zf == expected_zf, f"Failed {desc}: ZF mismatch"


# =============================================================================
# 2. 64-Bit Core LZC Tests
# =============================================================================
@pytest.mark.parametrize(
    "val,expected_count,expected_zf,desc",
    [
        (0x0000000000000000, 64, True, "64-bit zero -> 64 zeros, ZF=True"),
        (0x8000000000000000, 0, False, "MSB set -> 0 zeros"),
        (0x4000000000000000, 1, False, "Bit 62 set -> 1 zero"),
        (0x0000000100000000, 31, False, "Bit 32 set -> 31 zeros"),
        (0x0000000080000000, 32, False, "Bit 31 set -> 32 zeros"),
        (0x000000000000FFFF, 48, False, "Low 16 bits set -> 48 zeros"),
        (0x0000000000000001, 63, False, "Bit 0 set -> 63 zeros"),
        (0xFFFFFFFFFFFFFFFF, 0, False, "All bits set -> 0 zeros"),
    ],
)
def test_lzc_core_64(val, expected_count, expected_zf, desc):
    val_bytes = Registers.from_int(val, 8)
    count, zf = lzc_core(val_bytes, width_bytes=8)

    assert count == expected_count, f"Failed {desc}: count mismatch"
    assert zf == expected_zf, f"Failed {desc}: ZF mismatch"


# =============================================================================
# 3. Hardware Integration & Flag/Timing Tests
# =============================================================================
def test_lzc32_hardware_integration():
    hw = Hardware()
    # Put 0x00010000 in AL (bit 16 set -> 15 leading zeros)
    hw.reg.set(Reg.AL, Registers.from_int(0x00010000, 4))
    hw.reg.set_flag(StatusFlag.SIGN, True)  # Pre-set sign to verify it gets cleared

    count = lzc32(hw)

    assert count == 15
    assert hw.reg.c == 15
    assert hw.clock.cycles == 1  # 1 cycle execution
    assert not hw.reg.get_flag(StatusFlag.ZERO)
    assert not hw.reg.get_flag(StatusFlag.SIGN)  # Cleared by LZC


def test_lzc32_zero_operand():
    hw = Hardware()
    hw.reg.set(Reg.AL, Registers.from_int(0, 4))

    count = lzc32(hw)

    assert count == 32
    assert hw.reg.c == 32
    assert hw.clock.cycles == 1
    assert hw.reg.get_flag(StatusFlag.ZERO) is True
    assert not hw.reg.get_flag(StatusFlag.SIGN)


def test_lzc64_hardware_integration():
    hw = Hardware()
    # 0x0000000000000008 -> 60 leading zeros
    hw.reg.set(Reg.AX, Registers.from_int(0x8, 8))

    count = lzc64(hw)

    assert count == 60
    assert hw.reg.c == 60
    assert hw.clock.cycles == 1  # 1 cycle priority tree
    assert not hw.reg.get_flag(StatusFlag.ZERO)
    assert not hw.reg.get_flag(StatusFlag.SIGN)


def test_alu_class_lzc_delegation():
    hw = Hardware()
    alu = Alu(hw)

    hw.reg.set(Reg.AL, Registers.from_int(0x00000001, 4))
    count = alu.lzc32()

    assert count == 31
    assert hw.reg.c == 31
    assert hw.clock.cycles == 1
