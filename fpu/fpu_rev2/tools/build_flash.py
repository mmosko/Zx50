#!/usr/bin/env python3
"""
tools/build_flash.py
ZX50 FPU Flash ROM LUT Generator & Serializer

Defines individual generator functions for each lookup table:
  1. Reciprocal      (FLASH_RECIP_BASE  = 0x0400)
  2. Sqrt Seed       (FLASH_SQRT_BASE   = 0x0600)
  3. Exp2            (FLASH_EXP2_BASE   = 0x0800)
  4. Log2            (FLASH_LOG2_BASE   = 0x0A00)
  5. Sine            (FLASH_SIN_BASE    = 0x0C00)
  6. Cosine          (FLASH_COS_BASE    = 0x0E00)
  7. Tangent         (FLASH_TAN_BASE    = 0x1000)
  8. Natural Log     (FLASH_LN_BASE     = 0x1200)
  9. Base-10 Log     (FLASH_LOG10_BASE  = 0x1400)

Serializes all tables into:
  - bin/fpu_flash.bin  : Raw 32KB binary image for physical EEPROM/Flash burners
  - sim/fpu_rom.hex    : Verilog $readmemh image for simulation
  - src/fpu_rom_map.vh : Verilog header containing memory base addresses
"""

from decimal import Decimal, getcontext
import math
import os

# ROM Parameters & Base Addresses
FLASH_SIZE = 32768  # 32 KB active region for CA[14:0]
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
FLASH_CORDIC_ATAN32_BASE = 0x1800  # CORDIC Arctangent 32-bit Table (128 bytes: 32 x 4 bytes)
FLASH_CORDIC_ATAN64_BASE = 0x1900  # CORDIC Arctangent 64-bit Table (512 bytes: 64 x 8 bytes)
FLASH_TRIG_CONST_BASE = 0x1B00  # Trigonometric & CORDIC Constants (128 bytes: 16 x 8 bytes)

TABLES_DEF = [
    ("RECIP", FLASH_RECIP_BASE, "Reciprocal Table (512 bytes)"),
    ("SQRT", FLASH_SQRT_BASE, "Square Root Seed Table (512 bytes)"),
    ("EXP2", FLASH_EXP2_BASE, "Exp2 Table (512 bytes)"),
    ("LOG2", FLASH_LOG2_BASE, "Log2 Table (512 bytes)"),
    ("SIN", FLASH_SIN_BASE, "Sine Table (512 bytes)"),
    ("COS", FLASH_COS_BASE, "Cosine Table (512 bytes)"),
    ("TAN", FLASH_TAN_BASE, "Tangent Table (512 bytes)"),
    ("LN", FLASH_LN_BASE, "Natural Log Table (512 bytes)"),
    ("LOG10", FLASH_LOG10_BASE, "Base-10 Log Table (512 bytes)"),
    ("CONST", FLASH_CONST_BASE, "Mathematical Constants Table (128 bytes)"),
    ("CORDIC_ATAN32", FLASH_CORDIC_ATAN32_BASE, "CORDIC Arctangent 32-bit Table (128 bytes)"),
    ("CORDIC_ATAN64", FLASH_CORDIC_ATAN64_BASE, "CORDIC Arctangent 64-bit Table (512 bytes)"),
    ("TRIG_CONST", FLASH_TRIG_CONST_BASE, "Trigonometric & CORDIC Constants (128 bytes)"),
]

HEADER_FILE = "src/fpu_rom_map.vh"
HEX_FILE = "sim/fpu_rom.hex"
BIN_FILE = "bin/fpu_flash.bin"
EMU_BIN_FILE = "fpu_emu/rom/fpu_flash.bin"
PY_CONST_MAP_FILE = "fpu_emu/rom/fpu_const_map.py"


# =============================================================================
# Individual Lookup Table Generators
# =============================================================================
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


