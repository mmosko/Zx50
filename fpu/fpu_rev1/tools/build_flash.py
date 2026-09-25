#!/usr/bin/env python3
"""
tools/build_flash.py
ZX50 FPU Flash ROM LUT Generator & Serializer

Defines individual generator functions for each lookup table:
  1. Quarter-Square  (FLASH_QS_BASE     = 0x0000)
  2. Reciprocal      (FLASH_RECIP_BASE  = 0x0400)
  3. Sqrt Seed       (FLASH_SQRT_BASE   = 0x0600)
  4. Exp2            (FLASH_EXP2_BASE   = 0x0800)
  5. Log2            (FLASH_LOG2_BASE   = 0x0A00)
  6. Sine            (FLASH_SIN_BASE    = 0x0C00)
  7. Cosine          (FLASH_COS_BASE    = 0x0E00)
  8. Tangent         (FLASH_TAN_BASE    = 0x1000)
  9. Natural Log     (FLASH_LN_BASE     = 0x1200)
 10. Base-10 Log     (FLASH_LOG10_BASE  = 0x1400)

Serializes all tables into:
  - bin/fpu_flash.bin  : Raw 32KB binary image for physical EEPROM/Flash burners
  - sim/fpu_rom.hex    : Verilog $readmemh image for simulation
  - src/fpu_rom_map.vh : Verilog header containing memory base addresses
"""

import math
import os

# ROM Parameters & Base Addresses
FLASH_SIZE        = 32768   # 32 KB active region for CA[14:0]
FLASH_QS_BASE     = 0x0000  # Quarter-Square Table (1022 bytes)
FLASH_RECIP_BASE  = 0x0400  # Reciprocal Table (512 bytes)
FLASH_SQRT_BASE   = 0x0600  # Square Root Seed Table (512 bytes)
FLASH_EXP2_BASE   = 0x0800  # Exp2 Table (512 bytes)
FLASH_LOG2_BASE   = 0x0A00  # Log2 Table (512 bytes)
FLASH_SIN_BASE    = 0x0C00  # Sine Table (512 bytes)
FLASH_COS_BASE    = 0x0E00  # Cosine Table (512 bytes)
FLASH_TAN_BASE    = 0x1000  # Tangent Table (512 bytes)
FLASH_LN_BASE     = 0x1200  # Natural Log Table (512 bytes)
FLASH_LOG10_BASE  = 0x1400  # Base-10 Log Table (512 bytes)

HEADER_FILE = "src/fpu_rom_map.vh"
HEX_FILE    = "sim/fpu_rom.hex"
BIN_FILE    = "bin/fpu_flash.bin"


