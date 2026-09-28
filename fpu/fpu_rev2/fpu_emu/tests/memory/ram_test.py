"""Unit tests for Ram class."""

import unittest
from fpu_emu.memory.ram import (
    Ram,
    DEFAULT_RAM_SIZE,
    STACK_BASE,
    SCRATCHPAD_BASE,
    USER_MEM_BASE,
    USER_MEM_SIZE,
)


class TestRam(unittest.TestCase):
    """Test suite for SysMEM EBR Ram implementation."""

    def setUp(self):
        self.ram = Ram()

    def test_initial_state(self):
        """Test default RAM sizing and zero initialization."""
        self.assertEqual(len(self.ram), DEFAULT_RAM_SIZE)
        self.assertEqual(self.ram.size, DEFAULT_RAM_SIZE)
        self.assertEqual(self.ram.load(0, 16), bytearray(16))

        # Custom size
        custom = Ram(1024)
        self.assertEqual(len(custom), 1024)

        # Invalid size
        with self.assertRaises(ValueError):
            Ram(0)
        with self.assertRaises(ValueError):
            Ram(-100)

    def test_load_and_store(self):
        """Test basic load, store, copy isolation, and data types."""
        test_data = bytearray([0xDE, 0xAD, 0xBE, 0xEF])

        # Store and default load (4 bytes)
        self.ram.store(0x100, test_data)
        ret = self.ram.load(0x100)
        self.assertEqual(ret, test_data)

        # Verify copy isolation
        ret[0] = 0x00
        self.assertEqual(self.ram.load(0x100), test_data)

        # 8-byte store and load
        data64 = bytearray([1, 2, 3, 4, 5, 6, 7, 8])
        self.ram.store(0x20, data64)
        self.assertEqual(self.ram.load(0x20, length=8), data64)

        # Store single integer byte
        self.ram.store(0x50, 0x42)
        self.assertEqual(self.ram.load(0x50, length=1), bytearray([0x42]))

        # Invalid data type
        with self.assertRaises(TypeError):
            self.ram.store(0x50, "invalid")  # type: ignore

    def test_bounds_validation(self):
        """Test address bounds checking and exceptions."""
        with self.assertRaises(IndexError):
            self.ram.load(-1)
        with self.assertRaises(IndexError):
            self.ram.load(DEFAULT_RAM_SIZE)
        with self.assertRaises(IndexError):
            self.ram.load(DEFAULT_RAM_SIZE - 2, length=4)
        with self.assertRaises(ValueError):
            self.ram.load(0, length=-1)

        with self.assertRaises(IndexError):
            self.ram.store(-1, bytearray([1]))
        with self.assertRaises(IndexError):
            self.ram.store(DEFAULT_RAM_SIZE, bytearray([1]))
        with self.assertRaises(IndexError):
            self.ram.store(DEFAULT_RAM_SIZE - 2, bytearray([1, 2, 3, 4]))

    def test_scratchpad_access(self):
        """Test scratchpad word addressing at 0x0200."""
        # Word 0 -> 0x0200
        w0_data = bytearray([0x11, 0x22, 0x33, 0x44])
        self.ram.store_scratch(0, w0_data)
        self.assertEqual(self.ram.load_scratch(0), w0_data)
        self.assertEqual(self.ram.load(SCRATCHPAD_BASE, 4), w0_data)

        # Word 63 -> 0x02FC
        w63_data = bytearray([0xAA, 0xBB, 0xCC, 0xDD])
        self.ram.store_scratch(63, w63_data)
        self.assertEqual(self.ram.load_scratch(63), w63_data)
        self.assertEqual(self.ram.load(SCRATCHPAD_BASE + 252, 4), w63_data)

        # 8-byte access at word 0
        w8_data = bytearray([1, 2, 3, 4, 5, 6, 7, 8])
        self.ram.store_scratch(0, w8_data)
        self.assertEqual(self.ram.load_scratch(0, length=8), w8_data)

        # Out of bounds word indices
        with self.assertRaises(IndexError):
            self.ram.load_scratch(-1)
        with self.assertRaises(IndexError):
            self.ram.load_scratch(64)

        # 8-byte write at word 63 exceeds scratchpad
        with self.assertRaises(IndexError):
            self.ram.store_scratch(63, w8_data)

    def test_user_memory_access(self):
        """Test user memory slot addressing at 0x0300 and zero_user_mem."""
        # Slot 0 -> 0x0300
        slot0_data = bytearray([0x55, 0x66, 0x77, 0x88])
        self.ram.store_user_mem(0, slot0_data)
        self.assertEqual(self.ram.load_user_mem(0), slot0_data)
        self.assertEqual(self.ram.load(USER_MEM_BASE, 4), slot0_data)

        # Slot 15 -> 0x033C
        slot15_data = bytearray([0x99, 0xAA, 0xBB, 0xCC])
        self.ram.store_user_mem(15, slot15_data)
        self.assertEqual(self.ram.load_user_mem(15), slot15_data)
        self.assertEqual(self.ram.load(USER_MEM_BASE + 60, 4), slot15_data)

        # Out of bounds slots
        with self.assertRaises(IndexError):
            self.ram.load_user_mem(-1)
        with self.assertRaises(IndexError):
            self.ram.load_user_mem(16)

        # 8-byte write at slot 15 exceeds user memory
        with self.assertRaises(IndexError):
            self.ram.store_user_mem(15, bytearray([1, 2, 3, 4, 5, 6, 7, 8]))

        # Test zero_user_mem isolates user area
        self.ram.store(STACK_BASE, bytearray([0xFF, 0xFF, 0xFF, 0xFF]))
        self.ram.store(SCRATCHPAD_BASE, bytearray([0xEE, 0xEE, 0xEE, 0xEE]))

        self.ram.zero_user_mem()
        self.assertEqual(self.ram.load_user_mem(0), bytearray(4))
        self.assertEqual(self.ram.load_user_mem(15), bytearray(4))
        self.assertEqual(self.ram.load(USER_MEM_BASE, USER_MEM_SIZE), bytearray(USER_MEM_SIZE))

        # Verify stack and scratchpad untouched
        self.assertEqual(self.ram.load(STACK_BASE, 4), bytearray([0xFF, 0xFF, 0xFF, 0xFF]))
        self.assertEqual(self.ram.load(SCRATCHPAD_BASE, 4), bytearray([0xEE, 0xEE, 0xEE, 0xEE]))

    def test_indexing_and_slicing(self):
        """Test bracket indexing and slicing operations."""
        self.ram[0x10] = 0x7E
        self.assertEqual(self.ram[0x10], 0x7E)

        self.ram[0x20:0x24] = b"\x01\x02\x03\x04"
        self.assertEqual(self.ram[0x20:0x24], bytearray([1, 2, 3, 4]))

        with self.assertRaises(IndexError):
            _ = self.ram[DEFAULT_RAM_SIZE]

    def test_clear(self):
        """Test full clear zeroes entire RAM."""
        self.ram.store(0, bytearray([1, 2, 3, 4]))
        self.ram.store(DEFAULT_RAM_SIZE - 4, bytearray([5, 6, 7, 8]))
        self.ram.clear()
        self.assertEqual(self.ram.load(0, 4), bytearray(4))
        self.assertEqual(self.ram.load(DEFAULT_RAM_SIZE - 4, 4), bytearray(4))


if __name__ == "__main__":
    unittest.main()
