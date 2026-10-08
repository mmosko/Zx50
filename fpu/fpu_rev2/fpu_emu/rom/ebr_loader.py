"""EBR ROM buffer loader for Zx50 FPU.

Populates initial ROM buffers for EBR 2, EBR 3, and EBR 4 from the compiled
flash ROM binary image (fpu_flash.bin).
"""

from pathlib import Path
import struct
from typing import List, Optional

from fpu_emu.rom.fpu_const_map import FpuTables


def get_default_rom_path() -> Path:
    return Path(__file__).parent / "fpu_flash.bin"


def load_ebr_rom_buffers(rom_path: Optional[Path] = None) -> List[Optional[List[int]]]:
    """Generates the 8 EBR initialization buffers (512 words each) for Memory.

    EBR Allocation:
      - EBR 0 & 1: RAM (None)
      - EBR 2 & 3: Paired 32-bit ROM (EBR 2 = low 16 bits, EBR 3 = high 16 bits):
          * Words 0..127: Trig & CORDIC Angles
          * Words 128..255: Chebyshev Polynomial Coefficients
          * Words 256..319: IEEE-754 Math Constants
          * Words 320..511: Headroom
      - EBR 4: Single 16-bit ROM:
          * Words 0..255: Reciprocal / Division Seed LUT (256 x 16-bit)
          * Words 256..511: Square Root Seed LUT (256 x 16-bit)
      - EBR 5 & 6: Microcode Execution Store (managed separately or None)
      - EBR 7: Unallocated (None)
    """
    ebr2 = [0] * 512
    ebr3 = [0] * 512
    ebr4 = [0] * 512

    path = rom_path if (rom_path is not None and rom_path.exists()) else get_default_rom_path()
    if path.exists():
        with open(path, "rb") as f:
            data = f.read()

        # 1. EBR 4: Reciprocal Seeds (256 x 16-bit at FLASH_RECIP_BASE = 0x0400)
        recip_bytes = data[FpuTables.RECIP : FpuTables.RECIP + 512]
        if len(recip_bytes) == 512:
            recip_words = struct.unpack("<256H", recip_bytes)
            for i, w in enumerate(recip_words):
                ebr4[i] = w

        # 2. EBR 4: SQRT Seeds (256 x 16-bit at FLASH_SQRT_BASE = 0x0600)
        sqrt_bytes = data[FpuTables.SQRT : FpuTables.SQRT + 512]
        if len(sqrt_bytes) == 512:
            sqrt_words = struct.unpack("<256H", sqrt_bytes)
            for i, w in enumerate(sqrt_words):
                ebr4[256 + i] = w

        # 3. EBR 2 & 3: Mathematical Constants (64 x 32-bit at FLASH_CONST_BASE = 0x1600)
        # Stored at EBR 2/3 base 0x100 (words 256..319)
        const_bytes = data[FpuTables.CONST : FpuTables.CONST + 256]
        if len(const_bytes) == 256:
            const_words = struct.unpack("<64I", const_bytes)
            for i, val in enumerate(const_words):
                ebr2[256 + i] = val & 0xFFFF
                ebr3[256 + i] = (val >> 16) & 0xFFFF

        # 4. EBR 2 & 3: Chebyshev & Polynomial Coefficients (128 x 32-bit at FLASH_CHEB_BASE = 0x1C00)
        # Stored at EBR 2/3 base 0x080 (words 128..255)
        cheb_bytes = data[FpuTables.CHEB : FpuTables.CHEB + 512]
        if len(cheb_bytes) == 512:
            cheb_words = struct.unpack("<128I", cheb_bytes)
            for i, val in enumerate(cheb_words):
                ebr2[128 + i] = val & 0xFFFF
                ebr3[128 + i] = (val >> 16) & 0xFFFF
            if ebr2[128 + 11] == 0 and ebr3[128 + 11] == 0:
                ebr2[128 + 11] = 0x04F3
                ebr3[128 + 11] = 0x00B5

        # 5. EBR 2 & 3: CORDIC ATAN32 (32 x 32-bit at FLASH_CORDIC_ATAN32_BASE = 0x1800)
        # Stored at EBR 2/3 base 0x000 (words 0..31)
        cordic_bytes = data[FpuTables.CORDIC_ATAN32 : FpuTables.CORDIC_ATAN32 + 128]
        if len(cordic_bytes) == 128:
            cordic_words = struct.unpack("<32I", cordic_bytes)
            for i, val in enumerate(cordic_words):
                ebr2[i] = val & 0xFFFF
                ebr3[i] = (val >> 16) & 0xFFFF

    return [None, None, ebr2, ebr3, ebr4, None, None, None]
