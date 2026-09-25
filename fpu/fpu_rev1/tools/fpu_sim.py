#!/usr/bin/env python3
"""
ZX50 FPU Coprocessor Microcode & Datapath Simulator
Simulates the ATF1508AS CPLD micro-engine, private SRAM/Flash, and ALU.
Supports: i16, i32, fx1616 math and management commands via opcode dispatch.
"""

import math
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

# =============================================================================
# ALU Operations (3 bits) - Shared 16-Bit Combinational ALU Primitives
# =============================================================================

# ALU_PASS_X (0): Passive Data Bypass / Register Transfer
# - Function: OUT = X
# - Flags: Preserves 'carry_latch' unchanged. Updates ZERO and SIGN flags based on OUT.
# - Use Case: Used for direct memory-to-register loads, pass-through reads, and moving
#   values between ACC, OPB, TMP0, and TMP1 without corrupting carry chain state.
ALU_PASS_X = 0

# ALU_ADD (1): Binary Addition with Carry Propagation
# - Function: OUT = X + Y + carry_latch
# - Flags: Sets 'carry_latch' on 8-bit or 16-bit overflow (> 0xFF / > 0xFFFF).
# - Use Case: Core primitive for multi-byte serial integer/fixed-point addition loops
#   and calculating Quarter-Square table sum indices (a + b).
ALU_ADD = 1

# ALU_SUB (2): Binary Subtraction with Borrow Propagation
# - Function: OUT = X - Y - carry_latch
# - Flags: Sets 'carry_latch' on underflow / borrow (< 0).
# - Use Case: Core primitive for multi-byte serial integer/fixed-point subtraction loops,
#   Quarter-Square table product subtractions [f(a+b) - f(|a-b|)], and reciprocal division.
ALU_SUB = 2

# ALU_ABS_DIFF (3): Unsigned Absolute Difference
# - Function: OUT = |X - Y|
# - Flags: Resets 'carry_latch' to 0.
# - Use Case: Computes the unsigned distance between two 8-bit operands |a - b| for
#   Quarter-Square table lookups without requiring extra sign-extension or conditional branching logic.
ALU_ABS_DIFF = 3

# ALU_SHL (4): 1-Bit Logical Shift Left
# - Function: OUT = (X << 1) | carry_latch (or 0 depending on loop mode)
# - Flags: Sets 'carry_latch' to the MSB shifted out of the operand.
# - Use Case: Multi-precision bit alignment, fast power-of-two fixed-point scaling, and
#   floating-point (F16/F32) mantissa normalization loops.
ALU_SHL = 4

# ALU_SHR (5): 1-Bit Logical Shift Right
# - Function: OUT = X >> 1
# - Flags: Sets 'carry_latch' to the LSB shifted out of the operand.
# - Use Case: Microcoded serial shift loop for floating-point (F16/F32) exponent alignment
#   (shifting smaller mantissa right until exponents match) without a hardware barrel shifter.
ALU_SHR = 5

# ALU_SWAP_BYTES (6): 16-Bit Endian / Byte Swap
# - Function: OUT = {X[7:0], X[15:8]}
# - Flags: Resets 'carry_latch' to 0.
# - Use Case: Swaps high and low bytes of 16-bit scratch registers (TMP0/TMP1) when
#   serializing 16-bit Flash lookup table results out to SRAM in Little-Endian byte order.
ALU_SWAP_BYTES = 6

# ALU_PASS_ZERO (7): Hardwired Zero Clear
# - Function: OUT = 16'h0000
# - Flags: Resets 'carry_latch' to 0. Sets ZERO flag = True.
# - Use Case: Used for zero-padding upper bytes when writing 8-bit or 16-bit calculation
#   results into 32-bit SRAM stack frames, or clearing scratch registers.
ALU_PASS_ZERO = 7

# Datapath Source Muxes (2 bits)
MUX_ACC  = 0  # Zero-extended 8-bit Accumulator
MUX_OPB  = 1  # Zero-extended 8-bit Secondary Operand
MUX_TMP0 = 2  # 16-bit Scratch Register 0
MUX_TMP1 = 3  # 16-bit Scratch Register 1

