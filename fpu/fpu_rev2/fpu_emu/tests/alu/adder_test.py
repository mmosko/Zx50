"""Comprehensive unit tests for 32/64-bit adder primitive using pytest parametrization."""

import pytest
from fpu_emu.alu.adder import (
    adder_core,
    add32,
    adc32,
    sub32,
    sbb32,
    cmp32,
    add64,
    adc64,
    sub64,
    sbb64,
    cmp64,
)
from fpu_emu.alu.alu import Alu
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import HalfSelect, Reg, StatusFlag, Registers
from fpu_emu.tests.testharness import RegTestHarness


# =============================================================================
# 1. Core 32-Bit Addition Test Vectors
# =============================================================================
@pytest.mark.parametrize(
    "a,b,cin,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        # (a, b, cin, expected_res, cf, zf, sf, vf, description)
        (0, 0, 0, 0, False, True, False, False, "zero + zero"),
        (0, 0, 1, 1, False, False, False, False, "zero + zero + cin"),
        (10, 25, 0, 35, False, False, False, False, "small positive integers"),
        (100, 200, 1, 301, False, False, False, False, "small positive with cin"),
        # Unsigned boundary & carry out
        (0xFFFFFFFF, 1, 0, 0, True, True, False, False, "max uint32 + 1"),
        (0xFFFFFFFF, 0, 1, 0, True, True, False, False, "max uint32 + cin"),
        (0xFFFFFFFF, 0xFFFFFFFF, 0, 0xFFFFFFFE, True, False, True, False, "max uint32 + max uint32"),
        (0xFFFFFFFF, 0xFFFFFFFF, 1, 0xFFFFFFFF, True, False, True, False, "max uint32 + max uint32 + cin"),
        # Signed positive overflow (pos + pos = neg)
        (0x7FFFFFFF, 1, 0, 0x80000000, False, False, True, True, "max int32 + 1"),
        (0x7FFFFFFF, 0x7FFFFFFF, 0, 0xFFFFFFFE, False, False, True, True, "max int32 + max int32"),
        # Signed negative overflow (neg + neg = pos)
        (0x80000000, 0x80000000, 0, 0, True, True, False, True, "min int32 + min int32"),
        (0x80000000, 0xFFFFFFFF, 0, 0x7FFFFFFF, True, False, False, True, "min int32 + (-1)"),
        # Mixed sign addition
        (0xFFFFFFF6, 10, 0, 0, True, True, False, False, "(-10) + 10"),
        (0xFFFFFFF6, 5, 0, 0xFFFFFFFB, False, False, True, False, "(-10) + 5 = -5"),
        (10, 0xFFFFFFFB, 0, 5, True, False, False, False, "10 + (-5) = 5"),
    ],
)
def test_adder_core_add(a, b, cin, expected_res, exp_cf, exp_zf, exp_sf, exp_vf, desc):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(a, 4))
    reg.set(Reg.BL, Registers.from_int(b, 4))
    reg.set_ha_bus_mux(HalfSelect.LO)
    reg.set_hb_bus_mux(HalfSelect.LO, Reg.BL)
    res, cf, zf, sf, vf = adder_core(hw, cin=cin, sub=False)

    assert Registers.to_int(res) == expected_res, f"Failed {desc}: result mismatch"
    assert cf == exp_cf, f"Failed {desc}: CF mismatch (got {cf}, expected {exp_cf})"
    assert zf == exp_zf, f"Failed {desc}: ZF mismatch (got {zf}, expected {exp_zf})"
    assert sf == exp_sf, f"Failed {desc}: SF mismatch (got {sf}, expected {exp_sf})"
    assert vf == exp_vf, f"Failed {desc}: VF mismatch (got {vf}, expected {exp_vf})"


