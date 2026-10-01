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
FLASH_SIZE = 32768  # 32 KB active region for CA[14:0]
FLASH_QS_BASE = 0x0000  # Quarter-Square Table (1022 bytes)
FLASH_RECIP_BASE = 0x0400  # Reciprocal Table (512 bytes)
FLASH_SQRT_BASE = 0x0600  # Square Root Seed Table (512 bytes)
FLASH_EXP2_BASE = 0x0800  # Exp2 Table (512 bytes)
FLASH_LOG2_BASE = 0x0A00  # Log2 Table (512 bytes)
FLASH_SIN_BASE = 0x0C00  # Sine Table (512 bytes)
FLASH_COS_BASE = 0x0E00  # Cosine Table (512 bytes)
FLASH_TAN_BASE = 0x1000  # Tangent Table (512 bytes)
FLASH_LN_BASE = 0x1200  # Natural Log Table (512 bytes)
FLASH_LOG10_BASE = 0x1400  # Base-10 Log Table (512 bytes)
FLASH_CONST_BASE = 0x1600  # Mathematical Constants Table (128 bytes)

HEADER_FILE = "src/fpu_rom_map.vh"
HEX_FILE = "sim/fpu_rom.hex"
BIN_FILE = "bin/fpu_flash.bin"
EMU_BIN_FILE = "fpu_emu/rom/fpu_flash.bin"