CONSTANTS_DEF = [
    # (enum_name, slot, hex_val, num_bytes, description)
    # Mathematical Constants (0xA0..0xAF push opcodes)
    ("PI_F32", 0, 0x40490FDB, 4, "pi in IEEE-754 single precision"),
    ("PI_F64", 2, 0x400921FB54442D18, 8, "pi in IEEE-754 double precision"),
    ("E_F32", 4, 0x402DF854, 4, "e in IEEE-754 single precision"),
    ("E_F64", 6, 0x4005BF0A8B145769, 8, "e in IEEE-754 double precision"),
    ("LN2_F32", 8, 0x3F317218, 4, "ln(2) in IEEE-754 single precision"),
    ("LN2_F64", 10, 0x3FE62E42FEFA39EF, 8, "ln(2) in IEEE-754 double precision"),
    ("LOG2E_F32", 12, 0x3FB8AA3B, 4, "log2(e) in IEEE-754 single precision"),
    ("LOG2E_F64", 14, 0x3FF71547652B82FE, 8, "log2(e) in IEEE-754 double precision"),
    ("LOG2_10_F32", 16, 0x40549A78, 4, "log2(10) in IEEE-754 single precision"),
    ("LOG2_10_F64", 18, 0x400A934F0979A371, 8, "log2(10) in IEEE-754 double precision"),
    ("LOG10_2_F32", 20, 0x3E9A209B, 4, "log10(2) in IEEE-754 single precision"),
    ("LOG10_2_F64", 22, 0x3FD34413509F79FF, 8, "log10(2) in IEEE-754 double precision"),
    ("SQRT2_F32", 24, 0x3FB504F3, 4, "sqrt(2) in IEEE-754 single precision"),
    ("SQRT2_F64", 26, 0x3FF6A09E667F3BCD, 8, "sqrt(2) in IEEE-754 double precision"),
    ("INV_SQRT2_F32", 28, 0x3F3504F3, 4, "1/sqrt(2) in IEEE-754 single precision"),
    ("INV_SQRT2_F64", 30, 0x3FE6A09E667F3BCD, 8, "1/sqrt(2) in IEEE-754 double precision"),

    # IEEE-754 Special Constants
    ("ONE_F32", 32, 0x3F800000, 4, "1.0 in IEEE-754 single precision"),
    ("ONE_F64", 33, 0x3FF0000000000000, 8, "1.0 in IEEE-754 double precision"),
    ("NAN_F32", 35, 0x7FC00000, 4, "Quiet NaN in IEEE-754 single precision"),
    ("NAN_F64", 36, 0x7FF8000000000000, 8, "Quiet NaN in IEEE-754 double precision"),
    ("POS_INF_F32", 38, 0x7F800000, 4, "+Infinity in IEEE-754 single precision"),
    ("NEG_INF_F32", 39, 0xFF800000, 4, "-Infinity in IEEE-754 single precision"),
    ("POS_INF_F64", 40, 0x7FF0000000000000, 8, "+Infinity in IEEE-754 double precision"),
    ("NEG_INF_F64", 42, 0xFFF0000000000000, 8, "-Infinity in IEEE-754 double precision"),

    # Range Reduction Constants
    ("TWO_OVER_PI_F32", 44, 0x3F22F983, 4, "2/pi in IEEE-754 single precision"),
    ("TWO_OVER_PI_F64", 45, 0x3FE45F306DC9C883, 8, "2/pi in IEEE-754 double precision"),

    # Cody-Waite Split Constants
    ("CW_C1_F32", 47, 0x3FC90F80, 4, "Cody-Waite C1 in IEEE-754 single precision"),
    ("CW_C2_F32", 48, 0x37354443, 4, "Cody-Waite C2 in IEEE-754 single precision"),
    ("CW_C1_F64", 49, 0x3FF921FB54400000, 8, "Cody-Waite C1 in IEEE-754 double precision"),
    ("CW_C2_F64", 51, 0x3DD0B4611A626331, 8, "Cody-Waite C2 in IEEE-754 double precision"),
    ("CW_C3_F64", 53, 0x3BA3198A2E037073, 8, "Cody-Waite C3 in IEEE-754 double precision"),

    # CORDIC Constants
    ("CORDIC_INV_K_32", 55, 0x26DD3B6A, 4, "CORDIC 1/K scale factor in Q2.30"),
    ("CORDIC_INV_K_64", 56, 0x26DD3B6A10D7969A, 8, "CORDIC 1/K scale factor in Q2.62"),
]


