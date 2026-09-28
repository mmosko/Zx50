"""Unit tests for Registers class and Reg enum."""

import unittest
from fpu_emu.memory.registers import Reg, Registers, StatusFlag


class TestRegisters(unittest.TestCase):
    """Test suite for physical and logical FPU registers."""

    def setUp(self):
        self.regs = Registers()

    def test_initial_state(self):
        """Verify registers are initialized to zero."""
        for r in (Reg.AL, Reg.AH, Reg.BL, Reg.BH, Reg.DL, Reg.DH, Reg.FL, Reg.FH):
            self.assertEqual(self.regs.get(r), bytearray(4))
        self.assertEqual(self.regs.get(Reg.EA), bytearray(2))
        self.assertEqual(self.regs.get(Reg.EB), bytearray(2))
        self.assertEqual(self.regs.get(Reg.C), bytearray(1))
        self.assertEqual(self.regs.get(Reg.STATUS), bytearray(1))
        self.assertEqual(self.regs.get(Reg.SP), bytearray(1))
        self.assertEqual(self.regs.get(Reg.OSP), bytearray(1))
        self.assertEqual(self.regs.get(Reg.UPC), bytearray(2))

        self.assertEqual(self.regs.status, 0)
        self.assertEqual(self.regs.sp, 0)
        self.assertEqual(self.regs.osp, 0)
        self.assertEqual(self.regs.c, 0)
        self.assertEqual(self.regs.upc, 0)

    def test_32bit_registers_get_set(self):
        """Test read, write, copy isolation, and validation for 32-bit registers."""
        test_val = bytearray([0x12, 0x34, 0x56, 0x78])

        for r in (Reg.AL, Reg.AH, Reg.BL, Reg.BH, Reg.DL, Reg.DH, Reg.FL, Reg.FH):
            self.regs.set(r, test_val)
            ret = self.regs.get(r)
            self.assertEqual(ret, test_val)

            # Verify copy isolation (modifying returned bytearray doesn't affect register)
            ret[0] = 0xFF
            self.assertEqual(self.regs.get(r), test_val)

        # Test string register name lookup
        self.regs.set("al", bytearray([0xAA, 0xBB, 0xCC, 0xDD]))
        self.assertEqual(self.regs.get("AL"), bytearray([0xAA, 0xBB, 0xCC, 0xDD]))

        # Test invalid type
        with self.assertRaises(TypeError):
            self.regs.set(Reg.AL, 1234)  # type: ignore

        # Test invalid lengths
        with self.assertRaises(ValueError):
            self.regs.set(Reg.AL, bytearray([1, 2, 3]))
        with self.assertRaises(ValueError):
            self.regs.set(Reg.AL, bytearray([1, 2, 3, 4, 5]))

    def test_64bit_compound_registers(self):
        """Test 64-bit compound registers AX, BX, DX, FX mapping to low/high pairs."""
        raw_64 = bytearray([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])

        # Test AX
        self.regs.set(Reg.AX, raw_64)
        self.assertEqual(self.regs.get(Reg.AX), raw_64)
        self.assertEqual(self.regs.get(Reg.AL), bytearray([0x01, 0x02, 0x03, 0x04]))
        self.assertEqual(self.regs.get(Reg.AH), bytearray([0x05, 0x06, 0x07, 0x08]))

        # Modify AL and check AX updates
        self.regs.set(Reg.AL, bytearray([0xAA, 0xBB, 0xCC, 0xDD]))
        self.assertEqual(
            self.regs.ax,
            bytearray([0xAA, 0xBB, 0xCC, 0xDD, 0x05, 0x06, 0x07, 0x08]),
        )

        # Modify AH and check AX updates
        self.regs.set(Reg.AH, bytearray([0x11, 0x22, 0x33, 0x44]))
        self.assertEqual(
            self.regs.ax,
            bytearray([0xAA, 0xBB, 0xCC, 0xDD, 0x11, 0x22, 0x33, 0x44]),
        )

        # Test property setter
        self.regs.ax = raw_64
        self.assertEqual(self.regs.get(Reg.AX), raw_64)

        # Test BX, DX, FX
        for comp_reg, low_reg, high_reg in (
            (Reg.BX, Reg.BL, Reg.BH),
            (Reg.DX, Reg.DL, Reg.DH),
            (Reg.FX, Reg.FL, Reg.FH),
        ):
            self.regs.set(comp_reg, raw_64)
            self.assertEqual(self.regs.get(comp_reg), raw_64)
            self.assertEqual(self.regs.get(low_reg), raw_64[0:4])
            self.assertEqual(self.regs.get(high_reg), raw_64[4:8])

        # Test length validation for compound registers
        with self.assertRaises(ValueError):
            self.regs.set(Reg.AX, bytearray(4))
        with self.assertRaises(ValueError):
            self.regs.set(Reg.AX, bytearray(9))

    def test_exponent_registers(self):
        """Test EA and EB 2-byte registers."""
        val = bytearray([0x7F, 0x00])
        self.regs.set(Reg.EA, val)
        self.assertEqual(self.regs.get(Reg.EA), val)

        self.regs.set(Reg.EB, bytearray([0x01, 0x04]))
        self.assertEqual(self.regs.get(Reg.EB), bytearray([0x01, 0x04]))

        with self.assertRaises(ValueError):
            self.regs.set(Reg.EA, bytearray(1))

    def test_counter_and_pointers(self):
        """Test C counter, SP, OSP, and UPC."""
        # C is 6-bit (0..63)
        self.regs.c = 42
        self.assertEqual(self.regs.c, 42)
        self.assertEqual(self.regs.get(Reg.C), bytearray([42]))
        # 6-bit masking
        self.regs.c = 0xFF
        self.assertEqual(self.regs.c, 0x3F)

        # SP is 8-bit
        self.regs.sp = 0xA5
        self.assertEqual(self.regs.sp, 0xA5)
        self.assertEqual(self.regs.get(Reg.SP), bytearray([0xA5]))

        # OSP is 8-bit (5-bit hardware usage)
        self.regs.osp = 0x1F
        self.assertEqual(self.regs.osp, 0x1F)
        self.assertEqual(self.regs.get(Reg.OSP), bytearray([0x1F]))

        # UPC is 10-bit (0..1023)
        self.regs.upc = 0x2A5
        self.assertEqual(self.regs.upc, 0x2A5)
        self.assertEqual(self.regs.get(Reg.UPC), bytearray([0xA5, 0x02]))
        # 10-bit masking
        self.regs.upc = 0xFFFF
        self.assertEqual(self.regs.upc, 0x3FF)

    def test_status_flags(self):
        """Test individual status flag bitweights and operations."""
        # Bit assignments:
        # ERR=1 (0x02), UNDERFLOW=2 (0x04), OVERFLOW=3 (0x08),
        # CARRY=4 (0x10), SIGN=5 (0x20), ZERO=6 (0x40), BUSY=7 (0x80)
        expected_bits = {
            StatusFlag.ERR: 0x02,
            StatusFlag.UNDERFLOW: 0x04,
            StatusFlag.OVERFLOW: 0x08,
            StatusFlag.CARRY: 0x10,
            StatusFlag.SIGN: 0x20,
            StatusFlag.ZERO: 0x40,
            StatusFlag.BUSY: 0x80,
        }

        for flag, bitmask in expected_bits.items():
            self.regs.clear_flags()
            self.assertFalse(self.regs.get_flag(flag))
            self.assertEqual(self.regs.status, 0)

            self.regs.set_flag(flag)
            self.assertTrue(self.regs.get_flag(flag))
            self.assertEqual(self.regs.status, bitmask)

            self.regs.clr_flag(flag)
            self.assertFalse(self.regs.get_flag(flag))
            self.assertEqual(self.regs.status, 0)

        # Test multiple flags active simultaneously
        self.regs.clear_flags()
        self.regs.set_flag(StatusFlag.BUSY)
        self.regs.set_flag(StatusFlag.ZERO)
        self.regs.set_flag(StatusFlag.CARRY)
        self.assertEqual(self.regs.status, 0x80 | 0x40 | 0x10)
        self.assertTrue(self.regs.get_flag(StatusFlag.BUSY))
        self.assertTrue(self.regs.get_flag(StatusFlag.ZERO))
        self.assertTrue(self.regs.get_flag(StatusFlag.CARRY))
        self.assertFalse(self.regs.get_flag(StatusFlag.SIGN))

    def test_reset(self):
        """Test hardware reset clears all registers and asserts ZERO flag (0x40)."""
        self.regs.set(Reg.AL, bytearray([1, 2, 3, 4]))
        self.regs.set(Reg.AX, bytearray([1, 2, 3, 4, 5, 6, 7, 8]))
        self.regs.set(Reg.DL, bytearray([9, 9, 9, 9]))
        self.regs.sp = 16
        self.regs.osp = 4
        self.regs.c = 10
        self.regs.upc = 250
        self.regs.set_flag(StatusFlag.BUSY)

        self.regs.reset()

        for r in (Reg.AL, Reg.AH, Reg.BL, Reg.BH, Reg.DL, Reg.DH, Reg.FL, Reg.FH):
            self.assertEqual(self.regs.get(r), bytearray(4))
        self.assertEqual(self.regs.sp, 0)
        self.assertEqual(self.regs.osp, 0)
        self.assertEqual(self.regs.c, 0)
        self.assertEqual(self.regs.upc, 0)
        # Status should have ZERO=1 (0x40) per spec
        self.assertEqual(self.regs.status, 0x40)
        self.assertTrue(self.regs.get_flag(StatusFlag.ZERO))
        self.assertFalse(self.regs.get_flag(StatusFlag.BUSY))

    def test_integer_conversion_helpers(self):
        """Test from_int and to_int Little-Endian conversion utilities."""
        # 32-bit unsigned
        b = Registers.from_int(0x12345678, 4)
        self.assertEqual(b, bytearray([0x78, 0x56, 0x34, 0x12]))
        self.assertEqual(Registers.to_int(b), 0x12345678)

        # 32-bit signed negative
        b_neg = Registers.from_int(-1, 4, signed=True)
        self.assertEqual(b_neg, bytearray([0xFF, 0xFF, 0xFF, 0xFF]))
        self.assertEqual(Registers.to_int(b_neg, signed=True), -1)

        # 64-bit integer
        val64 = 0x0102030405060708
        b64 = Registers.from_int(val64, 8)
        self.assertEqual(Registers.to_int(b64), val64)

    def test_float_conversion_helpers(self):
        """Test from_f32, to_f32, from_f64, and to_f64 IEEE-754 helpers."""
        import math

        # 32-bit float: 1.0f -> 0x3F800000
        b_f32 = Registers.from_f32(1.0)
        self.assertEqual(b_f32, bytearray([0x00, 0x00, 0x80, 0x3F]))
        self.assertEqual(Registers.to_f32(b_f32), 1.0)

        # 32-bit float: -1.0f -> 0xBF800000
        b_neg_f32 = Registers.from_f32(-1.0)
        self.assertEqual(b_neg_f32, bytearray([0x00, 0x00, 0x80, 0xBF]))
        self.assertEqual(Registers.to_f32(b_neg_f32), -1.0)

        # 32-bit float round-trips
        for val in [0.0, -0.0, 2.5, -128.75, 1e-10, 1e10]:
            b = Registers.from_f32(val)
            self.assertEqual(len(b), 4)
            self.assertAlmostEqual(Registers.to_f32(b), val, places=6)

        # 64-bit double: 1.0 -> 0x3FF0000000000000
        b_f64 = Registers.from_f64(1.0)
        self.assertEqual(b_f64, bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xF0, 0x3F]))
        self.assertEqual(Registers.to_f64(b_f64), 1.0)

        # 64-bit double: -1.0 -> 0xBFF0000000000000
        b_neg_f64 = Registers.from_f64(-1.0)
        self.assertEqual(b_neg_f64, bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xF0, 0xBF]))
        self.assertEqual(Registers.to_f64(b_neg_f64), -1.0)

        # 64-bit double round-trips
        for val in [0.0, -0.0, 3.141592653589793, -1.23456789e-50, 1e100]:
            b = Registers.from_f64(val)
            self.assertEqual(len(b), 8)
            self.assertEqual(Registers.to_f64(b), val)

        # Special values: inf, -inf, nan
        self.assertTrue(math.isinf(Registers.to_f32(Registers.from_f32(float("inf")))))
        self.assertTrue(math.isinf(Registers.to_f64(Registers.from_f64(float("-inf")))))
        self.assertTrue(math.isnan(Registers.to_f32(Registers.from_f32(float("nan")))))
        self.assertTrue(math.isnan(Registers.to_f64(Registers.from_f64(float("nan")))))

        # Length validation
        with self.assertRaises(ValueError):
            Registers.to_f32(bytearray(3))
        with self.assertRaises(ValueError):
            Registers.to_f32(bytearray(8))
        with self.assertRaises(ValueError):
            Registers.to_f64(bytearray(4))
        with self.assertRaises(ValueError):
            Registers.to_f64(bytearray(16))

    def test_dump_and_repr(self):
        """Test dump formatting and repr."""
        self.regs.sp = 0x20
        self.regs.set_flag(StatusFlag.ZERO)
        dump_str = self.regs.dump()
        self.assertIn("AL:", dump_str)
        self.assertIn("STATUS: 0x40 [Z]", dump_str)
        self.assertIn("SP: 20", dump_str)

        repr_str = repr(self.regs)
        self.assertIn("SP=20", repr_str)
        self.assertIn("STATUS=40", repr_str)


if __name__ == "__main__":
    unittest.main()
