"""Flash ROM model for Zx50 FPU.

Loads and exposes lookup tables from the compiled 32KB Flash ROM image (fpu_flash.bin).
Direct member variable manipulation is discouraged; callers must use the public API.
"""

from enum import IntEnum
import os
from typing import Optional
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.rom.fpu_const_map import FpuConst

ROM_SIZE = 32768  # 32 KB active region for CA[14:0]

# ROM Base Addresses (matching src/fpu_rom_map.vh)
FLASH_QS_BASE = 0x0000  # Quarter-Square Table (1022 bytes)
FLASH_RECIP_BASE = 0x0400  # Reciprocal Table (512 bytes)
FLASH_SQRT_BASE = 0x0600  # Reciprocal Square Root Seed Table (512 bytes)
FLASH_EXP2_BASE = 0x0800  # Exp2 Table (512 bytes)
FLASH_LOG2_BASE = 0x0A00  # Log2 Table (512 bytes)
FLASH_SIN_BASE = 0x0C00  # Sine Table (512 bytes)
FLASH_COS_BASE = 0x0E00  # Cosine Table (512 bytes)
FLASH_TAN_BASE = 0x1000  # Tangent Table (512 bytes)
FLASH_LN_BASE = 0x1200  # Natural Log Table (512 bytes)
FLASH_LOG10_BASE = 0x1400  # Base-10 Log Table (512 bytes)
FLASH_CONST_BASE = 0x1600  # Mathematical Constants Table (128 bytes)
FLASH_CORDIC_ATAN32_BASE = 0x1800  # CORDIC Arctangent 32-bit Table (128 bytes: 32 x 4 bytes)
FLASH_CORDIC_ATAN64_BASE = 0x1900  # CORDIC Arctangent 64-bit Table (512 bytes: 64 x 8 bytes)
FLASH_TRIG_CONST_BASE = 0x1B00  # Trigonometric & CORDIC Constants (128 bytes: 16 x 8 bytes)


class TrigConstSlot(IntEnum):
    """Slot indices for Table 14: FLASH_TRIG_CONST_BASE (16 slots * 8 bytes)."""

    INV_K_32 = 0
    INV_K_64 = 1
    HALF_PI_32 = 2
    HALF_PI_64 = 3
    TWO_OVER_PI_32 = 4
    TWO_OVER_PI_64 = 5
    QUARTER_PI_32 = 6
    QUARTER_PI_64 = 7
    TWO_OVER_PI_F32 = 8
    TWO_OVER_PI_F64 = 9
    HALF_PI_F32 = 10
    HALF_PI_F64 = 11
    PI_F32 = 12
    PI_F64 = 13
    INV_K_F32 = 14
    INV_K_F64 = 15


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
                raise ValueError(f"Invalid ROM image size: {len(self._data)} bytes (expected {ROM_SIZE})")
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
            raise IndexError(f"ROM address 0x{addr:04X} out of range (0..0x{ROM_SIZE - 1:04X})")
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
            raise IndexError(f"ROM access at 0x{addr:04X} with length {length} exceeds ROM bounds (size={ROM_SIZE})")
        return bytearray(self._data[addr : addr + length])

    @fpga_resource(
        approach="Single SysMEM EBR (EBR 4, 512x16) for reciprocal and square root seed tables",
        luts=0,
        ffs=0,
        ebr=1,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_seed_rom",
    )
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

    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 2 & 3, 512x32) for trig/cordic angles and IEEE-754 constants",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_constants_rom",
    )
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

    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 2 & 3, 512x32) for trig/cordic angles and IEEE-754 constants",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_constants_rom",
    )
    def load_const_word(self, slot: int | FpuConst) -> int:
        """Loads 32-bit constant word from slot offset in FLASH_CONST_BASE (1 cycle)."""
        slot_int = int(slot)
        if not (0 <= slot_int < 64):
            raise IndexError(f"Constant slot {slot_int} out of range (0..63)")
        addr = FLASH_CONST_BASE + (slot_int << 2)
        return int.from_bytes(self.load(addr, 4), byteorder="little")

    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 2 & 3, 512x32) for trig/cordic angles and IEEE-754 constants",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=2,
        shared_unit="ebr_constants_rom",
    )
    def load_const_dword(self, slot: int | FpuConst) -> int:
        """Loads 64-bit constant dword from slot offset in FLASH_CONST_BASE (2 cycles)."""
        slot_int = int(slot)
        if not (0 <= slot_int < 63):
            raise IndexError(f"Constant slot {slot_int} out of range for 64-bit read (0..62)")
        addr = FLASH_CONST_BASE + (slot_int << 2)
        return int.from_bytes(self.load(addr, 8), byteorder="little")

    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 2 & 3, 512x32) for trig/cordic angles and IEEE-754 constants",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_constants_rom",
    )
    def load_cordic_atan32(self, index: int) -> int:
        """Loads 32-bit Q2.30 CORDIC arctangent angle for iteration index 0..31."""
        if not (0 <= index < 32):
            raise IndexError(f"CORDIC atan32 index {index} out of range (0..31)")
        addr = FLASH_CORDIC_ATAN32_BASE + (index * 4)
        return int.from_bytes(self.load(addr, 4), byteorder="little")

    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 2 & 3, 512x32) for trig/cordic angles and IEEE-754 constants",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=2,
        shared_unit="ebr_constants_rom",
    )
    def load_cordic_atan64(self, index: int) -> int:
        """Loads 64-bit Q2.62 CORDIC arctangent angle for iteration index 0..63."""
        if not (0 <= index < 64):
            raise IndexError(f"CORDIC atan64 index {index} out of range (0..63)")
        addr = FLASH_CORDIC_ATAN64_BASE + (index * 8)
        return int.from_bytes(self.load(addr, 8), byteorder="little")

    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 2 & 3, 512x32) for trig/cordic angles and IEEE-754 constants",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_constants_rom",
    )
    def load_trig_const32(self, slot: int | TrigConstSlot) -> int:
        """Loads 32-bit trig/cordic constant from slot 0..15."""
        slot_int = int(slot)
        if not (0 <= slot_int < 16):
            raise IndexError(f"Trig constant slot {slot_int} out of range (0..15)")
        addr = FLASH_TRIG_CONST_BASE + (slot_int * 8)
        return int.from_bytes(self.load(addr, 4), byteorder="little")

    @fpga_resource(
        approach="Paired Single-Port SysMEM EBR (EBR 2 & 3, 512x32) for trig/cordic angles and IEEE-754 constants",
        luts=0,
        ffs=0,
        ebr=2,
        delay_ns=3.2,
        cycles=2,
        shared_unit="ebr_constants_rom",
    )
    def load_trig_const64(self, slot: int | TrigConstSlot) -> int:
        """Loads 64-bit trig/cordic constant from slot 0..15."""
        slot_int = int(slot)
        if not (0 <= slot_int < 16):
            raise IndexError(f"Trig constant slot {slot_int} out of range (0..15)")
        addr = FLASH_TRIG_CONST_BASE + (slot_int * 8)
        return int.from_bytes(self.load(addr, 8), byteorder="little")
