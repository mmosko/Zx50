"""Unit tests for Clock and Hardware classes."""

import unittest
from fpu_emu.clock import Clock
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag


class TestClock(unittest.TestCase):
    """Test suite for master Clock."""

    def test_clock_initial_and_tick(self):
        clk = Clock(freq_hz=80_000_000.0)
        self.assertEqual(clk.cycles, 0)
        self.assertEqual(clk.freq_hz, 80_000_000.0)
        self.assertEqual(clk.elapsed_seconds, 0.0)

        clk.tick(10)
        self.assertEqual(clk.cycles, 10)
        self.assertAlmostEqual(clk.elapsed_us, 10 / 80.0)

        clk.tick(1)
        self.assertEqual(clk.cycles, 11)

        clk.reset()
        self.assertEqual(clk.cycles, 0)

    def test_clock_invalid_values(self):
        with self.assertRaises(ValueError):
            Clock(freq_hz=0)
        with self.assertRaises(ValueError):
            Clock(freq_hz=-10)

        clk = Clock()
        with self.assertRaises(ValueError):
            clk.tick(-1)


from fpu_emu.tests.testharness import RegTestHarness


class TestHardware(unittest.TestCase):
    """Test suite for Hardware container."""

    def test_hardware_defaults(self):
        hw = Hardware()
        self.assertIsNotNone(hw.clock)
        self.assertIsNotNone(hw.reg)
        self.assertIsNotNone(hw.mem)

        self.assertEqual(hw.clock.cycles, 0)
        self.assertEqual(hw.reg.status, 0)
        self.assertEqual(len(hw.mem), 9216)

    def test_hardware_reset(self):
        hw = Hardware()
        reg = RegTestHarness(hw.reg)
        hw.clock.tick(50)
        reg.set(Reg.AL, bytearray([1, 2, 3, 4]))
        hw.mem.store(0x100, bytearray([0xAA, 0xBB]))

        # Reset without clear_mem
        hw.reset(clear_mem=False)
        self.assertEqual(hw.clock.cycles, 0)
        self.assertEqual(hw.reg.status, 0x40)  # ZERO flag asserted per reset spec
        self.assertEqual(reg.peek(Reg.AL), bytearray(4))
        self.assertEqual(hw.mem.load(0x100, 2), bytearray([0xAA, 0xBB]))

        # Reset with clear_mem
        hw.reset(clear_mem=True)
        self.assertEqual(hw.mem.load(0x100, 2), bytearray([0x00, 0x00]))


if __name__ == "__main__":
    unittest.main()
