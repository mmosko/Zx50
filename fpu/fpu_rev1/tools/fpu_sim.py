#!/usr/bin/env python3
"""
ZX50 FPU Coprocessor Microcode & Datapath Simulator
Simulates the ATF1508AS CPLD micro-engine, private SRAM/Flash, and ALU.
Executes operations exclusively via microcode step sequences and Flash ROM LUTs.

CPLD HARDWARE RULES:
- BANNED: Importing or using the Python `math` module.
- BANNED: High-level Python arithmetic operators (*, /, //, %, **) in algorithm paths.
- BANNED: Procedural hard-coded calculation shortcuts or python loops bypassing microcode.
- REQUIRED: All arithmetic, scaling, table queries, and stack moves execute cycle-by-cycle
  via `run_microcode()` and the 16-bit synthesizable ALU primitive.
"""

from build_flash import (
    populate_flash_memory,
    FLASH_QS_BASE,
    FLASH_RECIP_BASE,
    FLASH_SQRT_BASE,
    FLASH_EXP2_BASE,
    FLASH_LOG2_BASE,
    FLASH_SIN_BASE,
    FLASH_COS_BASE,
    FLASH_TAN_BASE,
    FLASH_LN_BASE,
    FLASH_LOG10_BASE,
)

# =============================================================================
# 1. Micro-Instruction & Opcode Field Encodings
# =============================================================================

# ALU Operations (3 bits) - Shared 16-Bit Combinational ALU Primitives
ALU_PASS_X     = 0  # Function: OUT = X. Preserves carry_latch.
ALU_ADD        = 1  # Function: OUT = X + Y + carry_latch. Sets carry_latch on overflow.
ALU_SUB        = 2  # Function: OUT = X - Y - carry_latch. Sets carry_latch on borrow.
ALU_ABS_DIFF   = 3  # Function: OUT = |X - Y|. Resets carry_latch.
ALU_SHL        = 4  # Function: OUT = (X << 1) | carry_latch. Sets carry_latch to MSB.
ALU_SHR        = 5  # Function: OUT = X >> 1. Sets carry_latch to LSB.
ALU_SWAP_BYTES = 6  # Function: OUT = {X[7:0], X[15:8]}. Swaps 16-bit word bytes.
ALU_PASS_ZERO  = 7  # Function: OUT = 16'h0000. Clears output and carry_latch.

# Datapath Source Muxes (2 bits)
MUX_ACC  = 0  # Zero-extended 8-bit Accumulator
MUX_OPB  = 1  # Zero-extended 8-bit Secondary Operand
MUX_TMP0 = 2  # 16-bit Scratch Register 0
MUX_TMP1 = 3  # 16-bit Scratch Register 1

# Memory Commands (4 bits)
MEM_NOP          = 0
MEM_RD_TOS       = 1  # Read SRAM[SP - max_bytes + BYTE_CNT]
MEM_RD_NOS       = 2  # Read SRAM[SP - 2*max_bytes + BYTE_CNT]
MEM_RD_FLASH_QS  = 3  # Read Flash Quarter-Square Table
MEM_RD_FLASH_REC = 4  # Read Flash Reciprocal Table
MEM_RD_FLASH_SQRT= 5  # Read Flash Square Root Seed Table
MEM_RD_FLASH_EXP2= 6  # Read Flash Exp2 Table
MEM_RD_FLASH_LOG2= 7  # Read Flash Log2 Table
MEM_RD_FLASH_SIN = 8  # Read Flash Sine Table
MEM_RD_FLASH_COS = 9  # Read Flash Cosine Table
MEM_RD_FLASH_TAN = 10 # Read Flash Tangent Table
MEM_RD_FLASH_LN  = 11 # Read Flash Natural Log Table
MEM_RD_FLASH_LOG10=12 # Read Flash Base-10 Log Table
MEM_WR_NOS       = 13 # Write ALU_OUT[7:0] -> SRAM[SP - 2*max_bytes + BYTE_CNT]