def generate_constants_table() -> bytearray:
    """Table 11: Mathematical & Algorithm Constants (256 bytes / 64 word slots)."""
    data = bytearray(256)
    for _, slot, hex_val, nbytes, _ in CONSTANTS_DEF:
        offset = slot * 4
        raw = hex_val.to_bytes(nbytes, byteorder="little")
        data[offset : offset + nbytes] = raw
    return data


def generate_cordic_atan32_table() -> bytearray:
    """Table 12: CORDIC Arctangent 32-bit Table [ theta_i = atan(2^-i) in Q2.30 ] for i in [0..31]."""
    getcontext().prec = 100
    pi = Decimal(
        "3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679"
    )
    scale30 = Decimal(1 << 30)

    data = bytearray(32 * 4)
    for i in range(32):
        if i == 0:
            angle = pi / Decimal(4)
        else:
            x = Decimal(1) / (Decimal(2) ** i)
            term = x
            x_sq = x * x
            angle = x
            sign = -1
            denom = 3
            for _ in range(50):
                term *= x_sq
                delta = term / denom
                if delta == 0:
                    break
                angle += sign * delta
                sign = -sign
                denom += 2
        val = int(round(angle * scale30)) & 0xFFFFFFFF
        data[i * 4 : i * 4 + 4] = val.to_bytes(4, byteorder="little")
    return data


def generate_cordic_atan64_table() -> bytearray:
    """Table 13: CORDIC Arctangent 64-bit Table [ theta_i = atan(2^-i) in Q2.62 ] for i in [0..63]."""
    getcontext().prec = 100
    pi = Decimal(
        "3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679"
    )
    scale62 = Decimal(1 << 62)

    data = bytearray(64 * 8)
    for i in range(64):
        if i == 0:
            angle = pi / Decimal(4)
        else:
            x = Decimal(1) / (Decimal(2) ** i)
            term = x
            x_sq = x * x
            angle = x
            sign = -1
            denom = 3
            for _ in range(60):
                term *= x_sq
                delta = term / denom
                if delta == 0:
                    break
                angle += sign * delta
                sign = -sign
                denom += 2
        val = int(round(angle * scale62)) & 0xFFFFFFFFFFFFFFFF
        data[i * 8 : i * 8 + 8] = val.to_bytes(8, byteorder="little")
    return data