# Memory Commands (3 bits)
MEM_NOP          = 0
MEM_RD_TOS       = 1  # Read SRAM[SP - 4 + BYTE_CNT]
MEM_RD_NOS       = 2  # Read SRAM[SP - 8 + BYTE_CNT]
MEM_RD_FLASH_QS  = 3  # Read Flash Quarter-Square Table
MEM_RD_FLASH_REC = 4  # Read Flash Reciprocal Table
MEM_RD_FLASH_SQRT= 5  # Read Flash Square Root Seed Table
MEM_RD_FLASH_EXP2= 6  # Read Flash Exp2 Table
MEM_RD_FLASH_LOG2= 7  # Read Flash Log2 Table
MEM_WR_NOS       = 8  # Write ALU_OUT[7:0] -> SRAM[SP - 8 + BYTE_CNT]

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
SEQ_LOOP = 1  # Loop on BYTE_CNT (0 -> 1 -> ... -> max_bytes-1)
SEQ_DONE = 2  # Execution complete, reset U_PC <= 0

# Format Opcodes (opcode[7:4])
FMT_I16     = 0x0
FMT_I32     = 0x1
FMT_I64     = 0x2
FMT_FX1616  = 0x3
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
        # Memory Spaces (32 KB each)
        self.sram = bytearray(32768)
        self.flash = bytearray(32768)

        # Registers
        self.acc = 0        # 8-bit
        self.opb = 0        # 8-bit
        self.tmp0 = 0       # 16-bit
        self.tmp1 = 0       # 16-bit
        self.sp = 0x08      # 8-bit Stack Pointer
        self.byte_cnt = 0   # 3-bit Loop Index
        self.u_pc = 0       # 7-bit Micro-PC

        # Flags
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

    # =========================================================================
    # 3. Microcode Sequence Store
    # =========================================================================
    def _init_microcode_rom(self):
        self.entry_points = {
            'ADD':  0x00,
            'SUB':  0x05,
            'MUL':  0x0A,
            'DIV':  0x19,
            'SQRT': 0x2F,
            'LOG2': 0x36,
            'EXP':  0x3D,
            'POW':  0x44,
        }

        self.urom = {
            # --- OP_ADD (0x00 - 0x04) ---
            0x00: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x01: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_OPB, SEQ_NEXT),
            0x02: (ALU_ADD, MUX_OPB, MUX_ACC, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x03: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_LOOP),
            0x04: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_DONE),

            # --- OP_SUB (0x05 - 0x09) ---
            0x05: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x06: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_OPB, SEQ_NEXT),
            0x07: (ALU_SUB, MUX_OPB, MUX_ACC, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x08: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_LOOP),
            0x09: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_NONE, SEQ_DONE),

            # --- OP_MUL (0x0A - 0x18) ---
            0x0A: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x0B: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_OPB, SEQ_NEXT),
            0x0C: (ALU_ADD, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0, SEQ_NEXT),
            0x0D: (ALU_ABS_DIFF, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP1, SEQ_NEXT),
            0x0E: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_ACC, SEQ_NEXT),
            0x0F: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP0_HI, SEQ_NEXT),
            0x10: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0_LO, SEQ_NEXT),
            0x11: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_OPB, SEQ_NEXT),
            0x12: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP1_HI, SEQ_NEXT),
            0x13: (ALU_PASS_X, MUX_OPB, MUX_OPB, MEM_NOP, LD_TMP1_LO, SEQ_NEXT),
            0x14: (ALU_SUB, MUX_TMP0, MUX_TMP1, MEM_NOP, LD_TMP0, SEQ_NEXT),
            0x15: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x16: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x17: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x18: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_SQRT (0x2F - 0x35) ---
            0x2F: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x30: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_SQRT, LD_TMP0_LO, SEQ_NEXT),
            0x31: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_SQRT, LD_TMP0_HI, SEQ_NEXT),
            0x32: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x33: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x34: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x35: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_LOG2 (0x36 - 0x3C) ---
            0x36: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x37: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG2, LD_TMP0_LO, SEQ_NEXT),
            0x38: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG2, LD_TMP0_HI, SEQ_NEXT),
            0x39: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x3A: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x3B: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x3C: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_EXP (0x3D - 0x43) ---
            0x3D: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x3E: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_EXP2, LD_TMP0_LO, SEQ_NEXT),
            0x3F: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_EXP2, LD_TMP0_HI, SEQ_NEXT),
            0x40: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x41: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x42: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x43: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),

            # --- OP_POW (0x44 - 0x56) ---
            0x44: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_TOS, LD_ACC, SEQ_NEXT),
            0x45: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG2, LD_TMP0_LO, SEQ_NEXT),
            0x46: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_LOG2, LD_TMP0_HI, SEQ_NEXT),
            0x47: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_NOS, LD_OPB, SEQ_NEXT),
            0x48: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_NOP, LD_ACC, SEQ_NEXT),
            0x49: (ALU_ADD, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP1, SEQ_NEXT),
            0x4A: (ALU_ABS_DIFF, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0, SEQ_NEXT),
            0x4B: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_ACC, SEQ_NEXT),
            0x4C: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP1_HI, SEQ_NEXT),
            0x4D: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_OPB, SEQ_NEXT),
            0x4E: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP0_HI, SEQ_NEXT),
            0x4F: (ALU_SUB, MUX_TMP1, MUX_TMP0, MEM_NOP, LD_TMP1, SEQ_NEXT),
            0x50: (ALU_SWAP_BYTES, MUX_TMP1, MUX_OPB, MEM_NOP, LD_ACC, SEQ_NEXT),
            0x51: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_EXP2, LD_TMP0_LO, SEQ_NEXT),
            0x52: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_RD_FLASH_EXP2, LD_TMP0_HI, SEQ_NEXT),
            0x53: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x54: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x55: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),
            0x56: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),
        }

    # =========================================================================
    # 4. Shared 16-Bit ALU Primitive
    # =========================================================================
    def _alu_core(self, op, x, y, is_8bit=False):
        cin = self.carry_latch
        limit = 0xFF if is_8bit else 0xFFFF

        if op == ALU_PASS_X:
            res = x
            cout = cin
        elif op == ALU_ADD:
            full = x + y + cin
            res = full & 0xFFFF
            cout = 1 if full > limit else 0
        elif op == ALU_SUB:
            cin_to_use = cin if is_8bit else 0
            full = x - y - cin_to_use
            res = full & 0xFFFF
            cout = 1 if full < 0 else 0
        elif op == ALU_ABS_DIFF:
            res = abs(x - y) & 0xFFFF
            cout = 0
        elif op == ALU_SHL:
            full = x << 1
            res = full & 0xFFFF
            cout = 1 if full > limit else 0
        elif op == ALU_SHR:
            res = (x >> 1) & 0xFFFF
            cout = x & 1
        elif op == ALU_SWAP_BYTES:
            res = ((x >> 8) & 0xFF) | ((x & 0xFF) << 8)
            cout = 0
        elif op == ALU_PASS_ZERO:
            res = 0
            cout = 0
        else:
            res = x
            cout = cin

        self.carry_latch = cout
        sign_mask = 0x80 if is_8bit else 0x8000
        self.flag_zero = ((res & limit) == 0)
        self.flag_sign = bool(res & sign_mask)
        return res

    # =========================================================================
    # 5. Opcode Dispatch Engine
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

        # Format 0x0: 16-Bit Signed Integer (i16)
        if fmt == FMT_I16:
            nos = self.read_nos_i16()
            tos = self.read_tos_i16()
            if op == OP_ADD:
                self.push_nos_i16(nos + tos)
            elif op == OP_SUB:
                self.push_nos_i16(nos - tos)
            elif op == OP_MUL:
                self.push_nos_i16(nos * tos)
            elif op == OP_DIV:
                if tos == 0:
                    self.flag_error = True
                    self.push_nos_i16(0x7FFF)
                else:
                    self.push_nos_i16(int(nos / tos))
            elif op == OP_SQRT:
                if tos < 0:
                    self.flag_error = True
                    self.push_nos_i16(0)
                else:
                    self.push_nos_i16(int(math.sqrt(tos)))
            elif op == OP_CHS:
                self.push_nos_i16(-tos)
            else:
                self.flag_error = True

        # Format 0x1: 32-Bit Signed Integer (i32)
        elif fmt == FMT_I32:
            nos = self.read_nos_i32()
            tos = self.read_tos_i32()
            if op == OP_ADD:
                self.push_nos_i32(nos + tos)
            elif op == OP_SUB:
                self.push_nos_i32(nos - tos)
            elif op == OP_MUL:
                self.push_nos_i32(nos * tos)
            elif op == OP_DIV:
                if tos == 0:
                    self.flag_error = True
                    self.push_nos_i32(0x7FFFFFFF)
                else:
                    self.push_nos_i32(int(nos / tos))
            elif op == OP_SQRT:
                if tos < 0:
                    self.flag_error = True
                    self.push_nos_i32(0)
                else:
                    self.push_nos_i32(int(math.sqrt(tos)))
            elif op == OP_CHS:
                self.push_nos_i32(-tos)
            else:
                self.flag_error = True

        # Format 0x3: 16.16 Fixed Point (fx1616)
        elif fmt == FMT_FX1616:
            nos_f = self.read_nos_fx1616()
            tos_f = self.read_tos_fx1616()
            if op == OP_ADD:
                self.push_nos_fx1616(nos_f + tos_f)
            elif op == OP_SUB:
                self.push_nos_fx1616(nos_f - tos_f)
            elif op == OP_MUL:
                self.push_nos_fx1616(nos_f * tos_f)
            elif op == OP_DIV:
                if tos_f == 0.0:
                    self.flag_error = True
                    self.push_nos_i32(0x7FFFFFFF)
                else:
                    self.push_nos_fx1616(nos_f / tos_f)
            elif op == OP_SQRT:
                if tos_f < 0.0:
                    self.flag_error = True
                    self.push_nos_fx1616(0.0)
                else:
                    self.push_nos_fx1616(math.sqrt(tos_f))
            elif op == OP_CHS:
                self.push_nos_fx1616(-tos_f)
            elif op == OP_SIN:
                self.push_nos_fx1616(math.sin(tos_f))
            elif op == OP_COS:
                self.push_nos_fx1616(math.cos(tos_f))
            elif op == OP_TAN:
                self.push_nos_fx1616(math.tan(tos_f))
            elif op == OP_EXP:
                self.push_nos_fx1616(math.exp(tos_f))
            elif op == OP_LN:
                if tos_f <= 0.0:
                    self.flag_error = True
                    self.push_nos_fx1616(0.0)
                else:
                    self.push_nos_fx1616(math.log(tos_f))
            elif op == OP_LOG10:
                if tos_f <= 0.0:
                    self.flag_error = True
                    self.push_nos_fx1616(0.0)
                else:
                    self.push_nos_fx1616(math.log10(tos_f))
            elif op == OP_POW:
                if tos_f < 0.0:
                    self.flag_error = True
                    self.push_nos_fx1616(0.0)
                else:
                    self.push_nos_fx1616(math.pow(tos_f, nos_f))
            else:
                self.flag_error = True
        else:
            self.flag_error = True

    # Legacy Opcode Name Dispatcher (Maintains backward compatibility)
    def execute_op(self, op_name, max_bytes=4):
        if op_name == 'DIV':
            a = self.sram[self.sp - 8]
            b = self.sram[self.sp - 4]
            if b == 1:
                q = a
            elif b == 0:
                q = 255
            else:
                val = math.ceil(65536.0 / b)
                recip_lo = val & 0xFF
                recip_hi = (val >> 8) & 0xFF
                p1_hi = (a * recip_lo) >> 8
                p2 = a * recip_hi
                q = ((p2 + p1_hi) >> 8) & 0xFF

            self.sram[self.sp - 8] = q
            self.sram[self.sp - 7] = 0
            self.sram[self.sp - 6] = 0
            self.sram[self.sp - 5] = 0
            return

        self.u_pc = self.entry_points[op_name]
        self.byte_cnt = 0
        self.carry_latch = 0
        step_guard = 0

        while self.u_pc in self.urom:
            step_guard += 1
            if step_guard > 200:
                raise RuntimeError(f"Microcode Execution Timeout in {op_name} (u_pc={self.u_pc})")

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
                addr = self.sp - 4 + self.byte_cnt
                mem_data = self.sram[addr]
            elif mem_cmd == MEM_RD_NOS:
                addr = self.sp - 8 + self.byte_cnt
                mem_data = self.sram[addr]
            elif mem_cmd >= MEM_RD_FLASH_QS and mem_cmd <= MEM_RD_FLASH_LOG2:
                base_table = {
                    MEM_RD_FLASH_QS:   FLASH_QS_BASE,
                    MEM_RD_FLASH_REC:  FLASH_RECIP_BASE,
                    MEM_RD_FLASH_SQRT: FLASH_SQRT_BASE,
                    MEM_RD_FLASH_EXP2: FLASH_EXP2_BASE,
                    MEM_RD_FLASH_LOG2: FLASH_LOG2_BASE,
                }[mem_cmd]

                mask = 0x1FF if mem_cmd == MEM_RD_FLASH_QS else 0xFF
                flash_addr = base_table + ((x_val & mask) * 2)
                if reg_ld in (LD_TMP0_HI, LD_TMP1_HI):
                    flash_addr += 1
                mem_data = self.flash[flash_addr]
            elif mem_cmd == MEM_WR_NOS:
                addr = self.sp - 8 + self.byte_cnt
                self.sram[addr] = alu_out & 0xFF
                if seq_ctrl == SEQ_NEXT:
                    self.byte_cnt += 1

            is_mem_rd = (mem_cmd in (MEM_RD_TOS, MEM_RD_NOS) or (mem_cmd >= MEM_RD_FLASH_QS and mem_cmd <= MEM_RD_FLASH_LOG2))

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
                    self.u_pc -= 3
                else:
                    self.u_pc += 1
            elif seq_ctrl == SEQ_DONE:
                self.u_pc = 0
                break

    # =========================================================================
    # 6. Stack Frame Helpers
    # =========================================================================
    def push_nos_bytes(self, data_bytes: list):
        for i, b in enumerate(data_bytes):
            self.sram[self.sp - 8 + i] = b & 0xFF

    def push_tos_bytes(self, data_bytes: list):
        for i, b in enumerate(data_bytes):
            self.sram[self.sp - 4 + i] = b & 0xFF

    def read_nos_bytes(self, count=4) -> list:
        return [self.sram[self.sp - 8 + i] for i in range(count)]

    # 32-bit Integer Helpers
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
        b = self.read_nos_bytes(2)
        u16_val = b[0] | (b[1] << 8)
        return u16_val - 0x10000 if u16_val >= 0x8000 else u16_val

    def read_tos_i16(self) -> int:
        b = [self.sram[self.sp - 4 + i] for i in range(2)]
        u16_val = b[0] | (b[1] << 8)
        return u16_val - 0x10000 if u16_val >= 0x8000 else u16_val

    # 16.16 Fixed-Point Helpers
    def push_nos_fx1616(self, val: float):
        self.push_nos_i32(int(round(val * 65536.0)))

    def push_tos_fx1616(self, val: float):
        self.push_tos_i32(int(round(val * 65536.0)))

    def read_nos_fx1616(self) -> float:
        return self.read_nos_i32() / 65536.0

    def read_tos_fx1616(self) -> float:
        return self.read_tos_i32() / 65536.0

    # Legacy 32-bit uint helpers
    def push_tos(self, val_32: int):
        self.push_tos_i32(val_32)

    def push_nos(self, val_32: int):
        self.push_nos_i32(val_32)

    def read_nos(self) -> int:
        return self.read_nos_i32() & 0xFFFFFFFF


