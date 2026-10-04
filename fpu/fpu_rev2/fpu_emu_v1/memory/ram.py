"""SysMEM EBR RAM model for Zx50 FPU.

Models dual-port SysMEM EBR memory blocks with defined address partitions:
- 0x0000 - 0x00FF: Hardware Operand Stack (256 bytes)
- 0x0200 - 0x02FF: Internal Scratchpad RAM (256 bytes / 64 words)
- 0x0300 - 0x033F: User Storage Slots (64 bytes / 16 words)
- 0x0340 - 0x035F: Command Stack / Batch Queue (32 bytes)
- 0x0400 - 0x07FF: Microcode ROM & Constant Tables (1024 bytes)

Direct member variable manipulation is discouraged; callers must use the public API.
"""

from typing import Union
from fpu_emu.fpga_resource import fpga_resource

# Default size for Lattice MachXO2-2000HC (9 EBR blocks * 1024 bytes = 9216 bytes)
DEFAULT_RAM_SIZE = 9216

# Address Partition Constants
STACK_BASE = 0x0000
STACK_SIZE = 256  # 0x0000 - 0x00FF (64 words * 4 bytes)

SCRATCHPAD_BASE = 0x0200
SCRATCHPAD_SIZE = 256  # 0x0200 - 0x02FF (64 words * 4 bytes)
SCRATCHPAD_WORDS = 64

USER_MEM_BASE = 0x0300
USER_MEM_SIZE = 64  # 0x0300 - 0x033F (16 words * 4 bytes)
USER_MEM_SLOTS = 16

CMD_STACK_BASE = 0x0340
CMD_STACK_SIZE = 32  # 0x0340 - 0x035F (32 opcodes)

ROM_BASE = 0x0400
ROM_SIZE = 1024  # 0x0400 - 0x07FF


