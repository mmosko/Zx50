"""Comprehensive unit tests for 12-Bit Exponent ALU (alu_exp12 / ieee754_exp)."""

import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.alu.ieee754_exp import (
    to_signed_12,
    from_signed_12,
    exp_core_add,
    exp_core_sub,
    exp_core_diff,
    exp_core_add_mul,
    exp_core_sub_div,
    exp_core_adj_norm,
    exp_add,
    exp_sub,
    exp_diff,
    exp_add_mul,
    exp_sub_div,
    exp_adj_norm,
    exp_inc,
    exp_dec,
    unpack_f32,
    pack_f32,
    unpack_f64,
    pack_f64,
    BIAS_F32,
    BIAS_F64,
    LIMIT_EXP_MAX,
    LIMIT_EXP_MIN,
)
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers


# =============================================================================
# 1. 12-Bit Signed Integer Helpers
# =============================================================================
@pytest.mark.parametrize(
    "raw_12,expected_signed",
    [
        (0x000, 0),
        (0x001, 1),
        (0x7FF, 2047),
        (0x800, -2048),
        (0xFFF, -1),
        (0xFE0, -32),
    ],
)
def test_to_signed_12(raw_12, expected_signed):
    assert to_signed_12(raw_12) == expected_signed
    assert from_signed_12(expected_signed) == raw_12


# =============================================================================
# 2. Exponent Addition / Subtraction Core Tests
# =============================================================================
@pytest.mark.parametrize(
    "ea,eb,expected_res,expected_ovf,expected_uf,desc",
    [
        (0, 0, 0, False, False, "0 + 0"),
        (10, 20, 30, False, False, "10 + 20"),
        (100, from_signed_12(-30), 70, False, False, "100 + (-30)"),
        (from_signed_12(-50), from_signed_12(-50), from_signed_12(-100), False, False, "-50 + (-50)"),
        # Overflow > +1023
        (1000, 24, 1024, True, False, "1000 + 24 -> 1024 (OVF)"),
        (LIMIT_EXP_MAX, 1, 1024, True, False, "1023 + 1 -> 1024 (OVF)"),
        # Underflow < -1022
        (from_signed_12(-1000), from_signed_12(-23), from_signed_12(-1023), False, True, "-1000 + (-23) -> -1023 (UF)"),
        (from_signed_12(LIMIT_EXP_MIN), from_signed_12(-1), from_signed_12(-1023), False, True, "-1022 + (-1) -> -1023 (UF)"),
    ],
)
def test_exp_core_add(ea, eb, expected_res, expected_ovf, expected_uf, desc):
    res, ovf, uf = exp_core_add(ea, eb)
    assert res == expected_res, f"Failed {desc}: result mismatch"
    assert ovf == expected_ovf, f"Failed {desc}: OVF mismatch"
    assert uf == expected_uf, f"Failed {desc}: UF mismatch"


@pytest.mark.parametrize(
    "ea,eb,expected_res,expected_ovf,expected_uf,desc",
    [
        (50, 20, 30, False, False, "50 - 20"),
        (20, 50, from_signed_12(-30), False, False, "20 - 50"),
        (0, 0, 0, False, False, "0 - 0"),
        (100, from_signed_12(-50), 150, False, False, "100 - (-50)"),
        # Overflow > +1023
        (1000, from_signed_12(-24), 1024, True, False, "1000 - (-24) -> 1024 (OVF)"),
        # Underflow < -1022
        (from_signed_12(-1000), 23, from_signed_12(-1023), False, True, "-1000 - 23 -> -1023 (UF)"),
    ],
)
def test_exp_core_sub(ea, eb, expected_res, expected_ovf, expected_uf, desc):
    res, ovf, uf = exp_core_sub(ea, eb)
    assert res == expected_res, f"Failed {desc}: result mismatch"
    assert ovf == expected_ovf, f"Failed {desc}: OVF mismatch"
    assert uf == expected_uf, f"Failed {desc}: UF mismatch"