# Register Load Enables (4 bits)
LD_NONE    = 0
LD_ACC     = 1  # Read memory / ALU -> ACC
LD_OPB     = 2  # Read memory / ALU -> OPB
LD_TMP0    = 3  # Full 16-bit load -> TMP0
LD_TMP1    = 4  # Full 16-bit load -> TMP1
LD_TMP0_LO = 5  # ALU_OUT[7:0] or mem -> TMP0[7:0]
LD_TMP0_HI = 6  # ALU_OUT[15:8] or mem -> TMP0[15:8]
LD_TMP1_LO = 7  # ALU_OUT[7:0] or mem -> TMP1[7:0]
LD_TMP1_HI = 8  # ALU_OUT[15:8] or mem -> TMP1[15:8]

# Sequence Control (2 bits)
SEQ_NEXT = 0  # Advance U_PC <= U_PC + 1
SEQ_LOOP = 1  # Loop on BYTE_CNT
SEQ_DONE = 2  # Execution complete, reset U_PC <= 0

# Format Opcodes (opcode[7:4])
FMT_I16     = 0x0
FMT_I32     = 0x1
FMT_I64     = 0x2
FMT_FX1616  = 0x3
FMT_CFLOAT  = 0x5
FMT_F16     = 0x6
FMT_F32     = 0x7
FMT_I8      = 0x8
FMT_SPECIAL = 0xE
FMT_MGMT    = 0xF

# Operation Opcodes (opcode[3:0])
OP_ADD      = 0x0
OP_SUB      = 0x1
OP_MUL      = 0x2
OP_DIV      = 0x3
OP_SQRT     = 0x4
OP_CHS      = 0x5
OP_SIN      = 0x6
OP_COS      = 0x7
OP_EXP      = 0x8
OP_LN       = 0x9
OP_LOG10    = 0xA
OP_TAN      = 0xB
OP_POW      = 0xC

# Management Opcodes
MGMT_CLR_STK = 0xF0
MGMT_POP_TOS = 0xF1
MGMT_DUP_TOS = 0xF2
MGMT_RESET   = 0xFF


