"""Comprehensive unit tests for Radix-4 Modified Booth Multiplier (alu_booth_mul)."""

import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.alu.booth_mul import (
    booth_core,
    mul32,
    mul64,
    CYCLES_32,
    CYCLES_64,
)
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers
from fpu_emu.tests.testharness import RegTestHarness


# =============================================================================
# 1. 32-Bit Core Booth Multiplier Tests
# =============================================================================
@pytest.mark.parametrize(
    "m,q,expected_res64,expected_cf,expected_zf,expected_sf,expected_vf,desc",
    [
        # Zero operands
        (0, 0, 0, False, True, False, False, "0 * 0 -> 0"),
        (0, 12345, 0, False, True, False, False, "0 * 12345 -> 0"),
        (12345, 0, 0, False, True, False, False, "12345 * 0 -> 0"),
        # Positive * Positive (no overflow)
        (10, 20, 200, False, False, False, False, "10 * 20 -> 200"),
        (1000, 2000, 2000000, False, False, False, False, "1000 * 2000 -> 2000000"),
        (0x00007FFF, 2, 0x0000FFFE, False, False, False, False, "0x7FFF * 2 (fits in int32)"),
        # Positive * Negative & Negative * Positive (no overflow)
        (10, -20, (10 * -20) & 0xFFFFFFFFFFFFFFFF, False, False, True, False, "10 * -20 -> -200"),
        (-10, 20, (-10 * 20) & 0xFFFFFFFFFFFFFFFF, False, False, True, False, "-10 * 20 -> -200"),
        (-1, 5, -5 & 0xFFFFFFFFFFFFFFFF, False, False, True, False, "-1 * 5 -> -5"),
        (5, -1, -5 & 0xFFFFFFFFFFFFFFFF, False, False, True, False, "5 * -1 -> -5"),
        # Negative * Negative (no overflow)
        (-10, -20, 200, False, False, False, False, "-10 * -20 -> 200"),
        (-1, -1, 1, False, False, False, False, "-1 * -1 -> 1"),
        # Overflow cases (high 32-bit word AH != sign_extension(AL))
        (0x40000000, 2, 0x0000000080000000, False, False, False, True, "0x40000000 * 2 (overflows signed int32)"),
        (0x7FFFFFFF, 2, 0x00000000FFFFFFFE, False, False, False, True, "MaxInt32 * 2 (overflows signed int32)"),
        (
            0x7FFFFFFF,
            0x7FFFFFFF,
            (0x7FFFFFFF * 0x7FFFFFFF) & 0xFFFFFFFFFFFFFFFF,
            False,
            False,
            False,
            True,
            "MaxInt32 * MaxInt32",
        ),
        (-0x80000000, 1, 0xFFFFFFFF80000000, False, False, True, False, "MinInt32 * 1 -> fits in int32"),
        (-0x80000000, -1, 0x0000000080000000, False, False, False, True, "MinInt32 * -1 -> overflows int32 (+2^31)"),
        (-0x80000000, 2, (-0x80000000 * 2) & 0xFFFFFFFFFFFFFFFF, False, False, True, True, "MinInt32 * 2"),
    ],
)
def test_booth_core_32(m, q, expected_res64, expected_cf, expected_zf, expected_sf, expected_vf, desc):
    m_bytes = Registers.from_int(m & 0xFFFFFFFF, 4)
    q_bytes = Registers.from_int(q & 0xFFFFFFFF, 4)
    res_bytes, cf, zf, sf, vf = booth_core(m_bytes, q_bytes, width_bytes=4)

    res_int = Registers.to_int(res_bytes)
    assert res_int == expected_res64, f"Failed {desc}: result mismatch {hex(res_int)} != {hex(expected_res64)}"
    assert cf == expected_cf, f"Failed {desc}: CF mismatch"
    assert zf == expected_zf, f"Failed {desc}: ZF mismatch"
    assert sf == expected_sf, f"Failed {desc}: SF mismatch"
    assert vf == expected_vf, f"Failed {desc}: VF mismatch"


