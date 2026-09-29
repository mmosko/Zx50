"""Flash ROM model for Zx50 FPU.

Loads and exposes lookup tables from the compiled 32KB Flash ROM image (fpu_flash.bin).
Direct member variable manipulation is discouraged; callers must use the public API.
"""

import os
from typing import Optional, Union

ROM_SIZE = 32768  # 32 KB active region for CA[14:0]

# ROM Base Addresses (matching src/fpu_rom_map.vh)
FLASH_QS_BASE     = 0x0000  # Quarter-Square Table (1022 bytes)
FLASH_RECIP_BASE  = 0x0400  # Reciprocal Table (512 bytes)
FLASH_SQRT_BASE   = 0x0600  # Reciprocal Square Root Seed Table (512 bytes)
FLASH_EXP2_BASE   = 0x0800  # Exp2 Table (512 bytes)
FLASH_LOG2_BASE   = 0x0A00  # Log2 Table (512 bytes)
FLASH_SIN_BASE    = 0x0C00  # Sine Table (512 bytes)
FLASH_COS_BASE    = 0x0E00  # Cosine Table (512 bytes)
FLASH_TAN_BASE    = 0x1000  # Tangent Table (512 bytes)
FLASH_LN_BASE     = 0x1200  # Natural Log Table (512 bytes)
FLASH_LOG10_BASE  = 0x1400  # Base-10 Log Table (512 bytes)
FLASH_CONST_BASE  = 0x1600  # Mathematical Constants Table (128 bytes)


def get_default_rom_path() -> str:
    """Returns the default path to the bundled fpu_flash.bin image."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "rom", "fpu_flash.bin")


class Rom:
    """32KB Flash ROM lookup table model."""

    def __init__(self, rom_path: Optional[str] = None):
        if rom_path is None:
            rom_path = get_default_rom_path()
        self._rom_path = rom_path
        if os.path.exists(rom_path):
            with open(rom_path, "rb") as f:
                self._data = bytearray(f.read())
            if len(self._data) != ROM_SIZE:
                raise ValueError(
                    f"Invalid ROM image size: {len(self._data)} bytes (expected {ROM_SIZE})"
                )
        else:
            # Fallback uninitialized ROM image pre-filled with 0xFF
            self._data = bytearray([0xFF] * ROM_SIZE)

    @property
    def size(self) -> int:
        """Returns the total ROM capacity in bytes."""
        return len(self._data)

    def load_byte(self, addr: int) -> int:
        """Loads a single byte from ROM."""
        if not (0 <= addr < ROM_SIZE):
            raise IndexError(f"ROM address 0x{addr:04X} out of range (0..0x{ROM_SIZE-1:04X})")
        return self._data[addr]

    def load_u16(self, addr: int) -> int:
        """Loads a 16-bit little-endian word from ROM."""
        if not (0 <= addr <= ROM_SIZE - 2):
            raise IndexError(f"ROM address 0x{addr:04X} out of range for 16-bit read")
        return self._data[addr] | (self._data[addr + 1] << 8)

    def load(self, addr: int, length: int = 2) -> bytearray:
        """Loads `length` bytes from ROM starting at `addr`."""
        if length <= 0:
            raise ValueError(f"length must be positive, got {length}")
        if not (0 <= addr and addr + length <= ROM_SIZE):
            raise IndexError(
                f"ROM access at 0x{addr:04X} with length {length} exceeds ROM bounds (size={ROM_SIZE})"
            )
        return bytearray(self._data[addr : addr + length])

    def load_sqrt_seed(self, index: int) -> int:
        """Loads 16-bit Q0.16 reciprocal square root seed for index 0..255."""
        if not (0 <= index < 256):
            raise IndexError(f"Sqrt seed index {index} out of range (0..255)")
        addr = FLASH_SQRT_BASE + (index * 2)
        return self.load_u16(addr)

    def load_ln_seed(self, index: int) -> int:
        """Loads 16-bit word from Natural Log table for index 0..255."""
        if not (0 <= index < 256):
            raise IndexError(f"LN seed index {index} out of range (0..255)")
        addr = FLASH_LN_BASE + (index * 2)
        return self.load_u16(addr)

    def load_exp2_seed(self, index: int) -> int:
        """Loads 16-bit word from Exp2 table for index 0..255."""
        if not (0 <= index < 256):
            raise IndexError(f"Exp2 seed index {index} out of range (0..255)")
        addr = FLASH_EXP2_BASE + (index * 2)
        return self.load_u16(addr)

    def load_const32(self, opcode: int) -> bytearray:
        """Loads 4-byte little-endian IEEE-754 single precision constant for opcode 0xA0..0xAF."""
        if not (0xA0 <= opcode <= 0xAF):
            raise IndexError(f"Constant opcode 0x{opcode:02X} out of range (0xA0..0xAF)")
        addr = FLASH_CONST_BASE + ((opcode - 0xA0) * 8)
        return self.load(addr, 4)

    def load_const64(self, opcode: int) -> bytearray:
        """Loads 8-byte little-endian IEEE-754 double precision constant for opcode 0xA0..0xAF."""
        if not (0xA0 <= opcode <= 0xAF):
            raise IndexError(f"Constant opcode 0x{opcode:02X} out of range (0xA0..0xAF)")
        addr = FLASH_CONST_BASE + ((opcode - 0xA0) * 8)
        return self.load(addr, 8)