# =============================================================================
# Individual Lookup Table Generators
# =============================================================================
def generate_qs_table() -> bytearray:
    """Table 1: Quarter-Square [ f(n) = floor(n^2 / 4) ] for n in [0..510]"""
    data = bytearray(511 * 2)
    for n in range(511):
        val = (n * n) // 4
        data[n * 2] = val & 0xFF
        data[n * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_recip_table() -> bytearray:
    """Table 2: Reciprocal [ f(x) = ceil(65536 / x) ] for x in [1..255]"""
    data = bytearray(256 * 2)
    for x in range(1, 256):
        val = min(65535, math.ceil(65536.0 / x))
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_sqrt_table() -> bytearray:
    """Table 3: Reciprocal Square Root Seeds for mantissa M in [1.0, 4.0).

    Index (8 bits):
      - Bit 7: Exponent parity bit (0: M in [1.0, 2.0), 1: M in [2.0, 4.0))
      - Bits 6..0: Top 7 fraction bits of mantissa.
    Value (16-bit unsigned Q0.16):
      - r0 = round((1.0 / sqrt(M)) * 65536)
    """
    data = bytearray(256 * 2)
    for x in range(256):
        if x < 128:
            # Even exponent: M in [1.0, 2.0)
            m = 1.0 + (x + 0.5) / 128.0
        else:
            # Odd exponent: M in [2.0, 4.0)
            m = 2.0 * (1.0 + (x - 128 + 0.5) / 128.0)
        r = 1.0 / math.sqrt(m)
        val = min(65535, int(round(r * 65536.0)))
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_exp2_table() -> bytearray:
    """Table 4: Exp2 [ f(x) = 2^(x/256) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(2 ** (x / 256.0) * 256) & 0xFFFF
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_log2_table() -> bytearray:
    """Table 5: Log2 [ f(x) = log2(1 + x/256) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(math.log2(1.0 + (x / 256.0)) * 256) & 0xFFFF
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_sin_table() -> bytearray:
    """Table 6: Sine [ f(x) = sin(x/256 * pi/2) * 256 ] for x in [0..255] (0 to 90 degrees)"""
    data = bytearray(256 * 2)
    for x in range(256):
        rad = (x / 256.0) * (math.pi / 2.0)
        val = min(65535, int(round(math.sin(rad) * 256.0)))
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_cos_table() -> bytearray:
    """Table 7: Cosine [ f(x) = cos(x/256 * pi/2) * 256 ] for x in [0..255] (0 to 90 degrees)"""
    data = bytearray(256 * 2)
    for x in range(256):
        rad = (x / 256.0) * (math.pi / 2.0)
        val = min(65535, int(round(math.cos(rad) * 256.0)))
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_tan_table() -> bytearray:
    """Table 8: Tangent [ f(x) = tan(x/256 * pi/4) * 256 ] for x in [0..255] (0 to 45 degrees)"""
    data = bytearray(256 * 2)
    for x in range(256):
        rad = (x / 256.0) * (math.pi / 4.0)
        val = min(65535, int(round(math.tan(rad) * 256.0)))
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_ln_table() -> bytearray:
    """Table 9: Natural Log [ f(x) = ln(1 + x/256) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(round(math.log(1.0 + (x / 256.0)) * 256.0)) & 0xFFFF
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_log10_table() -> bytearray:
    """Table 10: Base-10 Log [ f(x) = log10(1 + x/256) * 256 ] for x in [0..255]"""
    data = bytearray(256 * 2)
    for x in range(256):
        val = int(round(math.log10(1.0 + (x / 256.0)) * 256.0)) & 0xFFFF
        data[x * 2] = val & 0xFF
        data[x * 2 + 1] = (val >> 8) & 0xFF
    return data


def generate_constants_table() -> bytearray:
    """Table 11: Mathematical Constants (0xA0..0xAF). 16 entries * 8 bytes = 128 bytes."""
    data = bytearray(16 * 8)
    constants_def = [
        # (index, hex_value, num_bytes)
        (0x00, 0x40490FDB, 4),  # 0xA0: PUSH_PI_32
        (0x01, 0x400921FB54442D18, 8),  # 0xA1: PUSH_PI_64
        (0x02, 0x402DF854, 4),  # 0xA2: PUSH_E_32
        (0x03, 0x4005BF0A8B145769, 8),  # 0xA3: PUSH_E_64
        (0x04, 0x3F317218, 4),  # 0xA4: PUSH_LN2_32
        (0x05, 0x3FE62E42FEFA39EF, 8),  # 0xA5: PUSH_LN2_64
        (0x06, 0x3FB8AA3B, 4),  # 0xA6: PUSH_LOG2E_32
        (0x07, 0x3FF71547652B82FE, 8),  # 0xA7: PUSH_LOG2E_64
        (0x08, 0x40549A78, 4),  # 0xA8: PUSH_LOG2_10_32
        (0x09, 0x400A934F0979A371, 8),  # 0xA9: PUSH_LOG2_10_64
        (0x0A, 0x3E9A209B, 4),  # 0xAA: PUSH_LOG10_2_32
        (0x0B, 0x3FD34413509F79FF, 8),  # 0xAB: PUSH_LOG10_2_64
        (0x0C, 0x3FB504F3, 4),  # 0xAC: PUSH_SQRT2_32
        (0x0D, 0x3FF6A09E667F3BCD, 8),  # 0xAD: PUSH_SQRT2_64
        (0x0E, 0x3F3504F3, 4),  # 0xAE: PUSH_INV_SQRT2_32
        (0x0F, 0x3FE6A09E667F3BCD, 8),  # 0xAF: PUSH_INV_SQRT2_64
    ]
    for idx, hex_val, nbytes in constants_def:
        offset = idx * 8
        raw = hex_val.to_bytes(nbytes, byteorder="little")
        data[offset : offset + nbytes] = raw
    return data


# =============================================================================
# In-Memory Flash Population Helper (Used by fpu_sim.py)
# =============================================================================
def populate_flash_memory(flash_mem: bytearray) -> bytearray:
    """Populate an existing 32KB bytearray with all Flash LUTs at their base addresses."""
    qs = generate_qs_table()
    recip = generate_recip_table()
    sqrt = generate_sqrt_table()
    exp2 = generate_exp2_table()
    log2 = generate_log2_table()
    sin = generate_sin_table()
    cos = generate_cos_table()
    tan = generate_tan_table()
    ln = generate_ln_table()
    log10 = generate_log10_table()
    consts = generate_constants_table()

    flash_mem[FLASH_QS_BASE : FLASH_QS_BASE + len(qs)] = qs
    flash_mem[FLASH_RECIP_BASE : FLASH_RECIP_BASE + len(recip)] = recip
    flash_mem[FLASH_SQRT_BASE : FLASH_SQRT_BASE + len(sqrt)] = sqrt
    flash_mem[FLASH_EXP2_BASE : FLASH_EXP2_BASE + len(exp2)] = exp2
    flash_mem[FLASH_LOG2_BASE : FLASH_LOG2_BASE + len(log2)] = log2
    flash_mem[FLASH_SIN_BASE : FLASH_SIN_BASE + len(sin)] = sin
    flash_mem[FLASH_COS_BASE : FLASH_COS_BASE + len(cos)] = cos
    flash_mem[FLASH_TAN_BASE : FLASH_TAN_BASE + len(tan)] = tan
    flash_mem[FLASH_LN_BASE : FLASH_LN_BASE + len(ln)] = ln
    flash_mem[FLASH_LOG10_BASE : FLASH_LOG10_BASE + len(log10)] = log10
    flash_mem[FLASH_CONST_BASE : FLASH_CONST_BASE + len(consts)] = consts

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
        f.write(f"  `define FLASH_LOG10_BASE  15'h{FLASH_LOG10_BASE:04X}\n")
        f.write(f"  `define FLASH_CONST_BASE  15'h{FLASH_CONST_BASE:04X}\n\n")
        f.write("`endif // FPU_ROM_MAP_VH\n")


def write_verilog_hex(hex_path: str, flash_image: bytearray):
    os.makedirs(os.path.dirname(hex_path), exist_ok=True)
    with open(hex_path, "w") as f:
        for byte in flash_image:
            f.write(f"{byte:02X}\n")


def main():
    os.makedirs("bin", exist_ok=True)
    os.makedirs("sim", exist_ok=True)
    os.makedirs(os.path.dirname(EMU_BIN_FILE), exist_ok=True)

    image = generate_flash_image()

    with open(BIN_FILE, "wb") as f:
        f.write(image)

    with open(EMU_BIN_FILE, "wb") as f:
        f.write(image)

    write_verilog_hex(HEX_FILE, image)
    write_verilog_header(HEADER_FILE)

    print(f"[*] Generated Binary Image: {BIN_FILE} ({len(image)} bytes)")
    print(f"[*] Generated Emulator Image: {EMU_BIN_FILE} ({len(image)} bytes)")
    print(f"[*] Generated Simulation Hex: {HEX_FILE}")
    print(f"[*] Generated Verilog Header: {HEADER_FILE}")


if __name__ == "__main__":
    main()
