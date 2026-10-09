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
    """Generates the EBR initialization buffers for Memory.

    EBR Allocation:
      - EBR 0: DATA_RAM (1024 words x 32-bit):
          * Words 0..255 (0x000..0x0FF): RAM Space (Stack, Scratchpad, USR, Headroom)
          * Words 256..319 (0x100..0x13F): IEEE-754 Math Constants (64 x 32-bit)
          * Words 320..511 (0x140..0x1FF): Headroom
          * Words 512..639 (0x200..0x27F): Trig & CORDIC Angles (128 x 32-bit)
          * Words 640..767 (0x280..0x2FF): Chebyshev Polynomial Coefficients (128 x 32-bit)
          * Words 768..1023 (0x300..0x3FF): Combined Seeds (RECIP low 16b, SQRT high 16b)
      - EBR 1..3: NullEbr (unallocated)
      - EBR 4: CODE_ROM (1024 words x 32-bit microcode execution store)
      - EBR 5..7: NullEbr (unallocated)
    """
    data_ram = [0] * 1024
    code_rom = [0] * 1024

    path = rom_path if (rom_path is not None and rom_path.exists()) else get_default_rom_path()
    if path.exists():
        with open(path, "rb") as f:
            data = f.read()

        # 1. Mathematical Constants (64 x 32-bit at FLASH_CONST_BASE = 0x1600)
        # Stored at DATA_RAM base 0x100 (words 256..319)
        const_bytes = data[FpuTables.CONST : FpuTables.CONST + 256]
        if len(const_bytes) == 256:
            const_words = struct.unpack("<64I", const_bytes)
            for i, val in enumerate(const_words):
                data_ram[256 + i] = val

        # 2. CORDIC ATAN32 (32 x 32-bit at FLASH_CORDIC_ATAN32_BASE = 0x1800)
        # Stored at DATA_RAM base 0x200 (words 512..543)
        cordic_bytes = data[FpuTables.CORDIC_ATAN32 : FpuTables.CORDIC_ATAN32 + 128]
        if len(cordic_bytes) == 128:
            cordic_words = struct.unpack("<32I", cordic_bytes)
            for i, val in enumerate(cordic_words):
                data_ram[512 + i] = val

        # 3. Chebyshev & Polynomial Coefficients (128 x 32-bit at FLASH_CHEB_BASE = 0x1C00)
        # Stored at DATA_RAM base 0x280 (words 640..767)
        cheb_bytes = data[FpuTables.CHEB : FpuTables.CHEB + 512]
        if len(cheb_bytes) == 512:
            cheb_words = struct.unpack("<128I", cheb_bytes)
            for i, val in enumerate(cheb_words):
                data_ram[640 + i] = val
            if data_ram[640 + 11] == 0:
                data_ram[640 + 11] = 0x00B504F3

        # 4. Combined Seeds at DATA_RAM base 0x300 (words 768..1023):
        # RECIP low 16-bit slice, SQRT high 16-bit slice
        recip_bytes = data[FpuTables.RECIP : FpuTables.RECIP + 512]
        sqrt_bytes = data[FpuTables.SQRT : FpuTables.SQRT + 512]
        recip_words = struct.unpack("<256H", recip_bytes) if len(recip_bytes) == 512 else [0] * 256
        sqrt_words = struct.unpack("<256H", sqrt_bytes) if len(sqrt_bytes) == 512 else [0] * 256
        for i in range(256):
            data_ram[768 + i] = ((sqrt_words[i] & 0xFFFF) << 16) | (recip_words[i] & 0xFFFF)

    return [data_ram, code_rom, None, None, None, None, None, None]