# =============================================================================
# 2. 64-Bit Core Booth Multiplier Tests
# =============================================================================
@pytest.mark.parametrize(
    "m,q,expected_res128,expected_cf,expected_zf,expected_sf,expected_vf,desc",
    [
        (0, 0, 0, False, True, False, False, "64-bit 0 * 0"),
        (100, 200, 20000, False, False, False, False, "64-bit 100 * 200 (no overflow)"),
        (-100, 200, (-100 * 200) & ((1 << 128) - 1), False, False, True, False, "64-bit -100 * 200"),
        (-100, -200, 20000, False, False, False, False, "64-bit -100 * -200"),
        # 64-bit overflow cases
        (
            0x4000000000000000,
            2,
            0x00000000000000008000000000000000,
            False,
            False,
            False,
            True,
            "64-bit 0x4000... * 2 overflows int64",
        ),
        (
            0x7FFFFFFFFFFFFFFF,
            2,
            (0x7FFFFFFFFFFFFFFF * 2) & ((1 << 128) - 1),
            False,
            False,
            False,
            True,
            "MaxInt64 * 2 overflows",
        ),
        (
            -0x8000000000000000,
            -1,
            0x00000000000000008000000000000000,
            False,
            False,
            False,
            True,
            "MinInt64 * -1 (+2^63) overflows",
        ),
        (
            -0x8000000000000000,
            1,
            (-0x8000000000000000) & ((1 << 128) - 1),
            False,
            False,
            True,
            False,
            "MinInt64 * 1 fits in int64",
        ),
    ],
)
def test_booth_core_64(m, q, expected_res128, expected_cf, expected_zf, expected_sf, expected_vf, desc):
    m_bytes = Registers.from_int(m & 0xFFFFFFFFFFFFFFFF, 8)
    q_bytes = Registers.from_int(q & 0xFFFFFFFFFFFFFFFF, 8)
    res_bytes, cf, zf, sf, vf = booth_core(m_bytes, q_bytes, width_bytes=8)

    res_int = Registers.to_int(res_bytes)
    assert res_int == expected_res128, f"Failed {desc}: result mismatch"
    assert cf == expected_cf, f"Failed {desc}: CF mismatch"
    assert zf == expected_zf, f"Failed {desc}: ZF mismatch"
    assert sf == expected_sf, f"Failed {desc}: SF mismatch"
    assert vf == expected_vf, f"Failed {desc}: VF mismatch"


# =============================================================================
# 3. Hardware Integration & Cycle Timing Tests
# =============================================================================
@pytest.mark.parametrize("src", [Reg.BL, Reg.DL, Reg.FL, Reg.BH, Reg.DH, Reg.FH])
def test_mul32_all_source_registers(src):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(3, 4))
    reg.set(src, Registers.from_int(7, 4))

    mul32(hw, src)

    assert hw.clock.cycles == CYCLES_32  # Exactly 16 cycles
    assert Registers.to_int(reg.peek(Reg.AL)) == 21
    assert Registers.to_int(reg.peek(Reg.AH)) == 0  # Upper 32 bits
    assert not reg.get_flag(StatusFlag.CARRY)
    assert not reg.get_flag(StatusFlag.ZERO)
    assert not reg.get_flag(StatusFlag.SIGN)
    assert not reg.get_flag(StatusFlag.OVERFLOW)


def test_mul32_overflow_sets_flags():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    # 0x40000000 * 2 = 0x80000000 (overflows signed 32-bit)
    reg.set(Reg.AL, Registers.from_int(0x40000000, 4))
    reg.set(Reg.BL, Registers.from_int(2, 4))

    mul32(hw, Reg.BL)

    assert hw.clock.cycles == CYCLES_32
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x80000000
    assert Registers.to_int(reg.peek(Reg.AH)) == 0x00000000
    assert reg.get_flag(StatusFlag.OVERFLOW) is True
    assert not reg.get_flag(StatusFlag.SIGN)  # MSB of product AH is 0


@pytest.mark.parametrize("src", [Reg.BX, Reg.DX, Reg.FX])
def test_mul64_all_source_registers(src):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(10, 8))
    reg.set(src, Registers.from_int(20, 8))

    mul64(hw, src)

    assert hw.clock.cycles == CYCLES_64  # Exactly 32 cycles
    assert Registers.to_int(reg.peek(Reg.AX)) == 200
    assert Registers.to_int(reg.peek(Reg.DX)) == 0  # Upper 64 bits to DX
    assert not reg.get_flag(StatusFlag.OVERFLOW)


def test_invalid_source_registers():
    hw = Hardware()
    with pytest.raises(ValueError):
        mul32(hw, Reg.AX)  # 64-bit reg into 32-bit op
    with pytest.raises(ValueError):
        mul64(hw, Reg.AL)  # 32-bit reg into 64-bit op


def test_alu_class_booth_delegation():
    hw = Hardware()
    alu = Alu(hw)
    reg = RegTestHarness(hw.reg)

    reg.set(Reg.AL, Registers.from_int(6, 4))
    reg.set(Reg.BL, Registers.from_int(7, 4))

    alu.mul32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 42
    assert hw.clock.cycles == CYCLES_32
