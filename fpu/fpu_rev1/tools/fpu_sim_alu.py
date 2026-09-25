#!/usr/bin/env python3
"""
tools/fpu_sim_alu.py
ZX50 FPU Shared 16-Bit Combinational ALU & Field Encodings
Defines datapath muxes, register load enables, memory commands, opcodes,
and the hardware ALU primitive (`alu_core`).
"""

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
# - Function: OUT = (X << 1) | carry_latch
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


# =============================================================================
# 2. Shared 16-Bit Combinational ALU Primitive (Gate-Level Model)
# =============================================================================
def alu_core(op, x, y, carry_in, is_8bit=False):
    """
    Models the 16-bit combinational ALU block synthesized inside CPLD macrocells.
    Returns (res_out, carry_out, flag_zero, flag_sign).
    """
    limit = 0xFF if is_8bit else 0xFFFF

    if op == ALU_PASS_X:
        res = x
        cout = carry_in
    elif op == ALU_ADD:
        full = x + y + carry_in
        res = full & 0xFFFF
        cout = 1 if full > limit else 0
    elif op == ALU_SUB:
        cin_to_use = carry_in if is_8bit else 0
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
        cout = carry_in

    flag_zero = ((res & limit) == 0)
    sign_mask = 0x80 if is_8bit else 0x8000
    flag_sign = bool(res & sign_mask)

    return res, cout, flag_zero, flag_sign