# =============================================================================
# 3. Mantissa Alignment Exponent Difference Core Tests
# =============================================================================
@pytest.mark.parametrize(
    "ea,eb,expected_shift,expected_borrow,desc",
    [
        (130, 127, 3, False, "EA > EB by 3"),
        (127, 130, 3, True, "EA < EB by 3 (borrow/CF=True)"),
        (127, 127, 0, False, "EA == EB (shift=0, no borrow)"),
        (200, 100, 63, False, "Delta 100 clamped to 63 max C shift"),
        (100, 200, 63, True, "Delta -100 clamped to 63 with borrow"),
    ],
)
def test_exp_core_diff(ea, eb, expected_shift, expected_borrow, desc):
    _, shift_count, borrow = exp_core_diff(ea, eb)
    assert shift_count == expected_shift, f"Failed {desc}: shift_count mismatch"
    assert borrow == expected_borrow, f"Failed {desc}: borrow mismatch"


# =============================================================================
# 4. Multiplication & Division Exponent Calculation Tests
# =============================================================================
@pytest.mark.parametrize(
    "ea,eb,bias,expected_res,expected_ovf,expected_uf,expected_err,desc",
    [
        # F32 Normal: (127 + 128 - 127) = 128
        (127, 128, BIAS_F32, 128, False, False, False, "F32 1.0 * 2.0"),
        # F32 Underflow: (1 + 10 - 127) = -116 <= 0
        (1, 10, BIAS_F32, from_signed_12(-116), False, True, False, "F32 Underflow"),
        # F32 Overflow: (200 + 100 - 127) = 173 (fits)
        (200, 100, BIAS_F32, 173, False, False, False, "F32 Large normal"),
        # F32 Overflow > 254: (200 + 200 - 127) = 273 > 254
        (200, 200, BIAS_F32, 273, True, False, True, "F32 Overflow"),
        # F64 Normal: (1023 + 1024 - 1023) = 1024
        (1023, 1024, BIAS_F64, 1024, False, False, False, "F64 normal"),
        # F64 Overflow > 2046
        (2000, 2000, BIAS_F64, 2977, True, False, True, "F64 Overflow"),
    ],
)
def test_exp_core_add_mul(ea, eb, bias, expected_res, expected_ovf, expected_uf, expected_err, desc):
    res, ovf, uf, err = exp_core_add_mul(ea, eb, bias=bias)
    assert res == expected_res, f"Failed {desc}: result mismatch"
    assert ovf == expected_ovf, f"Failed {desc}: OVF mismatch"
    assert uf == expected_uf, f"Failed {desc}: UF mismatch"
    assert err == expected_err, f"Failed {desc}: ERR mismatch"


@pytest.mark.parametrize(
    "ea,eb,bias,expected_res,expected_ovf,expected_uf,expected_err,desc",
    [
        # F32 Normal: (130 - 128 + 127) = 129
        (130, 128, BIAS_F32, 129, False, False, False, "F32 normal div"),
        # F32 Underflow: (10 - 200 + 127) = -63 <= 0
        (10, 200, BIAS_F32, from_signed_12(-63), False, True, False, "F32 div underflow"),
        # F32 Overflow: (200 - 10 + 127) = 317 > 254
        (200, 10, BIAS_F32, 317, True, False, True, "F32 div overflow"),
    ],
)
def test_exp_core_sub_div(ea, eb, bias, expected_res, expected_ovf, expected_uf, expected_err, desc):
    res, ovf, uf, err = exp_core_sub_div(ea, eb, bias=bias)
    assert res == expected_res, f"Failed {desc}: result mismatch"
    assert ovf == expected_ovf, f"Failed {desc}: OVF mismatch"
    assert uf == expected_uf, f"Failed {desc}: UF mismatch"
    assert err == expected_err, f"Failed {desc}: ERR mismatch"


