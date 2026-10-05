"""Unit tests for Radix-4 Modified Booth Multiplier primitive (BoothMulCore)."""

import pytest
from fpu_emu.blocks.adder.booth_mul import BoothMulCore, BoothMulResult


def to_bytes(val: int, signed: bool = False) -> bytes:
    """Helper to pack 32-bit int into 4-byte little-endian bytes."""
    val &= 0xFFFFFFFF
    return val.to_bytes(4, byteorder="little", signed=False)


def to_product_int(res: bytearray) -> int:
    """Helper to convert 8-byte product into 64-bit unsigned int."""
    return int.from_bytes(res, byteorder="little", signed=False)


class TestBoothMulCore:
    def test_signed_basic_multiplication(self):
        # 3 * 5 = 15
        result = BoothMulCore.booth_mul_core(to_bytes(3), to_bytes(5), signed=True)
        assert to_product_int(result.res) == 15
        assert not result.cf
        assert not result.zf
        assert not result.sf
        assert not result.vf

        # 7 * -4 = -28
        result = BoothMulCore.booth_mul_core(to_bytes(7), to_bytes(-4), signed=True)
        assert to_product_int(result.res) == (-28 & 0xFFFFFFFFFFFFFFFF)
        assert not result.zf
        assert result.sf
        assert not result.vf

        # -6 * -9 = 54
        result = BoothMulCore.booth_mul_core(to_bytes(-6), to_bytes(-9), signed=True)
        assert to_product_int(result.res) == 54
        assert not result.zf
        assert not result.sf
        assert not result.vf

    def test_signed_zero(self):
        result = BoothMulCore.booth_mul_core(to_bytes(0), to_bytes(12345), signed=True)
        assert to_product_int(result.res) == 0
        assert result.zf
        assert not result.sf
        assert not result.cf
        assert not result.vf

    def test_signed_overflow(self):
        # Concrete example from SystemReference.md:
        # AL = 65536, BL = 131072 -> Product = 8,589,934,592 = 0x00000002_00000000
        # AH = 2, AL = 0, VF = 1
        result = BoothMulCore.booth_mul_core(to_bytes(65536), to_bytes(131072), signed=True)
        prod = to_product_int(result.res)
        assert prod == 0x00000002_00000000
        assert result.res[0:4] == to_bytes(0)
        assert result.res[4:8] == to_bytes(2)
        assert result.vf
        assert not result.zf
        assert not result.sf

        # Negative overflow: -100,000 * 100,000 = -10,000,000,000
        result = BoothMulCore.booth_mul_core(to_bytes(-100000), to_bytes(100000), signed=True)
        assert result.vf
        assert result.sf

    def test_signed_extreme_values(self):
        # Max positive: 0x7FFFFFFF * 1 = 0x7FFFFFFF (fits in 32-bit signed, VF=0)
        result = BoothMulCore.booth_mul_core(to_bytes(0x7FFFFFFF), to_bytes(1), signed=True)
        assert to_product_int(result.res) == 0x7FFFFFFF
        assert not result.vf

        # Max positive * 2: 0x7FFFFFFF * 2 = 0x00000000_FFFFFFFE (VF=1 because bit 31 set but AH=0)
        result = BoothMulCore.booth_mul_core(to_bytes(0x7FFFFFFF), to_bytes(2), signed=True)
        assert to_product_int(result.res) == 0xFFFFFFFE
        assert result.vf

        # Min negative: -0x80000000 * 1 = -0x80000000 (fits in 32-bit signed, VF=0, AH=0xFFFFFFFF)
        result = BoothMulCore.booth_mul_core(to_bytes(-0x80000000), to_bytes(1), signed=True)
        assert to_product_int(result.res) == (-0x80000000 & 0xFFFFFFFFFFFFFFFF)
        assert not result.vf
        assert result.sf

        # Min negative * -1: -0x80000000 * -1 = +0x80000000 (overflows signed 32-bit, VF=1)
        result = BoothMulCore.booth_mul_core(to_bytes(-0x80000000), to_bytes(-1), signed=True)
        assert to_product_int(result.res) == 0x80000000
        assert result.vf

        # Min negative * Min negative: -0x80000000 * -0x80000000 = 0x40000000_00000000
        result = BoothMulCore.booth_mul_core(to_bytes(-0x80000000), to_bytes(-0x80000000), signed=True)
        assert to_product_int(result.res) == 0x40000000_00000000
        assert result.vf

    def test_unsigned_multiplication(self):
        # Small unsigned
        result = BoothMulCore.booth_mul_core(to_bytes(3), to_bytes(5), signed=False)
        assert to_product_int(result.res) == 15
        assert not result.vf
        assert not result.zf

        # 0xFFFFFFFF * 1 = 0xFFFFFFFF (fits in 32-bit, VF=0)
        result = BoothMulCore.booth_mul_core(to_bytes(0xFFFFFFFF), to_bytes(1), signed=False)
        assert to_product_int(result.res) == 0xFFFFFFFF
        assert not result.vf

        # 0xFFFFFFFF * 2 = 0x1_FFFFFFFE (exceeds 32-bit, VF=1)
        result = BoothMulCore.booth_mul_core(to_bytes(0xFFFFFFFF), to_bytes(2), signed=False)
        assert to_product_int(result.res) == 0x1_FFFFFFFE
        assert result.vf

        # Max unsigned * Max unsigned: 0xFFFFFFFF * 0xFFFFFFFF = 0xFFFFFFFE_00000001
        result = BoothMulCore.booth_mul_core(to_bytes(0xFFFFFFFF), to_bytes(0xFFFFFFFF), signed=False)
        assert to_product_int(result.res) == 0xFFFFFFFE_00000001
        assert result.vf

        # Arbitrary 32-bit unsigned
        a = 0x12345678
        b = 0x87654321
        result = BoothMulCore.booth_mul_core(to_bytes(a), to_bytes(b), signed=False)
        assert to_product_int(result.res) == (a * b)
        assert result.vf

    def test_invalid_length(self):
        with pytest.raises(ValueError, match="Operands must be 4 bytes each"):
            BoothMulCore.booth_mul_core(b"\x01\x02\x03", to_bytes(1))

        with pytest.raises(ValueError, match="Operands must be 4 bytes each"):
            BoothMulCore.booth_mul_core(to_bytes(1), b"\x01\x02\x03\x04\x05")

    def test_resource_annotation(self):
        assert hasattr(BoothMulCore, "__fpga_resource__")
        res = getattr(BoothMulCore, "__fpga_resource__")
        assert res.shared_unit == "alu_booth_mul"
        assert res.luts == 77
        assert res.slices_ccu2c == 17
        assert res.ffs == 75
        assert res.delay_ns == 4.7
        assert res.cycles == 16