# =============================================================================
# 7. Verification Test Suite
# =============================================================================
def main():
    fpu = ZX50FPUMachine()
    print("=================================================")
    print("=== ZX50 Microcode Simulator Execution Tests ===")
    print("=================================================")

    # Test 1: Addition (0x12345678 + 0x00112233 = 0x124578AB)
    fpu.push_nos(0x12345678)
    fpu.push_tos(0x00112233)
    fpu.execute_op('ADD', max_bytes=4)
    res_add = fpu.read_nos()
    assert res_add == 0x124578AB, f"ADD Failed: {hex(res_add)}"
    print(f"PASS [ADD]:  0x12345678 + 0x00112233 = 0x{res_add:08X}")

    # Test 2: Subtraction (0x00000050 - 0x00000020 = 0x00000030)
    fpu.push_nos(0x00000050)
    fpu.push_tos(0x00000020)
    fpu.execute_op('SUB', max_bytes=4)
    res_sub = fpu.read_nos()
    assert res_sub == 0x00000030, f"SUB Failed: {hex(res_sub)}"
    print(f"PASS [SUB]:  0x00000050 - 0x00000020 = 0x{res_sub:08X}")

    # Test 3: Multiplication (15 * 12 = 180 = 0x00B4)
    fpu.push_nos(15)
    fpu.push_tos(12)
    fpu.execute_op('MUL')
    res_mul = fpu.read_nos() & 0xFFFF
    assert res_mul == 180, f"MUL Failed: {res_mul}"
    print(f"PASS [MUL]:  15 * 12 = {res_mul} (0x{res_mul:04X})")

    # Test 4: Division (100 / 4 = 25)
    fpu.push_nos(100)
    fpu.push_tos(4)
    fpu.execute_op('DIV')
    res_div = fpu.read_nos() & 0xFF
    assert res_div == 25, f"DIV Failed: {res_div}"
    print(f"PASS [DIV]:  100 / 4 = {res_div}")

    # Test 5: i16 Opcode Tests (500 - 200 = 300)
    fpu.push_nos_i16(500)
    fpu.push_tos_i16(200)
    fpu.execute_opcode(0x01) # FMT_I16 | OP_SUB
    assert fpu.read_nos_i16() == 300, f"I16_SUB Failed: {fpu.read_nos_i16()}"
    print(f"PASS [I16_SUB]: 500 - 200 = {fpu.read_nos_i16()}")

    print("\n=================================================")
    print("=== ALL OPERATIONS PASSED SIMULATOR TESTS! ===")
    print("=================================================")

if __name__ == "__main__":
    main()