# =============================================================================
# 5. Post-Normalization Exponent Adjustment Tests
# =============================================================================
@pytest.mark.parametrize(
    "ea,shift_count,expected_res,expected_uf,desc",
    [
        (127, 3, 124, False, "Normal shift deduction"),
        (5, 5, 0, True, "Deduction down to 0 (underflow)"),
        (5, 10, from_signed_12(-5), True, "Deduction below 0 (underflow)"),
    ],
)
def test_exp_core_adj_norm(ea, shift_count, expected_res, expected_uf, desc):
    res, uf = exp_core_adj_norm(ea, shift_count)
    assert res == expected_res, f"Failed {desc}: result mismatch"
    assert uf == expected_uf, f"Failed {desc}: UF mismatch"


# =============================================================================
# 6. Hardware Mutating Functions & Timing Tests (1 Cycle Latency)
# =============================================================================
def test_exp_add_hardware():
    hw = Hardware()
    hw.reg.ea = 100
    hw.reg.eb = 50

    exp_add(hw)

    assert hw.clock.cycles == 1
    assert hw.reg.ea == 150
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert not hw.reg.get_flag(StatusFlag.UNDERFLOW)


def test_exp_sub_hardware():
    hw = Hardware()
    hw.reg.ea = 100
    hw.reg.eb = 40

    exp_sub(hw)

    assert hw.clock.cycles == 1
    assert hw.reg.ea == 60
    assert not hw.reg.get_flag(StatusFlag.OVERFLOW)


def test_exp_diff_hardware():
    hw = Hardware()
    # EA < EB -> should set C to difference and set CARRY flag
    hw.reg.ea = 120
    hw.reg.eb = 125

    exp_diff(hw)

    assert hw.clock.cycles == 1
    assert hw.reg.c == 5
    assert hw.reg.get_flag(StatusFlag.CARRY) is True

    # EA > EB -> CARRY flag cleared
    hw.reg.ea = 130
    hw.reg.eb = 120

    exp_diff(hw)

    assert hw.clock.cycles == 2
    assert hw.reg.c == 10
    assert hw.reg.get_flag(StatusFlag.CARRY) is False


def test_exp_inc_dec():
    hw = Hardware()
    hw.reg.ea = 127

    exp_inc(hw)
    assert hw.reg.ea == 128
    assert hw.clock.cycles == 1

    exp_dec(hw)
    assert hw.reg.ea == 127
    assert hw.clock.cycles == 2


def test_exp_adj_norm_hardware():
    hw = Hardware()
    hw.reg.ea = 130
    hw.reg.c = 4

    exp_adj_norm(hw)

    assert hw.clock.cycles == 1
    assert hw.reg.ea == 126
    assert not hw.reg.get_flag(StatusFlag.UNDERFLOW)


# =============================================================================
# 7. IEEE-754 Unpack & Pack Tests
# =============================================================================
def test_f32_unpack_and_pack_positive():
    hw = Hardware()
    # 1.0f in IEEE-754: 0x3F800000 (sign=0, exp=127, mantissa=0)
    hw.reg.testharness_set(Reg.AL, Registers.from_f32(1.0))

    sign = unpack_f32(hw, src=Reg.AL, dst_mantissa=Reg.AL, dst_exp=Reg.EA)

    assert sign == 0
    assert hw.reg.ea == 127
    # Mantissa left-justified with hidden bit at bit 31: (1 << 23) << 8 = 0x80000000
    assert Registers.to_int(hw.reg.get(Reg.AL)) == 0x80000000

    # Pack back
    pack_f32(hw, sign=sign, src_mantissa=Reg.AL, src_exp=Reg.EA, dst=Reg.AL)
    assert Registers.to_f32(hw.reg.get(Reg.AL)) == 1.0