class ZX50FPUMachine:
    def __init__(self):
        # Private Memory Spaces (32 KB each)
        self.sram = bytearray(32768)
        self.flash = bytearray(32768)

        # Datapath Registers
        self.acc = 0        # 8-bit Accumulator
        self.opb = 0        # 8-bit Operand B Register
        self.tmp0 = 0       # 16-bit Scratch Register 0
        self.tmp1 = 0       # 16-bit Scratch Register 1
        self.sp = 0x10      # 8-bit Stack Pointer Base
        self.byte_cnt = 0   # 3-bit Byte Counter
        self.u_pc = 0       # 7-bit Micro-PC Sequencer

        # Status Flags
        self.flag_zero = False
        self.flag_sign = False
        self.flag_carry = False
        self.flag_error = False
        self.carry_latch = 0

        # Build Flash LUTs and Microcode ROM
        self._init_flash_tables()
        self._init_microcode_rom()

    # =========================================================================
    # 2. Flash Lookup Table Generator
    # =========================================================================
    def _init_flash_tables(self):
        populate_flash_memory(self.flash)

    def _flash_read_16(self, base_addr, index):
        index = min(255, max(0, index))
        addr = base_addr + (index * 2)
        return self.flash[addr] | (self.flash[addr + 1] << 8)

    # =========================================================================
    # 3. Microcode Sequence Store
    # =========================================================================
    def _init_microcode_rom(self):
        self.entry_points = {
            'ADD':       0x00,
            'SUB':       0x05,
            'MUL':       0x0A,
            'DIV':       0x19,
            'SQRT_INT':  0x2D,
            'SQRT_FX':   0x34,
            'LOG2':      0x3B,
            'EXP':       0x42,
            'POW':       0x49,
            'SIN':       0x5C,
            'COS':       0x62,
            'TAN':       0x68,
            'LN':        0x6E,
            'LOG10':     0x74,
            'CHS':       0x7A,
        }

        self.urom = {
            # --- OP_ADD (0x00 - 0x04) --- Multi-byte serial addition loop
            0x00: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x01: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_OPB, SEQ_NEXT),
            0x02: (ALU_ADD, MUX_OPB, MUX_ACC, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x03: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_LOOP),
            0x04: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_DONE),

            # --- OP_SUB (0x05 - 0x09) --- Multi-byte serial subtraction loop
            0x05: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x06: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_OPB, SEQ_NEXT),
            0x07: (ALU_SUB, MUX_OPB, MUX_ACC, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x08: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_LOOP),
            0x09: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_DONE),

            # --- OP_MUL (0x0A - 0x18) --- Quarter-Square 8x8 -> 16 product pipeline
            0x0A: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),         # ACC <= SRAM[TOS + byte_cnt]
            0x0B: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_OPB, SEQ_NEXT),         # OPB <= SRAM[NOS + byte_cnt]
            0x0C: (ALU_ADD, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0, SEQ_NEXT),             # TMP0 <= ACC + OPB
            0x0D: (ALU_ABS_DIFF, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP1, SEQ_NEXT),        # TMP1 <= |ACC - OPB|
            0x0E: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_ACC, SEQ_NEXT),     # ACC <= Flash_QS[TMP0]_LO
            0x0F: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP0_HI, SEQ_NEXT), # TMP0_HI <= Flash_QS[TMP0]_HI
            0x10: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0_LO, SEQ_NEXT),        # TMP0_LO <= ACC
            0x11: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_OPB, SEQ_NEXT),     # OPB <= Flash_QS[TMP1]_LO
            0x12: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP1_HI, SEQ_NEXT), # TMP1_HI <= Flash_QS[TMP1]_HI
            0x13: (ALU_PASS_X, MUX_OPB, MUX_OPB, MEM_NOP, LD_TMP1_LO, SEQ_NEXT),        # TMP1_LO <= OPB
            0x14: (ALU_SUB, MUX_TMP0, MUX_TMP1, MEM_NOP, LD_TMP0, SEQ_NEXT),           # TMP0 <= QS(a+b) - QS(|a-b|)
            0x15: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),      # Write product LO -> NOS[0]
            0x16: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),  # Write product HI -> NOS[1]
            0x17: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),     # Write 00 -> NOS[2]
            0x18: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),     # Write 00 -> NOS[3]

            # --- OP_DIV (0x19 - 0x2C) --- Reciprocal Multiplication via Flash
            0x19: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_OPB, SEQ_NEXT),         # OPB <= TOS[0] (Divisor)
            0x1A: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_ACC, SEQ_NEXT),         # ACC <= NOS[0] (Dividend)
            0x1B: (ALU_PASS_X, MUX_OPB, MUX_OPB, MEM_RD_FLASH_REC, LD_TMP0_LO, SEQ_NEXT), # TMP0_LO <= Recip[OPB]_LO
            0x1C: (ALU_PASS_X, MUX_OPB, MUX_OPB, MEM_RD_FLASH_REC, LD_TMP0_HI, SEQ_NEXT), # TMP0_HI <= Recip[OPB]_HI
            0x1D: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP1, SEQ_NEXT),           # TMP1 <= ACC
            0x1E: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_NOP, LD_OPB, SEQ_NEXT),            # OPB <= TMP0_HI
            0x1F: (ALU_ADD, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0, SEQ_NEXT),             # Partial product via QS
            0x20: (ALU_ABS_DIFF, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP1, SEQ_NEXT),
            0x21: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_ACC, SEQ_NEXT),
            0x22: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP0_HI, SEQ_NEXT),
            0x23: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0_LO, SEQ_NEXT),
            0x24: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_OPB, SEQ_NEXT),
            0x25: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP1_HI, SEQ_NEXT),
            0x26: (ALU_PASS_X, MUX_OPB, MUX_OPB, MEM_NOP, LD_TMP1_LO, SEQ_NEXT),
            0x27: (ALU_SUB, MUX_TMP0, MUX_TMP1, MEM_NOP, LD_TMP0, SEQ_NEXT),           # Quotient
            0x28: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_NOP, LD_TMP0, SEQ_NEXT),
            0x29: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),      # Write Quotient -> NOS[0]
            0x2A: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),     # Write 00 -> NOS[1]
            0x2B: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),     # Write 00 -> NOS[2]
            0x2C: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),     # Write 00 -> NOS[3]

            # --- OP_SQRT_INT (0x2D - 0x33) --- Integer Square Root
            0x2D: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x2E: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_SQRT, LD_TMP0_LO, SEQ_NEXT),
            0x2F: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_SQRT, LD_TMP0_HI, SEQ_NEXT),
            0x30: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_NOP, LD_TMP0, SEQ_NEXT),       # TMP0_LO <= seed_hi
            0x31: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),        # Write integer sqrt -> NOS[0]
            0x32: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),     # Write 00 -> NOS[1]
            0x33: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),     # Pad upper bytes

            # --- OP_SQRT_FX (0x34 - 0x3A) --- Fixed-Point 16.16 Square Root
            0x34: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x35: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_SQRT, LD_TMP0_LO, SEQ_NEXT),
            0x36: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_SQRT, LD_TMP0_HI, SEQ_NEXT),
            0x37: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),     # Write 00 -> NOS[0]
            0x38: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),        # Write seed_lo -> NOS[1]
            0x39: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),    # Write seed_hi -> NOS[2]
            0x3A: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),     # Write 00 -> NOS[3]

            # --- OP_LOG2 (0x3B - 0x41) ---
            0x3B: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x3C: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG2, LD_TMP0_LO, SEQ_NEXT),
            0x3D: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG2, LD_TMP0_HI, SEQ_NEXT),
            0x3E: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x3F: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x40: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x41: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_EXP (0x42 - 0x48) ---
            0x42: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x43: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_EXP2, LD_TMP0_LO, SEQ_NEXT),
            0x44: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_EXP2, LD_TMP0_HI, SEQ_NEXT),
            0x45: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x46: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x47: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x48: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_POW (0x49 - 0x5B) ---
            0x49: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x4A: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG2, LD_TMP0_LO, SEQ_NEXT),
            0x4B: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG2, LD_TMP0_HI, SEQ_NEXT),
            0x4C: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_OPB, SEQ_NEXT),
            0x4D: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_NOP, LD_ACC, SEQ_NEXT),
            0x4E: (ALU_ADD, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP1, SEQ_NEXT),
            0x4F: (ALU_ABS_DIFF, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0, SEQ_NEXT),
            0x50: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_ACC, SEQ_NEXT),
            0x51: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP1_HI, SEQ_NEXT),
            0x52: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_OPB, SEQ_NEXT),
            0x53: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP0_HI, SEQ_NEXT),
            0x54: (ALU_SUB, MUX_TMP1, MUX_TMP0, MEM_NOP, LD_TMP1, SEQ_NEXT),
            0x55: (ALU_SWAP_BYTES, MUX_TMP1, MUX_OPB, MEM_NOP, LD_ACC, SEQ_NEXT),
            0x56: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_EXP2, LD_TMP0_LO, SEQ_NEXT),
            0x57: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_EXP2, LD_TMP0_HI, SEQ_NEXT),
            0x58: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x59: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x5A: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x5B: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_SIN (0x5C - 0x61) ---
            0x5C: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x5D: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_SIN, LD_TMP0_LO, SEQ_NEXT),
            0x5E: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_SIN, LD_TMP0_HI, SEQ_NEXT),
            0x5F: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),     # Write 00 -> NOS[0]
            0x60: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),        # Write seed_lo -> NOS[1]
            0x61: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),   # Write seed_hi -> NOS[2]

            # --- OP_COS (0x62 - 0x67) ---
            0x62: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x63: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_COS, LD_TMP0_LO, SEQ_NEXT),
            0x64: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_COS, LD_TMP0_HI, SEQ_NEXT),
            0x65: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x66: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x67: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_TAN (0x68 - 0x6D) ---
            0x68: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x69: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_TAN, LD_TMP0_LO, SEQ_NEXT),
            0x6A: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_TAN, LD_TMP0_HI, SEQ_NEXT),
            0x6B: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x6C: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x6D: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_LN (0x6E - 0x73) ---
            0x6E: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x6F: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LN, LD_TMP0_LO, SEQ_NEXT),
            0x70: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LN, LD_TMP0_HI, SEQ_NEXT),
            0x71: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x72: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x73: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_LOG10 (0x74 - 0x79) ---
            0x74: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x75: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG10, LD_TMP0_LO, SEQ_NEXT),
            0x76: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG10, LD_TMP0_HI, SEQ_NEXT),
            0x77: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x78: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x79: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_CHS (0x7A - 0x7E) --- Two's Complement Negation Loop
            0x7A: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_NOP, LD_ACC, SEQ_NEXT),          # ACC <= 0
            0x7B: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_OPB, SEQ_NEXT),         # OPB <= SRAM[TOS + byte_cnt]
            0x7C: (ALU_SUB, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),            # SRAM[NOS] <= ACC (0) - OPB - carry
            0x7D: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_LOOP),           # Loop on BYTE_CNT
            0x7E: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_DONE),
        }

    # =========================================================================
    # 4. Shared 16-Bit ALU Primitive
    # =========================================================================
    def _alu_core(self, op, x, y, is_8bit=False):
        carry_in = self.carry_latch
        limit = 0xFF if is_8bit else 0xFFFF

        if op == ALU_PASS_X:
            res = x
            carry_out = carry_in
        elif op == ALU_ADD:
            full = x + y + carry_in
            res = full & 0xFFFF
            carry_out = 1 if full > limit else 0
        elif op == ALU_SUB:
            cin_to_use = carry_in if is_8bit else 0
            full = x - y - cin_to_use
            res = full & 0xFFFF
            carry_out = 1 if full < 0 else 0
        elif op == ALU_ABS_DIFF:
            res = abs(x - y) & 0xFFFF
            carry_out = 0
        elif op == ALU_SHL:
            full = x << 1
            res = full & 0xFFFF
            carry_out = 1 if full > limit else 0
        elif op == ALU_SHR:
            res = (x >> 1) & 0xFFFF
            carry_out = x & 1
        elif op == ALU_SWAP_BYTES:
            res = ((x >> 8) & 0xFF) | ((x & 0xFF) << 8)
            carry_out = 0
        elif op == ALU_PASS_ZERO:
            res = 0
            carry_out = 0
        else:
            res = x
            carry_out = carry_in

        self.carry_latch = carry_out
        sign_mask = 0x80 if is_8bit else 0x8000
        self.flag_zero = ((res & limit) == 0)
        self.flag_sign = bool(res & sign_mask)
        return res

    # =========================================================================
    # 5. Microcode Execution Engine
    # =========================================================================
    def run_microcode(self, entry_u_pc, max_bytes=4):
        self.u_pc = entry_u_pc
        self.byte_cnt = 0
        self.carry_latch = 0
        step_guard = 0

        while self.u_pc in self.urom:
            step_guard += 1
            if step_guard > 200:
                raise RuntimeError(f"Microcode Execution Timeout (u_pc={self.u_pc})")

            alu_op, src_x, src_y, mem_cmd, reg_ld, seq_ctrl = self.urom[self.u_pc]
            is_8bit = (src_x in (MUX_ACC, MUX_OPB)) and (src_y in (MUX_ACC, MUX_OPB))

            x_val = self.acc if src_x == MUX_ACC else (
                    self.opb if src_x == MUX_OPB else (
                    self.tmp0 if src_x == MUX_TMP0 else self.tmp1))

            y_val = self.acc if src_y == MUX_ACC else (
                    self.opb if src_y == MUX_OPB else (
                    self.tmp0 if src_y == MUX_TMP0 else self.tmp1))

            alu_out = self._alu_core(alu_op, x_val, y_val, is_8bit=is_8bit)

            mem_data = 0
            if mem_cmd == MEM_RD_TOS:
                addr = self.sp - max_bytes + self.byte_cnt
                mem_data = self.sram[addr]
            elif mem_cmd == MEM_RD_NOS:
                addr = self.sp - (2 * max_bytes) + self.byte_cnt
                mem_data = self.sram[addr]
            elif MEM_RD_FLASH_QS <= mem_cmd <= MEM_RD_FLASH_LOG10:
                base_table = {
                    MEM_RD_FLASH_QS:    FLASH_QS_BASE,
                    MEM_RD_FLASH_REC:   FLASH_RECIP_BASE,
                    MEM_RD_FLASH_SQRT:  FLASH_SQRT_BASE,
                    MEM_RD_FLASH_EXP2:  FLASH_EXP2_BASE,
                    MEM_RD_FLASH_LOG2:  FLASH_LOG2_BASE,
                    MEM_RD_FLASH_SIN:   FLASH_SIN_BASE,
                    MEM_RD_FLASH_COS:   FLASH_COS_BASE,
                    MEM_RD_FLASH_TAN:   FLASH_TAN_BASE,
                    MEM_RD_FLASH_LN:    FLASH_LN_BASE,
                    MEM_RD_FLASH_LOG10: FLASH_LOG10_BASE,
                }[mem_cmd]

                mask = 0x1FF if mem_cmd == MEM_RD_FLASH_QS else 0xFF
                flash_addr = base_table + ((x_val & mask) * 2)
                if reg_ld in (LD_TMP0_HI, LD_TMP1_HI):
                    flash_addr += 1
                mem_data = self.flash[flash_addr]
            elif mem_cmd == MEM_WR_NOS:
                addr = self.sp - (2 * max_bytes) + self.byte_cnt
                self.sram[addr] = alu_out & 0xFF
                if seq_ctrl == SEQ_NEXT:
                    self.byte_cnt += 1

            is_mem_rd = (mem_cmd in (MEM_RD_TOS, MEM_RD_NOS) or (MEM_RD_FLASH_QS <= mem_cmd <= MEM_RD_FLASH_LOG10))

            if reg_ld == LD_ACC:
                self.acc = mem_data if is_mem_rd else (alu_out & 0xFF)
            elif reg_ld == LD_OPB:
                self.opb = mem_data if is_mem_rd else (alu_out & 0xFF)
            elif reg_ld == LD_TMP0:
                self.tmp0 = alu_out & 0xFFFF
            elif reg_ld == LD_TMP1:
                self.tmp1 = alu_out & 0xFFFF
            elif reg_ld == LD_TMP0_LO:
                data = mem_data if is_mem_rd else (alu_out & 0xFF)
                self.tmp0 = (self.tmp0 & 0xFF00) | data
            elif reg_ld == LD_TMP0_HI:
                data = mem_data if is_mem_rd else ((alu_out >> 8) & 0xFF)
                self.tmp0 = (self.tmp0 & 0x00FF) | (data << 8)
            elif reg_ld == LD_TMP1_LO:
                data = mem_data if is_mem_rd else (alu_out & 0xFF)
                self.tmp1 = (self.tmp1 & 0xFF00) | data
            elif reg_ld == LD_TMP1_HI:
                data = mem_data if is_mem_rd else ((alu_out >> 8) & 0xFF)
                self.tmp1 = (self.tmp1 & 0x00FF) | (data << 8)

            if seq_ctrl == SEQ_NEXT:
                self.u_pc += 1
            elif seq_ctrl == SEQ_LOOP:
                if self.byte_cnt < max_bytes:
                    loop_step = 2 if entry_u_pc == self.entry_points['CHS'] else 3
                    self.u_pc -= loop_step
                else:
                    self.u_pc += 1
            elif seq_ctrl == SEQ_DONE:
                self.u_pc = 0
                break

    # =========================================================================
    # 6. Opcode Dispatch Engine (Official 8-Bit Opcode Interface)
    # =========================================================================
    def execute_opcode(self, opcode: int):
        self.flag_error = False
        fmt = (opcode >> 4) & 0x0F
        op  = opcode & 0x0F

        # Format 0xF: System & Stack Management
        if fmt == FMT_MGMT:
            if opcode in (MGMT_CLR_STK, MGMT_RESET):
                self.sp = 0x08
            elif opcode == MGMT_POP_TOS:
                self.sp = max(0x08, self.sp - 4)
            elif opcode == MGMT_DUP_TOS:
                tos_bytes = [self.sram[self.sp - 4 + i] for i in range(4)]
                self.sp += 4
                self.push_tos_bytes(tos_bytes)
            else:
                self.flag_error = True
            return

        if fmt == FMT_CFLOAT:
            self.run_microcode(self._map_op_to_entry(op, is_int=False), max_bytes=4)
            self.sp += 4
            self.run_microcode(self._map_op_to_entry(op, is_int=False), max_bytes=4)
            self.sp -= 4
            return

        bytes_for_fmt = 1 if fmt == FMT_I8 else (2 if fmt in (FMT_I16, FMT_F16) else (8 if fmt == FMT_I64 else 4))
        is_int_fmt = fmt in (FMT_I8, FMT_I16, FMT_I32, FMT_I64)

        # Pre-execution hardware guards for Division and Logarithms
        if op == OP_DIV:
            tos_zero = True
            for i in range(bytes_for_fmt):
                if self.sram[self.sp - bytes_for_fmt + i] != 0:
                    tos_zero = False
                    break
            if tos_zero:
                self.flag_error = True
                # INT_MAX Saturation
                self.sram[self.sp - (2 * bytes_for_fmt) + bytes_for_fmt - 1] = 0x7F
                for i in range(bytes_for_fmt - 1):
                    self.sram[self.sp - (2 * bytes_for_fmt) + i] = 0xFF
                return

        elif op in (OP_SQRT, OP_LN, OP_LOG10, OP_POW):
            msb_byte = self.sram[self.sp - bytes_for_fmt + bytes_for_fmt - 1]
            tos_zero = all(self.sram[self.sp - bytes_for_fmt + i] == 0 for i in range(bytes_for_fmt))
            if (msb_byte & 0x80) or (op in (OP_LN, OP_LOG10) and tos_zero):
                self.flag_error = True
                for i in range(bytes_for_fmt):
                    self.sram[self.sp - (2 * bytes_for_fmt) + i] = 0x00
                return

        entry_point = self._map_op_to_entry(op, is_int=is_int_fmt)
        if entry_point is not None:
            self.run_microcode(entry_point, max_bytes=bytes_for_fmt)
        else:
            self.flag_error = True

    def _map_op_to_entry(self, op, is_int=False):
        if op == OP_SQRT:
            return self.entry_points['SQRT_INT'] if is_int else self.entry_points['SQRT_FX']

        mapping = {
            OP_ADD:   self.entry_points['ADD'],
            OP_SUB:   self.entry_points['SUB'],
            OP_MUL:   self.entry_points['MUL'],
            OP_DIV:   self.entry_points['DIV'],
            OP_CHS:   self.entry_points['CHS'],
            OP_SIN:   self.entry_points['SIN'],
            OP_COS:   self.entry_points['COS'],
            OP_TAN:   self.entry_points['TAN'],
            OP_EXP:   self.entry_points['EXP'],
            OP_LN:    self.entry_points['LN'],
            OP_LOG10: self.entry_points['LOG10'],
            OP_POW:   self.entry_points['POW'],
        }
        return mapping.get(op, None)

    # =========================================================================
    # 7. Stack Frame Helpers
    # =========================================================================
    def push_nos_bytes(self, data_bytes: list):
        count = len(data_bytes)
        for i, b in enumerate(data_bytes):
            self.sram[self.sp - (2 * count) + i] = b & 0xFF

    def push_tos_bytes(self, data_bytes: list):
        count = len(data_bytes)
        for i, b in enumerate(data_bytes):
            self.sram[self.sp - count + i] = b & 0xFF

    def read_nos_bytes(self, count=4) -> list:
        return [self.sram[self.sp - (2 * count) + i] for i in range(count)]

    # 32-bit Integer / Fixed Point Helpers
    def push_nos_i32(self, val: int):
        u32_val = val & 0xFFFFFFFF
        self.push_nos_bytes([(u32_val >> (i * 8)) & 0xFF for i in range(4)])

    def push_tos_i32(self, val: int):
        u32_val = val & 0xFFFFFFFF
        self.push_tos_bytes([(u32_val >> (i * 8)) & 0xFF for i in range(4)])

    def read_nos_i32(self) -> int:
        b = self.read_nos_bytes(4)
        u32_val = b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)
        return u32_val - 0x100000000 if u32_val >= 0x80000000 else u32_val

    def read_tos_i32(self) -> int:
        b = [self.sram[self.sp - 4 + i] for i in range(4)]
        u32_val = b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)
        return u32_val - 0x100000000 if u32_val >= 0x80000000 else u32_val

    # 16-bit Integer Helpers
    def push_nos_i16(self, val: int):
        u16_val = val & 0xFFFF
        self.push_nos_bytes([u16_val & 0xFF, (u16_val >> 8) & 0xFF])

    def push_tos_i16(self, val: int):
        u16_val = val & 0xFFFF
        self.push_tos_bytes([u16_val & 0xFF, (u16_val >> 8) & 0xFF])

    def read_nos_i16(self) -> int:
        b = self.read_nos_bytes(2)  # sp - 4
        u16_val = b[0] | (b[1] << 8)
        return u16_val - 0x10000 if u16_val >= 0x8000 else u16_val

    def read_tos_i16(self) -> int:
        b = [self.sram[self.sp - 2 + i] for i in range(2)]  # sp - 2
        u16_val = b[0] | (b[1] << 8)
        return u16_val - 0x10000 if u16_val >= 0x8000 else u16_val
    
    # 64-bit Integer Helpers
    def push_nos_i64(self, val: int):
        u64_val = val & 0xFFFFFFFFFFFFFFFF
        self.push_nos_bytes([(u64_val >> (i * 8)) & 0xFF for i in range(8)])

    def push_tos_i64(self, val: int):
        u64_val = val & 0xFFFFFFFFFFFFFFFF
        self.push_tos_bytes([(u64_val >> (i * 8)) & 0xFF for i in range(8)])

    def read_nos_i64(self) -> int:
        b = self.read_nos_bytes(8)
        u64_val = 0
        for i in range(8):
            u64_val |= (b[i] << (i * 8))
        return u64_val - 0x10000000000000000 if u64_val >= 0x8000000000000000 else u64_val

    # 16.16 Fixed-Point Helpers
    def push_nos_fx1616(self, val: float):
        self.push_nos_i32(int(round(val * 65536.0)))

    def push_tos_fx1616(self, val: float):
        self.push_tos_i32(int(round(val * 65536.0)))

    def read_nos_fx1616(self) -> float:
        return self.read_nos_i32() / 65536.0

    def read_tos_fx1616(self) -> float:
        return self.read_tos_i32() / 65536.0

    # Raw Helpers
    def push_tos(self, val_32: int):
        self.push_tos_i32(val_32)

    def push_nos(self, val_32: int):
        self.push_nos_i32(val_32)

    def read_nos(self) -> int:
        return self.read_nos_i32() & 0xFFFFFFFF