# =============================================================================
# 2. Core 32-Bit Subtraction Test Vectors
# =============================================================================
@pytest.mark.parametrize(
    "a,b,cin,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        # (a, b, cin, expected_res, cf, zf, sf, vf, description)
        (0, 0, 0, 0, False, True, False, False, "zero - zero"),
        (0, 0, 1, 0xFFFFFFFF, True, False, True, False, "zero - zero with borrow"),
        (25, 10, 0, 15, False, False, False, False, "25 - 10"),
        (25, 10, 1, 14, False, False, False, False, "25 - 10 with borrow"),
        (10, 10, 0, 0, False, True, False, False, "10 - 10 = 0"),
        # Unsigned borrow (A < B)
        (10, 25, 0, 0xFFFFFFF1, True, False, True, False, "10 - 25 = -15"),
        (0, 1, 0, 0xFFFFFFFF, True, False, True, False, "0 - 1 = -1"),
        (0, 0xFFFFFFFF, 0, 1, True, False, False, False, "0 - max uint32"),
        # Signed overflow on subtraction
        # Pos - Neg = Neg (Overflow: 0x7FFFFFFF - (-1) = 0x80000000)
        (0x7FFFFFFF, 0xFFFFFFFF, 0, 0x80000000, True, False, True, True, "max int32 - (-1)"),
        # Neg - Pos = Pos (Overflow: 0x80000000 - 1 = 0x7FFFFFFF)
        (0x80000000, 1, 0, 0x7FFFFFFF, False, False, False, True, "min int32 - 1"),
    ],
)
def test_adder_core_sub(a, b, cin, expected_res, exp_cf, exp_zf, exp_sf, exp_vf, desc):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(a, 4))
    reg.set(Reg.BL, Registers.from_int(b, 4))
    reg.set_ha_bus_mux(HalfSelect.LO)
    reg.set_hb_bus_mux(HalfSelect.LO, Reg.BL)
    res, cf, zf, sf, vf = adder_core(hw, cin=cin, sub=True)

    assert Registers.to_int(res) == expected_res, f"Failed {desc}: result mismatch"
    assert cf == exp_cf, f"Failed {desc}: CF mismatch (got {cf}, expected {exp_cf})"
    assert zf == exp_zf, f"Failed {desc}: ZF mismatch (got {zf}, expected {exp_zf})"
    assert sf == exp_sf, f"Failed {desc}: SF mismatch (got {sf}, expected {exp_sf})"
    assert vf == exp_vf, f"Failed {desc}: VF mismatch (got {vf}, expected {exp_vf})"


# =============================================================================
# 3. 64-Bit Arithmetic Test Vectors
# =============================================================================
@pytest.mark.parametrize(
    "a64,b64,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        # (a64, b64, expected_res, cf, zf, sf, vf, desc)
        (0, 0, 0, False, True, False, False, "zero + zero 64"),
        (100, 200, 300, False, False, False, False, "small pos 64"),
        # Crossing 32-bit boundary
        (0x00000000FFFFFFFF, 1, 0x0000000100000000, False, False, False, False, "32-bit boundary carry"),
        (0x00000001FFFFFFFF, 1, 0x0000000200000000, False, False, False, False, "multi-word ripple"),
        # 64-bit carry out
        (0xFFFFFFFFFFFFFFFF, 1, 0, True, True, False, False, "max uint64 + 1"),
        # 64-bit signed overflow
        (0x7FFFFFFFFFFFFFFF, 1, 0x8000000000000000, False, False, True, True, "max int64 + 1"),
        (0x8000000000000000, 0x8000000000000000, 0, True, True, False, True, "min int64 + min int64"),
    ],
)
def test_add64_operations(a64, b64, expected_res, exp_cf, exp_zf, exp_sf, exp_vf, desc):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(a64, 8))
    reg.set(Reg.BX, Registers.from_int(b64, 8))

    add64(hw, Reg.BX)

    assert hw.clock.cycles == 2, "64-bit add must consume exactly 2 cycles"
    assert Registers.to_int(reg.peek(Reg.AX)) == expected_res, f"Failed {desc}: result mismatch"
    assert reg.get_flag(StatusFlag.CARRY) == exp_cf, f"Failed {desc}: CF mismatch"
    assert reg.get_flag(StatusFlag.ZERO) == exp_zf, f"Failed {desc}: ZF mismatch"
    assert reg.get_flag(StatusFlag.SIGN) == exp_sf, f"Failed {desc}: SF mismatch"
    assert reg.get_flag(StatusFlag.OVERFLOW) == exp_vf, f"Failed {desc}: VF mismatch"


@pytest.mark.parametrize(
    "a64,b64,expected_res,exp_cf,exp_zf,exp_sf,exp_vf,desc",
    [
        # (a64, b64, expected_res, cf, zf, sf, vf, desc)
        (0, 0, 0, False, True, False, False, "zero - zero 64"),
        (500, 200, 300, False, False, False, False, "500 - 200"),
        # Borrow across 32-bit boundary
        (0x0000000100000000, 1, 0x00000000FFFFFFFF, False, False, False, False, "borrow across low/high word"),
        # Unsigned borrow (A < B)
        (10, 20, 0xFFFFFFFFFFFFFFF6, True, False, True, False, "10 - 20 = -10 (64-bit)"),
        # 64-bit signed overflow
        (0x8000000000000000, 1, 0x7FFFFFFFFFFFFFFF, False, False, False, True, "min int64 - 1"),
    ],
)
def test_sub64_operations(a64, b64, expected_res, exp_cf, exp_zf, exp_sf, exp_vf, desc):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(a64, 8))
    reg.set(Reg.DX, Registers.from_int(b64, 8))

    sub64(hw, Reg.DX)

    assert hw.clock.cycles == 2, "64-bit sub must consume exactly 2 cycles"
    assert Registers.to_int(reg.peek(Reg.AX)) == expected_res, f"Failed {desc}: result mismatch"
    assert reg.get_flag(StatusFlag.CARRY) == exp_cf, f"Failed {desc}: CF mismatch"
    assert reg.get_flag(StatusFlag.ZERO) == exp_zf, f"Failed {desc}: ZF mismatch"
    assert reg.get_flag(StatusFlag.SIGN) == exp_sf, f"Failed {desc}: SF mismatch"
    assert reg.get_flag(StatusFlag.OVERFLOW) == exp_vf, f"Failed {desc}: VF mismatch"