def test_f32_unpack_and_pack_negative():
    hw = Hardware()
    # -2.5f in IEEE-754: 0xC0200000 (sign=1, exp=128, mantissa=0x200000)
    hw.reg.testharness_set(Reg.BL, Registers.from_f32(-2.5))

    sign = unpack_f32(hw, src=Reg.BL, dst_mantissa=Reg.BL, dst_exp=Reg.EB)

    assert sign == 1
    assert hw.reg.eb == 128
    # Hidden bit inserted and left-justified: (0x800000 | 0x200000) << 8 = 0xA0000000
    assert Registers.to_int(hw.reg.get(Reg.BL)) == 0xA0000000

    pack_f32(hw, sign=sign, src_mantissa=Reg.BL, src_exp=Reg.EB, dst=Reg.BL)
    assert Registers.to_f32(hw.reg.get(Reg.BL)) == -2.5


def test_f64_unpack_and_pack():
    hw = Hardware()
    hw.reg.testharness_set(Reg.AX, Registers.from_f64(-3.141592653589793))

    sign = unpack_f64(hw, src=Reg.AX, dst_mantissa=Reg.AX, dst_exp=Reg.EA)

    assert sign == 1
    assert hw.reg.ea == 1024  # Floor(log2(3.1415...)) = 1 -> exp = 1023 + 1 = 1024

    # Pack back
    pack_f64(hw, sign=sign, src_mantissa=Reg.AX, src_exp=Reg.EA, dst=Reg.AX)
    assert Registers.to_f64(hw.reg.get(Reg.AX)) == -3.141592653589793


# =============================================================================
# 8. Alu Class Delegation Tests
# =============================================================================
def test_alu_class_exp_delegation():
    hw = Hardware()
    alu = Alu(hw)

    hw.reg.ea = 100
    hw.reg.eb = 200

    alu.exp_diff()
    assert hw.reg.c == 63  # 100 clamped to 63
    assert hw.reg.get_flag(StatusFlag.CARRY) is True


# =============================================================================
# 9. Exponent Tie-Breaking & Default Sign Latching Regression Tests
# =============================================================================
@pytest.mark.parametrize(
    "ea,eb,mant_a,mant_b,sign_a,sign_b,expected_carry,expected_diff_sign,desc",
    [
        (127, 127, 0x80000000, 0xC0000000, 0, 1, True, True, "Equal exp, AL < BL -> borrow=True, DIFF_SIGN=True"),
        (127, 127, 0xC0000000, 0x80000000, 1, 1, False, False, "Equal exp, AL > BL -> borrow=False, DIFF_SIGN=False"),
        (127, 127, 0x80000000, 0x80000000, 0, 0, False, False, "Equal exp, AL == BL -> borrow=False, DIFF_SIGN=False"),
        (128, 127, 0x80000000, 0xC0000000, 1, 0, False, True, "EA > EB -> borrow=False, DIFF_SIGN=True"),
        (126, 127, 0xC0000000, 0x80000000, 0, 0, True, False, "EA < EB -> borrow=True, DIFF_SIGN=False"),
    ],
)
def test_exp_diff_tie_breaking_and_diff_sign(
    ea, eb, mant_a, mant_b, sign_a, sign_b, expected_carry, expected_diff_sign, desc
):
    """Verify that when EA == EB, exp_diff compares mantissas so |A| >= |B| holds after swap, and sets DIFF_SIGN."""
    hw = Hardware()
    hw.reg.ea = ea
    hw.reg.eb = eb
    hw.reg.testharness_set(Reg.AL, Registers.from_int(mant_a, 4))
    hw.reg.testharness_set(Reg.BL, Registers.from_int(mant_b, 4))
    hw.reg.sign_a = sign_a
    hw.reg.sign_b = sign_b

    exp_diff(hw)

    assert hw.reg.get_flag(StatusFlag.CARRY) == expected_carry, f"Failed {desc}: CARRY flag mismatch"
    assert hw.reg.get_flag(StatusFlag.DIFF_SIGN) == expected_diff_sign, f"Failed {desc}: DIFF_SIGN flag mismatch"