def generate_trig_constants_table() -> bytearray:
    """Table 14: Trigonometric & CORDIC Constants (16 entries * 8 bytes = 128 bytes)."""
    getcontext().prec = 100
    pi = Decimal(
        "3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679"
    )
    # Compute CORDIC K for 64 stages
    k = Decimal(1)
    for i in range(64):
        k *= (Decimal(1) + (Decimal(1) / (Decimal(4) ** i))).sqrt()
    inv_k = Decimal(1) / k

    inv_k_32 = int(round(inv_k * Decimal(1 << 30))) & 0xFFFFFFFF
    inv_k_64 = int(round(inv_k * Decimal(1 << 62))) & 0xFFFFFFFFFFFFFFFF
    half_pi_32 = int(round((pi / Decimal(2)) * Decimal(1 << 30))) & 0xFFFFFFFF
    half_pi_64 = int(round((pi / Decimal(2)) * Decimal(1 << 62))) & 0xFFFFFFFFFFFFFFFF
    two_over_pi_32 = int(round((Decimal(2) / pi) * Decimal(1 << 31))) & 0xFFFFFFFF
    two_over_pi_64 = int(round((Decimal(2) / pi) * Decimal(1 << 63))) & 0xFFFFFFFFFFFFFFFF
    quarter_pi_32 = int(round((pi / Decimal(4)) * Decimal(1 << 30))) & 0xFFFFFFFF
    quarter_pi_64 = int(round((pi / Decimal(4)) * Decimal(1 << 62))) & 0xFFFFFFFFFFFFFFFF

    constants = [
        # (slot, hex_val, num_bytes)
        (0x00, inv_k_32, 4),  # INV_K_32 (Q2.30)
        (0x01, inv_k_64, 8),  # INV_K_64 (Q2.62)
        (0x02, half_pi_32, 4),  # HALF_PI_32 (Q2.30)
        (0x03, half_pi_64, 8),  # HALF_PI_64 (Q2.62)
        (0x04, two_over_pi_32, 4),  # TWO_OVER_PI_32 (Q1.31)
        (0x05, two_over_pi_64, 8),  # TWO_OVER_PI_64 (Q1.63)
        (0x06, quarter_pi_32, 4),  # QUARTER_PI_32 (Q2.30)
        (0x07, quarter_pi_64, 8),  # QUARTER_PI_64 (Q2.62)
        (0x08, 0x3F22F983, 4),  # TWO_OVER_PI_F32 (IEEE-754)
        (0x09, 0x3FE45F306DC9C883, 8),  # TWO_OVER_PI_F64 (IEEE-754)
        (0x0A, 0x3FC90FDB, 4),  # HALF_PI_F32 (IEEE-754)
        (0x0B, 0x3FF921FB54442D18, 8),  # HALF_PI_F64 (IEEE-754)
        (0x0C, 0x40490FDB, 4),  # PI_F32 (IEEE-754)
        (0x0D, 0x400921FB54442D18, 8),  # PI_F64 (IEEE-754)
        (0x0E, 0x3F1B74EE, 4),  # INV_K_F32 (IEEE-754)
        (0x0F, 0x3FE36E9DE57788A5, 8),  # INV_K_F64 (IEEE-754)
    ]

    data = bytearray(16 * 8)
    for idx, hex_val, nbytes in constants:
        offset = idx * 8
        raw = hex_val.to_bytes(nbytes, byteorder="little")
        data[offset : offset + nbytes] = raw
    return data


# =============================================================================
# In-Memory Flash Population Helper (Used by fpu_sim.py)
# =============================================================================
def populate_flash_memory(flash_mem: bytearray) -> bytearray:
    """Populate an existing 32KB bytearray with all Flash LUTs at their base addresses."""
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
    cordic_atan32 = generate_cordic_atan32_table()
    cordic_atan64 = generate_cordic_atan64_table()
    trig_consts = generate_trig_constants_table()

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
    flash_mem[FLASH_CORDIC_ATAN32_BASE : FLASH_CORDIC_ATAN32_BASE + len(cordic_atan32)] = cordic_atan32
    flash_mem[FLASH_CORDIC_ATAN64_BASE : FLASH_CORDIC_ATAN64_BASE + len(cordic_atan64)] = cordic_atan64
    flash_mem[FLASH_TRIG_CONST_BASE : FLASH_TRIG_CONST_BASE + len(trig_consts)] = trig_consts

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
        f.write(f"  `define FLASH_RECIP_BASE         15'h{FLASH_RECIP_BASE:04X}\n")
        f.write(f"  `define FLASH_SQRT_BASE          15'h{FLASH_SQRT_BASE:04X}\n")
        f.write(f"  `define FLASH_EXP2_BASE          15'h{FLASH_EXP2_BASE:04X}\n")
        f.write(f"  `define FLASH_LOG2_BASE          15'h{FLASH_LOG2_BASE:04X}\n")
        f.write(f"  `define FLASH_SIN_BASE           15'h{FLASH_SIN_BASE:04X}\n")
        f.write(f"  `define FLASH_COS_BASE           15'h{FLASH_COS_BASE:04X}\n")
        f.write(f"  `define FLASH_TAN_BASE           15'h{FLASH_TAN_BASE:04X}\n")
        f.write(f"  `define FLASH_LN_BASE            15'h{FLASH_LN_BASE:04X}\n")
        f.write(f"  `define FLASH_LOG10_BASE         15'h{FLASH_LOG10_BASE:04X}\n")
        f.write(f"  `define FLASH_CONST_BASE         15'h{FLASH_CONST_BASE:04X}\n")
        f.write(f"  `define FLASH_CORDIC_ATAN32_BASE 15'h{FLASH_CORDIC_ATAN32_BASE:04X}\n")
        f.write(f"  `define FLASH_CORDIC_ATAN64_BASE 15'h{FLASH_CORDIC_ATAN64_BASE:04X}\n")
        f.write(f"  `define FLASH_TRIG_CONST_BASE    15'h{FLASH_TRIG_CONST_BASE:04X}\n\n")
        f.write("  // FPU Constants Word Slot Map (32-bit words from FLASH_CONST_BASE)\n")
        for name, slot, _, _, _ in CONSTANTS_DEF:
            f.write(f"  `define CONST_SLOT_{name:<18} 6'd{slot}\n")
        f.write("\n")
        f.write("`endif // FPU_ROM_MAP_VH\n")