class Ram:
    """SysMEM EBR RAM implementation."""

    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 0 & 1, 512x32: Stack, Scratchpad, User Storage)",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_sysmem",
    )
    def __init__(self, size: int = DEFAULT_RAM_SIZE):
        if size <= 0:
            raise ValueError(f"RAM size must be positive, got {size}")
        self._size = size
        self._ram = bytearray(size)

    @property
    def size(self) -> int:
        """Returns the total RAM capacity in bytes."""
        return self._size

    # -------------------------------------------------------------------------
    # Core Load & Store API
    # -------------------------------------------------------------------------
    def load(self, addr: int, length: int = 4) -> bytearray:
        """Loads `length` bytes starting at `addr`."""
        self._validate_bounds(addr, length)
        return bytearray(self._ram[addr : addr + length])

    def store(self, addr: int, data: Union[bytes, bytearray, int]):
        """Stores `data` starting at `addr`.

        `data` may be bytes, a bytearray, or a single integer byte (0..255).
        """
        if isinstance(data, int):
            self._validate_bounds(addr, 1)
            self._ram[addr] = data & 0xFF
        elif isinstance(data, (bytes, bytearray)):
            self._validate_bounds(addr, len(data))
            self._ram[addr : addr + len(data)] = data
        else:
            raise TypeError(f"data must be bytes, bytearray, or int, got {type(data).__name__}")

    # -------------------------------------------------------------------------
    # Scratchpad Helpers (0x0200 - 0x02FF)
    # -------------------------------------------------------------------------
    def load_scratch(self, word_idx: int, length: int = 4) -> bytearray:
        """Loads from scratchpad at word index `0..63` (each word is 4 bytes)."""
        if not (0 <= word_idx < SCRATCHPAD_WORDS):
            raise IndexError(f"Scratchpad word index {word_idx} out of range (0..{SCRATCHPAD_WORDS - 1})")
        addr = SCRATCHPAD_BASE + (word_idx * 4)
        if addr + length > SCRATCHPAD_BASE + SCRATCHPAD_SIZE:
            raise IndexError(f"Scratchpad access at word {word_idx} with length {length} exceeds scratchpad partition")
        return self.load(addr, length)

    def store_scratch(self, word_idx: int, data: Union[bytes, bytearray]):
        """Stores `data` to scratchpad at word index `0..63`."""
        if not (0 <= word_idx < SCRATCHPAD_WORDS):
            raise IndexError(f"Scratchpad word index {word_idx} out of range (0..{SCRATCHPAD_WORDS - 1})")
        addr = SCRATCHPAD_BASE + (word_idx * 4)
        if addr + len(data) > SCRATCHPAD_BASE + SCRATCHPAD_SIZE:
            raise IndexError(f"Scratchpad write at word {word_idx} of {len(data)} bytes exceeds scratchpad partition")
        self.store(addr, data)

    # -------------------------------------------------------------------------
    # User Storage Helpers (0x0300 - 0x033F)
    # -------------------------------------------------------------------------
    def load_user_mem(self, slot_idx: int, length: int = 4) -> bytearray:
        """Loads from user memory at slot index `0..15` (each slot is 4 bytes)."""
        if not (0 <= slot_idx < USER_MEM_SLOTS):
            raise IndexError(f"User memory slot index {slot_idx} out of range (0..{USER_MEM_SLOTS - 1})")
        addr = USER_MEM_BASE + (slot_idx * 4)
        if addr + length > USER_MEM_BASE + USER_MEM_SIZE:
            raise IndexError(f"User memory access at slot {slot_idx} with length {length} exceeds user partition")
        return self.load(addr, length)

    def store_user_mem(self, slot_idx: int, data: Union[bytes, bytearray]):
        """Stores `data` to user memory at slot index `0..15`."""
        if not (0 <= slot_idx < USER_MEM_SLOTS):
            raise IndexError(f"User memory slot index {slot_idx} out of range (0..{USER_MEM_SLOTS - 1})")
        addr = USER_MEM_BASE + (slot_idx * 4)
        if addr + len(data) > USER_MEM_BASE + USER_MEM_SIZE:
            raise IndexError(f"User memory write at slot {slot_idx} of {len(data)} bytes exceeds user partition")
        self.store(addr, data)

    def zero_user_mem(self):
        """Zeroes all 64 bytes of user storage (Opcode ZERO_MEM 0xF0)."""
        self._ram[USER_MEM_BASE : USER_MEM_BASE + USER_MEM_SIZE] = b"\x00" * USER_MEM_SIZE

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    def clear(self):
        """Clears all RAM bytes to zero."""
        self._ram[:] = b"\x00" * self._size

    def _validate_bounds(self, addr: int, length: int):
        """Validates that [addr : addr + length] falls within RAM capacity."""
        if length < 0:
            raise ValueError(f"Length cannot be negative, got {length}")
        if addr < 0 or addr >= self._size:
            raise IndexError(f"Address 0x{addr:04X} out of bounds for RAM of size 0x{self._size:04X}")
        if addr + length > self._size:
            raise IndexError(f"Access range [0x{addr:04X} : 0x{addr + length:04X}] exceeds RAM size 0x{self._size:04X}")

    # -------------------------------------------------------------------------
    # Python Indexing & Slicing
    # -------------------------------------------------------------------------
    def __getitem__(self, item: Union[int, slice]) -> Union[int, bytearray]:
        if isinstance(item, int):
            self._validate_bounds(item, 1)
            return self._ram[item]
        elif isinstance(item, slice):
            start = item.start if item.start is not None else 0
            stop = item.stop if item.stop is not None else self._size
            if start < 0 or stop > self._size or start > stop:
                raise IndexError(f"Slice [{start}:{stop}] out of bounds for RAM size {self._size}")
            return bytearray(self._ram[item])
        raise TypeError(f"Invalid index type: {type(item).__name__}")

    def __setitem__(self, item: Union[int, slice], val: Union[int, bytes, bytearray]):
        if isinstance(item, int):
            if not isinstance(val, int):
                raise TypeError(f"Expected int value for single byte write, got {type(val).__name__}")
            self._validate_bounds(item, 1)
            self._ram[item] = val & 0xFF
        elif isinstance(item, slice):
            if not isinstance(val, (bytes, bytearray)):
                raise TypeError(f"Expected bytes or bytearray for slice write, got {type(val).__name__}")
            start = item.start if item.start is not None else 0
            stop = item.stop if item.stop is not None else self._size
            if start < 0 or stop > self._size or start > stop:
                raise IndexError(f"Slice [{start}:{stop}] out of bounds for RAM size {self._size}")
            self._ram[item] = val
        else:
            raise TypeError(f"Invalid index type: {type(item).__name__}")

    def __len__(self) -> int:
        return self._size
