"""Flash ROM model for Zx50 FPU.

Models off-chip ROM
"""

from pathlib import Path


class Rom:
    """32KB Flash ROM lookup table model."""

    def __init__(self, size: int, rom_path: Path):
        self._rom_path = rom_path
        if rom_path.exists():
            with open(rom_path, "rb") as f:
                self._data = bytearray(f.read())
            if len(self._data) != size:
                raise ValueError(f"Invalid ROM image size: {len(self._data)} bytes (expected {size})")
        else:
            # Fallback uninitialized ROM image pre-filled with 0xFF
            self._data = bytearray([0xFF] * size)

    @property
    def size(self) -> int:
        """Returns the total ROM capacity in bytes."""
        return len(self._data)

    def load_byte(self, addr: int) -> int:
        """Loads a single byte from ROM."""
        if not (0 <= addr < len(self._data)):
            raise IndexError(f"ROM address 0x{addr:04X} out of range (0..0x{len(self._data) - 1:04X})")
        return self._data[addr]

    def load(self, addr: int, length: int = 2) -> bytearray:
        """Loads `length` bytes from ROM starting at `addr`."""
        if length <= 0:
            raise ValueError(f"length must be positive, got {length}")
        if not (0 <= addr and addr + length <= len(self._data)):
            raise IndexError(f"ROM access at 0x{addr:04X} with length {length} exceeds ROM bounds (size={len(self._data)})")
        return bytearray(self._data[addr : addr + length])
