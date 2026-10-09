"""EBR ROM buffer loader for Zx50 FPU.

Loads initial ROM buffers for EBR 0 (DATA_RAM) and EBR 4 (CODE_ROM) from the
compiled 8KB flash ROM binary image (fpu_flash.bin).
"""

from pathlib import Path
import struct
from typing import List, Optional


def get_default_rom_path() -> Path:
    return Path(__file__).parent / "fpu_flash.bin"


def load_ebr_rom_buffers(rom_path: Optional[Path] = None) -> List[Optional[List[int]]]:
    """Generates the EBR initialization buffers for Memory.

    The 8KB flash ROM image is split directly in half:
      - EBR 0: DATA_RAM (1024 words x 32-bit, first 4096 bytes)
      - EBR 1..3: NullEbr (unallocated)
      - EBR 4: CODE_ROM (1024 words x 32-bit, second 4096 bytes)
      - EBR 5..7: NullEbr (unallocated)
    """
    data_ram = [0] * 1024
    code_rom = [0] * 1024

    path = rom_path if (rom_path is not None and rom_path.exists()) else get_default_rom_path()
    if path.exists():
        with open(path, "rb") as f:
            data = f.read()

        if len(data) >= 8192:
            data_ram = list(struct.unpack(">1024I", data[:4096]))
            code_rom = list(struct.unpack(">1024I", data[4096:8192]))

    return [data_ram, code_rom, None, None, None, None, None, None]