# =============================================================================
# 4. Multi-Register Parametrization (Source Register Permutations)
# =============================================================================
@pytest.mark.parametrize("src_reg", [Reg.BL, Reg.DL, Reg.FL, Reg.BH, Reg.DH, Reg.FH])
def test_add32_all_valid_sources(src_reg):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(50, 4))
    reg.set(src_reg, Registers.from_int(25, 4))

    add32(hw, src_reg)

    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AL)) == 75


@pytest.mark.parametrize("src_reg", [Reg.BX, Reg.DX, Reg.FX])
def test_add64_all_valid_sources(src_reg):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(0x100000000, 8))
    reg.set(src_reg, Registers.from_int(0x200000000, 8))

    add64(hw, src_reg)

    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x300000000


# =============================================================================
# 5. ADC, SBB, and CMP Specialized Checks
# =============================================================================
def test_adc32_with_initial_carry():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(10, 4))
    reg.set(Reg.BL, Registers.from_int(20, 4))
    reg.set_flag(StatusFlag.CARRY, True)

    adc32(hw, Reg.BL)
    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AL)) == 31


def test_sbb32_with_initial_borrow():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(50, 4))
    reg.set(Reg.BL, Registers.from_int(20, 4))
    reg.set_flag(StatusFlag.CARRY, True)

    sbb32(hw, Reg.BL)
    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AL)) == 29


def test_cmp32_preserves_al():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(42, 4))
    reg.set(Reg.BL, Registers.from_int(42, 4))

    cmp32(hw, Reg.BL)
    assert hw.clock.cycles == 1
    assert Registers.to_int(reg.peek(Reg.AL)) == 42
    assert reg.get_flag(StatusFlag.ZERO) is True


def test_cmp64_preserves_ax():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    val = 0x123456789ABCDEF0
    reg.set(Reg.AX, Registers.from_int(val, 8))
    reg.set(Reg.DX, Registers.from_int(val, 8))

    cmp64(hw, Reg.DX)
    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.AX)) == val
    assert reg.get_flag(StatusFlag.ZERO) is True


def test_invalid_source_registers():
    hw = Hardware()
    with pytest.raises(ValueError):
        add32(hw, Reg.AX)
    with pytest.raises(ValueError):
        add64(hw, Reg.AL)


def test_alu_class_delegation():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    reg.set(Reg.AL, Registers.from_int(15, 4))
    reg.set(Reg.BL, Registers.from_int(25, 4))

    alu.add32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 40


def test_adc64_and_sbb64():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AX, Registers.from_int(100, 8))
    reg.set(Reg.BX, Registers.from_int(200, 8))
    reg.set_flag(StatusFlag.CARRY, True)

    adc64(hw, Reg.BX)
    assert hw.clock.cycles == 2
    assert Registers.to_int(reg.peek(Reg.AX)) == 301

    reg.set(Reg.AX, Registers.from_int(500, 8))
    reg.set(Reg.BX, Registers.from_int(200, 8))
    reg.set_flag(StatusFlag.CARRY, True)

    sbb64(hw, Reg.BX)
    assert hw.clock.cycles == 4
    assert Registers.to_int(reg.peek(Reg.AX)) == 299


def test_adder_core_invalid_operand_length():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg._reg._al = bytearray(2)
    reg.set_ha_bus_mux(HalfSelect.LO)
    reg.set_hb_bus_mux(HalfSelect.LO, Reg.BL)
    with pytest.raises(ValueError, match="Operands must be 4 bytes each"):
        adder_core(hw)


def test_sub32_direct():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    reg.set(Reg.AL, Registers.from_int(50, 4))
    reg.set(Reg.BL, Registers.from_int(20, 4))
    sub32(hw, Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 30
    assert hw.clock.cycles == 1


def test_select_hb_invalid_reg():
    from fpu_emu.alu.adder import _select_hb
    hw = Hardware()
    with pytest.raises(ValueError, match="Invalid source register for HB_BUS"):
        _select_hb(hw, Reg.SP)