@pytest.mark.parametrize(
    "val_float,expected_sign_bit",
    [
        (-1.5, 1),
        (1.5, 0),
        (-100.25, 1),
        (42.0, 0),
    ],
)
def test_pack_f32_default_sign_from_sign_a(val_float, expected_sign_bit):
    """Verify pack_f32 without explicit sign argument defaults to hw.reg.sign_a."""
    hw = Hardware()
    hw.reg.testharness_set(Reg.AL, Registers.from_f32(val_float))
    unpack_f32(hw, src=Reg.AL, dst_mantissa=Reg.AL, dst_exp=Reg.EA)

    assert hw.reg.sign_a == expected_sign_bit

    # Pack without explicit sign parameter (as microcode does)
    pack_f32(hw, src_mantissa=Reg.AL, src_exp=Reg.EA, dst=Reg.AL)
    result = Registers.to_f32(hw.reg.get(Reg.AL))
    assert result == val_float


@pytest.mark.parametrize(
    "val_float,expected_sign_bit",
    [
        (-1.5, 1),
        (1.5, 0),
        (-3.141592653589793, 1),
        (2.718281828459045, 0),
    ],
)
def test_pack_f64_default_sign_from_sign_a(val_float, expected_sign_bit):
    """Verify pack_f64 without explicit sign argument defaults to hw.reg.sign_a."""
    hw = Hardware()
    hw.reg.testharness_set(Reg.AX, Registers.from_f64(val_float))
    unpack_f64(hw, src=Reg.AX, dst_mantissa=Reg.AX, dst_exp=Reg.EA)

    assert hw.reg.sign_a == expected_sign_bit

    # Pack without explicit sign parameter
    pack_f64(hw, src_mantissa=Reg.AX, src_exp=Reg.EA, dst=Reg.AX)
    result = Registers.to_f64(hw.reg.get(Reg.AX))
    assert result == val_float


@pytest.mark.parametrize(
    "ea,eb,mant_a,mant_b,sign_a,sign_b,expected_carry,expected_diff_sign,desc",
    [
        (1023, 1023, 0x8000000000000000, 0xC000000000000000, 0, 1, True, True, "Equal exp, AX < BX -> borrow=True, DIFF_SIGN=True"),
        (1023, 1023, 0xC000000000000000, 0x8000000000000000, 1, 1, False, False, "Equal exp, AX > BX -> borrow=False, DIFF_SIGN=False"),
        (1023, 1023, 0x8000000000000000, 0x8000000000000000, 0, 0, False, False, "Equal exp, AX == BX -> borrow=False, DIFF_SIGN=False"),
        (1024, 1023, 0x8000000000000000, 0xC000000000000000, 1, 0, False, True, "EA > EB -> borrow=False, DIFF_SIGN=True"),
        (1022, 1023, 0xC000000000000000, 0x8000000000000000, 0, 0, True, False, "EA < EB -> borrow=True, DIFF_SIGN=False"),
    ],
)
def test_exp_diff_tie_breaking_64bit(
    ea, eb, mant_a, mant_b, sign_a, sign_b, expected_carry, expected_diff_sign, desc
):
    """Verify that when EA == EB in 64-bit mode, exp_diff compares AX vs BX."""
    hw = Hardware()
    hw.reg.ea = ea
    hw.reg.eb = eb
    hw.reg.testharness_set(Reg.AX, Registers.from_int(mant_a, 8))
    hw.reg.testharness_set(Reg.BX, Registers.from_int(mant_b, 8))
    hw.reg.sign_a = sign_a
    hw.reg.sign_b = sign_b

    exp_diff(hw, reg=Reg.AX)

    assert hw.reg.get_flag(StatusFlag.CARRY) == expected_carry, f"Failed {desc}: CARRY flag mismatch"
    assert hw.reg.get_flag(StatusFlag.DIFF_SIGN) == expected_diff_sign, f"Failed {desc}: DIFF_SIGN flag mismatch"
