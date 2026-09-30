"""Unit tests for Registers class, bus routing, timing enforcement, and access controls."""

import unittest
from fpu_emu.clock import Clock
from fpu_emu.memory.registers import (
    HalfSelect,
    HardwareAccessViolationError,
    HardwareBusError,
    HardwareTimingConflictError,
    Reg,
    Registers,
    StatusFlag,
)


class TestRegisters(unittest.TestCase):
    """Test suite for physical FPU register file and bus timing rules."""

    def setUp(self):
        self.clock = Clock()
        self.regs = Registers(clock=self.clock)

    def test_initial_state(self):
        """Verify registers are initialized to zero and status flags are reset."""
        for r in (Reg.AL, Reg.AH, Reg.BL, Reg.BH, Reg.DL, Reg.DH, Reg.FL, Reg.FH):
            self.assertEqual(self.regs.testharness_peek(r), bytearray(4))
        self.assertEqual(self.regs.testharness_peek(Reg.EA), bytearray(2))
        self.assertEqual(self.regs.testharness_peek(Reg.EB), bytearray(2))
        self.assertEqual(self.regs.testharness_peek(Reg.C), bytearray(1))

        # Allowed getters
        self.assertEqual(self.regs.get(Reg.STATUS), bytearray(1))
        self.assertEqual(self.regs.get(Reg.SP), bytearray(1))
        self.assertEqual(self.regs.get(Reg.OSP), bytearray(1))
        self.assertEqual(self.regs.get(Reg.UPC), bytearray(2))
        self.assertEqual(self.regs.get(Reg.C), bytearray(1))

        self.assertEqual(self.regs.status, 0)
        self.assertEqual(self.regs.sp, 0)
        self.assertEqual(self.regs.osp, 0)
        self.assertEqual(self.regs.c, 0)
        self.assertEqual(self.regs.upc, 0)

    def test_compound_properties_forbidden(self):
        """Verify compound register property getters do not exist on Registers."""
        for prop in ("ax", "bx", "dx", "fx"):
            self.assertFalse(hasattr(self.regs, prop), f"Property {prop} should not exist")

    def test_ha_bus_mux_and_read(self):
        """Test HA_BUS selecting AL (LO) vs AH (HI)."""
        self.regs.load_test_vector(Reg.AL, 0x11223344)
        self.regs.load_test_vector(Reg.AH, 0x55667788)

        # Before configuring HA_BUS MUX, read raises HardwareBusError
        with self.assertRaises(HardwareBusError):
            self.regs.read_ha_bus()

        # Select LO (AL)
        self.regs.set_ha_bus_mux(HalfSelect.LO)
        self.assertEqual(Registers.to_int(self.regs.read_ha_bus()), 0x11223344)

        # In the next clock cycle, select HI (AH)
        self.clock.tick(1)
        self.regs.set_ha_bus_mux(HalfSelect.HI)
        self.assertEqual(Registers.to_int(self.regs.read_ha_bus()), 0x55667788)

    def test_hb_bus_mux_and_read(self):
        """Test HB_BUS selecting halves of BX, DX, FX, AX, EA, EB, C."""
        self.regs.load_test_vector(Reg.BX, 0x0102030405060708)
        self.regs.load_test_vector(Reg.DX, 0x0A0B0C0D0E0F1011)

        # Before configuring HB_BUS MUX, read raises HardwareBusError
        with self.assertRaises(HardwareBusError):
            self.regs.read_hb_bus()

        # Read BL (BX, LO)
        self.regs.set_hb_mux(HalfSelect.LO, Reg.BX)
        self.assertEqual(Registers.to_int(self.regs.read_hb_bus()), 0x05060708)

        # Advance cycle, read BH (BX, HI)
        self.clock.tick(1)
        self.regs.set_hb_mux(HalfSelect.HI, Reg.BX)
        self.assertEqual(Registers.to_int(self.regs.read_hb_bus()), 0x01020304)

        # Advance cycle, read DL
        self.clock.tick(1)
        self.regs.set_hb_mux(HalfSelect.LO, Reg.DX)
        self.assertEqual(Registers.to_int(self.regs.read_hb_bus()), 0x0E0F1011)

        # Read EA (zero-extended 12 bits)
        self.clock.tick(1)
        self.regs.ea = 0x3FF
        self.regs.set_hb_mux(HalfSelect.LO, Reg.EA)
        self.assertEqual(Registers.to_int(self.regs.read_hb_bus()), 0x3FF)

    def test_ha_bus_timing_conflict(self):
        """Verify calling set_ha_bus_mux twice in same clock cycle raises HardwareTimingConflictError."""
        self.regs.set_ha_bus_mux(HalfSelect.LO)
        with self.assertRaises(HardwareTimingConflictError):
            self.regs.set_ha_bus_mux(HalfSelect.HI)

        # Advances cycle -> should succeed
        self.clock.tick(1)
        self.regs.set_ha_bus_mux(HalfSelect.HI)

    def test_hb_bus_timing_conflict(self):
        """Verify calling set_hb_mux twice in same clock cycle raises HardwareTimingConflictError."""
        self.regs.set_hb_mux(HalfSelect.LO, Reg.BX)
        with self.assertRaises(HardwareTimingConflictError):
            self.regs.set_hb_mux(HalfSelect.HI, Reg.BX)

        # Advances cycle -> should succeed
        self.clock.tick(1)
        self.regs.set_hb_mux(HalfSelect.HI, Reg.DX)

    def test_res_bus_writeback_and_timing_conflict(self):
        """Verify set_res_bus writes to destination and forbids multiple writes per cycle."""
        # Cycle 0: write AL
        self.regs.set_res_bus(Reg.AL, 0xAABBCCDD)
        self.assertEqual(Registers.to_int(self.regs.testharness_peek(Reg.AL)), 0xAABBCCDD)

        # Second write in cycle 0 raises HardwareTimingConflictError
        with self.assertRaises(HardwareTimingConflictError):
            self.regs.set_res_bus(Reg.AH, 0x11223344)

        # Advance cycle -> write AH
        self.clock.tick(1)
        self.regs.set_res_bus(Reg.AH, 0x11223344)
        self.assertEqual(Registers.to_int(self.regs.testharness_peek(Reg.AH)), 0x11223344)

    def test_status_flags(self):
        """Test status flag manipulation."""
        self.regs.clear_flags()
        self.assertEqual(self.regs.status, 0)

        self.regs.set_flag(StatusFlag.ZERO)
        self.assertTrue(self.regs.get_flag(StatusFlag.ZERO))
        self.assertFalse(self.regs.get_flag(StatusFlag.CARRY))

        self.regs.clr_flag(StatusFlag.ZERO)
        self.assertFalse(self.regs.get_flag(StatusFlag.ZERO))

    def test_conversion_utilities(self):
        """Test integer and float Little-Endian conversions."""
        val32 = 0x12345678
        raw32 = Registers.from_int(val32, 4)
        self.assertEqual(Registers.to_int(raw32), val32)

        f_val = 3.1415927
        raw_f32 = Registers.from_f32(f_val)
        self.assertAlmostEqual(Registers.to_f32(raw_f32), f_val, places=6)

        d_val = 2.718281828459045
        raw_f64 = Registers.from_f64(d_val)
        self.assertAlmostEqual(Registers.to_f64(raw_f64), d_val, places=12)

    def test_reset(self):
        """Test hardware reset clears all registers and timing tracking."""
        self.regs.load_test_vector(Reg.AL, 0xFFFFFFFF)
        self.regs.set_ha_bus_mux(HalfSelect.LO)
        self.regs.reset()

        self.assertEqual(Registers.to_int(self.regs.testharness_peek(Reg.AL)), 0)
        # HA bus MUX should be reset
        with self.assertRaises(HardwareBusError):
            self.regs.read_ha_bus()

        # Should be able to set HA bus again at cycle 0 because reset cleared last tick
        self.regs.set_ha_bus_mux(HalfSelect.LO)

    def test_dump(self):
        """Verify dump format."""
        dump_str = self.regs.dump()
        self.assertIn("=== Register File Dump ===", dump_str)
        self.assertIn("AX: 0x", dump_str)
        self.assertIn("STATUS:", dump_str)