# =============================================================================
# Individual Lookup Table Generators
# =============================================================================
def generate_qs_table() -> bytearray:
    """Table 1: Quarter-Square [ f(n) = floor(n^2 / 4) ] for n in [0..510]"""
    data = bytearray(511 * 2)
    for n in range(511):
        val = (n * n) // 4
        data[n * 2]     = val & 0xFF
        data[n * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_recip_table() -> bytearray:
    """Table 2: Reciprocal [ f(x) = ceil(65536 / x) ] for x in [1..255]"""
    data = bytearray(256 * 2)
    for x in range(1, 256):
        val = min(65535, math.ceil(65536.0 / x))
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_sqrt_table() -> bytearray:
    """Table 3: Square Root Seeds [ f(x) = sqrt(x) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(math.sqrt(x) * 256) & 0xFFFF
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_exp2_table() -> bytearray:
    """Table 4: Exp2 [ f(x) = 2^(x/256) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(2 ** (x / 256.0) * 256) & 0xFFFF
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_log2_table() -> bytearray:
    """Table 5: Log2 [ f(x) = log2(1 + x/256) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(math.log2(1.0 + (x / 256.0)) * 256) & 0xFFFF
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_sin_table() -> bytearray:
    """Table 6: Sine [ f(x) = sin(x/256 * pi/2) * 256 ] for x in [0..255] (0 to 90 degrees)"""
    data = bytearray(256 * 2)
    for x in range(256):
        rad = (x / 256.0) * (math.pi / 2.0)
        val = min(65535, int(round(math.sin(rad) * 256.0)))
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_cos_table() -> bytearray:
    """Table 7: Cosine [ f(x) = cos(x/256 * pi/2) * 256 ] for x in [0..255] (0 to 90 degrees)"""
    data = bytearray(256 * 2)
    for x in range(256):
        rad = (x / 256.0) * (math.pi / 2.0)
        val = min(65535, int(round(math.cos(rad) * 256.0)))
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_tan_table() -> bytearray:
    """Table 8: Tangent [ f(x) = tan(x/256 * pi/4) * 256 ] for x in [0..255] (0 to 45 degrees)"""
    data = bytearray(256 * 2)
    for x in range(256):
        rad = (x / 256.0) * (math.pi / 4.0)
        val = min(65535, int(round(math.tan(rad) * 256.0)))
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_ln_table() -> bytearray:
    """Table 9: Natural Log [ f(x) = ln(1 + x/256) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(round(math.log(1.0 + (x / 256.0)) * 256.0)) & 0xFFFF
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_log10_table() -> bytearray:
    """Table 10: Base-10 Log [ f(x) = log10(1 + x/256) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(round(math.log10(1.0 + (x / 256.0)) * 256.0)) & 0xFFFF
        data[x * 2]     = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


# =============================================================================
# In-Memory Flash Population Helper (Used by fpu_sim.py)
# =============================================================================
def populate_flash_memory(flash_mem: bytearray) -> bytearray:
    """Populate an existing 32KB bytearray with all Flash LUTs at their base addresses."""
    qs    = generate_qs_table()
    recip = generate_recip_table()
    sqrt  = generate_sqrt_table()
    exp2  = generate_exp2_table()
    log2  = generate_log2_table()
    sin   = generate_sin_table()
    cos   = generate_cos_table()
    tan   = generate_tan_table()
    ln    = generate_ln_table()
    log10 = generate_log10_table()

    flash_mem[FLASH_QS_BASE    : FLASH_QS_BASE + len(qs)]       = qs
    flash_mem[FLASH_RECIP_BASE : FLASH_RECIP_BASE + len(recip)] = recip
    flash_mem[FLASH_SQRT_BASE  : FLASH_SQRT_BASE + len(sqrt)]   = sqrt
    flash_mem[FLASH_EXP2_BASE  : FLASH_EXP2_BASE + len(exp2)]   = exp2
    flash_mem[FLASH_LOG2_BASE  : FLASH_LOG2_BASE + len(log2)]   = log2
    flash_mem[FLASH_SIN_BASE   : FLASH_SIN_BASE + len(sin)]     = sin
    flash_mem[FLASH_COS_BASE   : FLASH_COS_BASE + len(cos)]     = cos
    flash_mem[FLASH_TAN_BASE   : FLASH_TAN_BASE + len(tan)]     = tan
    flash_mem[FLASH_LN_BASE    : FLASH_LN_BASE + len(ln)]       = ln
    flash_mem[FLASH_LOG10_BASE : FLASH_LOG10_BASE + len(log10)] = log10

    return flash_mem


def generate_flash_image() -> bytearray:
    """Generate a 32KB Flash ROM binary image pre-filled with 0xFF."""
    image = bytearray([0xFF] * FLASH_SIZE)
    return populate_flash_memory(image)


# =============================================================================
# Verilog Header & Hex Serialization
# =============================================================================
def write_verilog_header(header_path: str):
    os.makedirs(os.path.dirname(header_path), exist_ok=True)
    with open(header_path, "w") as f:
        f.write("/***************************************************************************************\n")
        f.write(" * FILE: src/fpu_rom_map.vh\n")
        f.write(" * DESCRIPTION: Auto-generated Flash ROM Address Map for ZX50 FPU Coprocessor.\n")
        f.write(" * DO NOT EDIT MANUALLY - Generated by tools/build_flash.py\n")
        f.write(" ***************************************************************************************/\n\n")
        f.write("`ifndef FPU_ROM_MAP_VH\n`define FPU_ROM_MAP_VH\n\n")
        f.write(f"  `define FLASH_QS_BASE     15'h{FLASH_QS_BASE:04X}\n")
        f.write(f"  `define FLASH_RECIP_BASE  15'h{FLASH_RECIP_BASE:04X}\n")
        f.write(f"  `define FLASH_SQRT_BASE   15'h{FLASH_SQRT_BASE:04X}\n")
        f.write(f"  `define FLASH_EXP2_BASE   15'h{FLASH_EXP2_BASE:04X}\n")
        f.write(f"  `define FLASH_LOG2_BASE   15'h{FLASH_LOG2_BASE:04X}\n")
        f.write(f"  `define FLASH_SIN_BASE    15'h{FLASH_SIN_BASE:04X}\n")
        f.write(f"  `define FLASH_COS_BASE    15'h{FLASH_COS_BASE:04X}\n")
        f.write(f"  `define FLASH_TAN_BASE    15'h{FLASH_TAN_BASE:04X}\n")
        f.write(f"  `define FLASH_LN_BASE     15'h{FLASH_LN_BASE:04X}\n")
        f.write(f"  `define FLASH_LOG10_BASE  15'h{FLASH_LOG10_BASE:04X}\n\n")
        f.write("`endif // FPU_ROM_MAP_VH\n")


def write_verilog_hex(hex_path: str, flash_image: bytearray):
    os.makedirs(os.path.dirname(hex_path), exist_ok=True)
    with open(hex_path, "w") as f:
        for byte in flash_image:
            f.write(f"{byte:02X}\n")


def main():
    os.makedirs("bin", exist_ok=True)
    os.makedirs("sim", exist_ok=True)

    image = generate_flash_image()

    with open(BIN_FILE, "wb") as f:
        f.write(image)

    write_verilog_hex(HEX_FILE, image)
    write_verilog_header(HEADER_FILE)

    print(f"[*] Generated Binary Image: {BIN_FILE} ({len(image)} bytes)")
    print(f"[*] Generated Simulation Hex: {HEX_FILE}")
    print(f"[*] Generated Verilog Header: {HEADER_FILE}")


if __name__ == "__main__":
    main()
    