def write_python_constants(py_path: str):
    os.makedirs(os.path.dirname(py_path), exist_ok=True)
    with open(py_path, "w") as f:
        f.write('"""Auto-generated by tools/build_flash.py - DO NOT EDIT MANUALLY.\n\n')
        f.write("FPU Tables Base Addresses and Word Slot Maps for EBR / Flash ROM.\n")
        f.write('"""\n\n')
        f.write("from enum import IntEnum\n\n\n")
        f.write("class FpuTables(IntEnum):\n")
        f.write('    """Flash ROM Table Base Byte Addresses."""\n')
        for name, base_addr, desc in TABLES_DEF:
            f.write(f"    {name} = 0x{base_addr:04X}  # {desc}\n")
        f.write("\n\n")
        f.write("class FpuTable(IntEnum):\n")
        f.write('    """4-bit Table Identifier for LDC instruction (MicroOp.LDC).\n\n')
        f.write("    Mapped to physical EBR and base offset in memory controller:\n")
        f.write("      - RECIP: EBR 4 (16-bit), base 0x000 (words 0..255)\n")
        f.write("      - SQRT:  EBR 4 (16-bit), base 0x100 (words 256..511)\n")
        f.write("      - TRIG:  EBR 2 & 3 (paired 32-bit), base 0x000 (words 0..127)\n")
        f.write("      - CHEB:  EBR 2 & 3 (paired 32-bit), base 0x080 (words 128..255)\n")
        f.write("      - CONST: EBR 2 & 3 (paired 32-bit), base 0x100 (words 256..319)\n")
        f.write('    """\n')
        f.write("    RECIP = 0b000  # 0: EBR 4 (16-bit), base 0x000 (words 0..255)\n")
        f.write("    SQRT = 0b001   # 1: EBR 4 (16-bit), base 0x100 (words 256..511)\n")
        f.write("    TRIG = 0b100   # 4: EBR 2 & 3 (paired 32-bit), base 0x000 (words 0..127)\n")
        f.write("    CHEB = 0b101   # 5: EBR 2 & 3 (paired 32-bit), base 0x080 (words 128..255)\n")
        f.write("    CONST = 0b110  # 6: EBR 2 & 3 (paired 32-bit), base 0x100 (words 256..319)\n\n\n")
        f.write("class FpuConst(IntEnum):\n")
        f.write('    """FPU Constants Word Slot Map for EBR Constants ROM.\n')
        f.write("    Each slot represents a 32-bit word offset from CONST table base (EBR 2/3 offset 0x100).\n")
        f.write('    """\n')
        for name, slot, _, _, desc in CONSTANTS_DEF:
            f.write(f"    {name} = {slot}  # {desc}\n")
        f.write("\n")


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
    write_python_constants(PY_CONST_MAP_FILE)

    print(f"[*] Generated Binary Image: {BIN_FILE} ({len(image)} bytes)")
    print(f"[*] Generated Emulator Image: {EMU_BIN_FILE} ({len(image)} bytes)")
    print(f"[*] Generated Simulation Hex: {HEX_FILE}")
    print(f"[*] Generated Verilog Header: {HEADER_FILE}")
    print(f"[*] Generated Python Map: {PY_CONST_MAP_FILE}")


if __name__ == "__main__":
    main()