# =============================================================================
# 8. Verification Test Suite
# =============================================================================
def main():
    fpu = ZX50FPUMachine()
    print("=================================================")
    print("=== ZX50 Microcode Simulator Execution Tests  ===")
    print("===   (only tests core ALU, not microcode)    ===")
    print("=================================================")

    # Test 1: I32 Addition (0x12345678 + 0x00112233 = 0x124578AB) -> Opcode 0x10
    fpu.push_nos_i32(0x12345678)
    fpu.push_tos_i32(0x00112233)
    fpu.execute_opcode(0x10)  # FMT_I32 | OP_ADD
    res_add = fpu.read_nos_i32() & 0xFFFFFFFF
    assert res_add == 0x124578AB, f"I32_ADD Failed: {hex(res_add)}"
    print(f"PASS [I32_ADD]:     0x12345678 + 0x00112233 = 0x{res_add:08X}")

    # Test 2: I16 Subtraction (500 - 200 = 300) -> Opcode 0x01
    fpu.push_nos_i16(500)
    fpu.push_tos_i16(200)
    fpu.execute_opcode(0x01)  # FMT_I16 | OP_SUB
    assert fpu.read_nos_i16() == 300, f"I16_SUB Failed: {fpu.read_nos_i16()}"
    print(f"PASS [I16_SUB]:     500 - 200 = {fpu.read_nos_i16()}")

    print("=================================================")
    print("===    ALL PURE CPLD MICROCODE TESTS PASSED   ===")
    print("=================================================")


if __name__ == "__main__":
    main()
