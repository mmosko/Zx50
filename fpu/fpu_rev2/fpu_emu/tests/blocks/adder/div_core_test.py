"""Unit tests for DivCore (Radix-2 Non-Restoring Divider)."""

import pytest
from fpu_emu.blocks.adder.div_core import DivCore

MASK_32 = 0xFFFFFFFF
SIGN_32 = 0x80000000


def to_bytes32(val: int, signed: bool = False) -> bytes:
    """Helper to convert integer to 4-byte little-endian bytes."""
    return (val & MASK_32).to_bytes(4, byteorder="little", signed=False)


from typing import Union


def from_bytes32_unsigned(b: Union[bytes, bytearray]) -> int:
    return int.from_bytes(b, byteorder="little", signed=False)


def from_bytes32_signed(b: Union[bytes, bytearray]) -> int:
    return int.from_bytes(b, byteorder="little", signed=True)


class TestDivCore:
    def test_invalid_lengths(self):
        with pytest.raises(ValueError, match="Operands must be 4 bytes each"):
            DivCore.div_core(b"\x00\x00", b"\x00\x00\x00\x00")

        with pytest.raises(ValueError, match="Operands must be 4 bytes each"):
            DivCore.div_core(b"\x00\x00\x00\x00", b"\x00\x00")

    def test_divide_by_zero(self):
        a = to_bytes32(23)
        b = to_bytes32(0)
        res = DivCore.div_core(a, b, signed=True)
        assert res.err is True
        assert res.vf is True
        assert res.zf is False
        assert res.sf is False
        assert res.cf is False
        assert from_bytes32_unsigned(res.quotient) == 0
        assert from_bytes32_unsigned(res.remainder) == 0

    def test_divide_by_zero_unsigned(self):
        a = to_bytes32(100)
        b = to_bytes32(0)
        res = DivCore.div_core(a, b, signed=False)
        assert res.err is True
        assert res.vf is True

    @pytest.mark.parametrize(
        "a, b, expected_q, expected_r, desc",
        [
            (23, 5, 4, 3, "23 / 5 = 4 rem 3 (SystemReference example)"),
            (100, 10, 10, 0, "Exact division: 100 / 10 = 10 rem 0"),
            (7, 3, 2, 1, "7 / 3 = 2 rem 1"),
            (5, 10, 0, 5, "Dividend smaller than divisor: 5 / 10 = 0 rem 5"),
            (42, 1, 42, 0, "Division by 1: 42 / 1 = 42 rem 0"),
            (0, 5, 0, 0, "Zero dividend: 0 / 5 = 0 rem 0"),
            (0x7FFFFFFF, 1, 0x7FFFFFFF, 0, "Max positive 32-bit int divided by 1"),
            (0x7FFFFFFF, 2, 0x3FFFFFFF, 1, "Max positive 32-bit int divided by 2"),
        ],
    )
    def test_signed_positive_division(
        self, a: int, b: int, expected_q: int, expected_r: int, desc: str
    ):
        res = DivCore.div_core(to_bytes32(a), to_bytes32(b), signed=True)
        assert not res.err, desc
        assert not res.vf, desc
        assert from_bytes32_signed(res.quotient) == expected_q, desc
        assert from_bytes32_signed(res.remainder) == expected_r, desc
        assert res.zf == (expected_q == 0), desc
        assert res.sf == (expected_q < 0), desc

    @pytest.mark.parametrize(
        "a, b, expected_q, expected_r, desc",
        [
            (-23, 5, -4, -3, "(-23) / 5 = -4 rem -3"),
            (23, -5, -4, 3, "23 / (-5) = -4 rem 3"),
            (-23, -5, 4, -3, "(-23) / (-5) = 4 rem -3"),
            (-7, 3, -2, -1, "(-7) / 3 = -2 rem -1"),
            (7, -3, -2, 1, "7 / (-3) = -2 rem 1"),
            (-7, -3, 2, -1, "(-7) / (-3) = 2 rem -1"),
            (-100, 10, -10, 0, "(-100) / 10 = -10 rem 0"),
            (100, -10, -10, 0, "100 / (-10) = -10 rem 0"),
            (-100, -10, 10, 0, "(-100) / (-10) = 10 rem 0"),
            (-5, 10, 0, -5, "(-5) / 10 = 0 rem -5"),
        ],
    )
    def test_signed_negative_division(
        self, a: int, b: int, expected_q: int, expected_r: int, desc: str
    ):
        res = DivCore.div_core(to_bytes32(a), to_bytes32(b), signed=True)
        assert not res.err, desc
        assert not res.vf, desc
        assert from_bytes32_signed(res.quotient) == expected_q, desc
        assert from_bytes32_signed(res.remainder) == expected_r, desc
        assert res.zf == (expected_q == 0), desc
        assert res.sf == (expected_q < 0), desc

    def test_signed_overflow_min_int(self):
        """0x80000000 (-2147483648) / -1 causes signed overflow."""
        a = to_bytes32(-0x80000000)
        b = to_bytes32(-1)
        res = DivCore.div_core(a, b, signed=True)
        assert res.vf is True
        assert res.err is False
        assert res.sf is True
        assert res.zf is False
        assert from_bytes32_unsigned(res.quotient) == 0x80000000
        assert from_bytes32_unsigned(res.remainder) == 0

    @pytest.mark.parametrize(
        "a, b, expected_q, expected_r, desc",
        [
            (0xFFFFFFFF, 2, 0x7FFFFFFF, 1, "0xFFFFFFFF / 2"),
            (0xFFFFFFFF, 0x10000, 0xFFFF, 0xFFFF, "0xFFFFFFFF / 0x10000"),
            (0x80000000, 2, 0x40000000, 0, "0x80000000 / 2"),
            (0x80000000, 0x80000000, 1, 0, "0x80000000 / 0x80000000 = 1 rem 0"),
            (10, 20, 0, 10, "10 / 20 = 0 rem 10"),
            (0xFFFFFFFE, 1, 0xFFFFFFFE, 0, "Large / 1"),
        ],
    )
    def test_unsigned_division(
        self, a: int, b: int, expected_q: int, expected_r: int, desc: str
    ):
        res = DivCore.div_core(to_bytes32(a), to_bytes32(b), signed=False)
        assert not res.err, desc
        assert not res.vf, desc
        assert from_bytes32_unsigned(res.quotient) == expected_q, desc
        assert from_bytes32_unsigned(res.remainder) == expected_r, desc
        assert res.zf == (expected_q == 0), desc
        assert res.sf == bool(expected_q & SIGN_32), desc
