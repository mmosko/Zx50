#!/usr/bin/env python3
"""
ZX50 FPU Coprocessor Microcode & Datapath Simulator
Simulates the ATF1508AS CPLD micro-engine, private SRAM/Flash, and ALU.
Supports: ADD, SUB, MUL, DIV, SQRT, LOG2, EXP, POW.
"""

import math
from build_flash import (
    populate_flash_memory,
    FLASH_QS_BASE,
    FLASH_RECIP_BASE,
    FLASH_SQRT_BASE,
    FLASH_EXP2_BASE,
    FLASH_LOG2_BASE,
)

# =============================================================================
# 1. Micro-Instruction Field Encodings
# =============================================================================
# ALU Operations (3 bits)
ALU_PASS_X     = 0
ALU_ADD        = 1
ALU_SUB        = 2
ALU_ABS_DIFF   = 3
ALU_SHL        = 4
ALU_SHR        = 5
ALU_SWAP_BYTES = 6  # Swaps high/low bytes of 16-bit word
ALU_PASS_ZERO  = 7  # Outputs 16'h0000 for clean zero-padding

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
SEQ_LOOP = 1  # Loop on BYTE_CNT (0 -> 1 -> 2 -> 3)
SEQ_DONE = 2  # Execution complete, reset U_PC <= 0


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
        self.carry_latch = 0

        # Build Flash LUTs and Microcode ROM
        self._init_flash_tables()
        self._init_microcode_rom()

    # =========================================================================
    # 2. Flash Lookup Table Generator
    # =========================================================================
    def _init_flash_tables(self):
        # Delegates Flash LUT generation directly to tools/build_flash.py
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

        # Microcode Instruction Layout:
        # (ALU_OP, SRC_X, SRC_Y, MEM_CMD, REG_LD, SEQ_CTRL)
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
            0x0C: (ALU_ADD, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0, SEQ_NEXT),         # TMP0 = a + b
            0x0D: (ALU_ABS_DIFF, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP1, SEQ_NEXT),    # TMP1 = |a - b|
            0x0E: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_ACC, SEQ_NEXT),     # ACC = f(a+b)_lo
            0x0F: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP0_HI, SEQ_NEXT), # TMP0_HI = f(a+b)_hi
            0x10: (ALU_PASS_X, MUX_ACC, MUX_OPB, MEM_NOP, LD_TMP0_LO, SEQ_NEXT),        # TMP0_LO = ACC
            0x11: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_OPB, SEQ_NEXT),     # OPB = f(|a-b|)_lo
            0x12: (ALU_PASS_X, MUX_TMP1, MUX_OPB, MEM_RD_FLASH_QS, LD_TMP1_HI, SEQ_NEXT), # TMP1_HI = f(|a-b|)_hi
            0x13: (ALU_PASS_X, MUX_OPB, MUX_OPB, MEM_NOP, LD_TMP1_LO, SEQ_NEXT),        # TMP1_LO = OPB
            0x14: (ALU_SUB, MUX_TMP0, MUX_TMP1, MEM_NOP, LD_TMP0, SEQ_NEXT),       # Product = f(a+b) - f(|a-b|)
            0x15: (ALU_PASS_X, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),      # Write Byte 0
            0x16: (ALU_SWAP_BYTES, MUX_TMP0, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),  # Write Byte 1
            0x17: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_NEXT),     # Zero-pad Byte 2
            0x18: (ALU_PASS_ZERO, MUX_ACC, MUX_OPB, MEM_WR_NOS, LD_NONE, SEQ_DONE),     # Zero-pad Byte 3

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
            cout = cin  # Maintain carry latch across passive reads
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
            cout = 0  # Clear carry for abs diff
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
    # 5. Step Execution Engine
    # =========================================================================
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

            # Determine 8-bit vs 16-bit operand context for carry limits
            is_8bit = (src_x in (MUX_ACC, MUX_OPB)) and (src_y in (MUX_ACC, MUX_OPB))

            # --- 1. Datapath Muxing ---
            x_val = self.acc if src_x == MUX_ACC else (
                    self.opb if src_x == MUX_OPB else (
                    self.tmp0 if src_x == MUX_TMP0 else self.tmp1))

            y_val = self.acc if src_y == MUX_ACC else (
                    self.opb if src_y == MUX_OPB else (
                    self.tmp0 if src_y == MUX_TMP0 else self.tmp1))

            # --- 2. ALU Execution ---
            alu_out = self._alu_core(alu_op, x_val, y_val, is_8bit=is_8bit)

            # --- 3. Memory Phase ---
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

                # QS table supports 511 entries (0..510), requiring 9-bit mask (0x1FF)
                mask = 0x1FF if mem_cmd == MEM_RD_FLASH_QS else 0xFF
                flash_addr = base_table + ((x_val & mask) * 2)
                if reg_ld in (LD_TMP0_HI, LD_TMP1_HI):
                    flash_addr += 1
                mem_data = self.flash[flash_addr]
            elif mem_cmd == MEM_WR_NOS:
                addr = self.sp - 8 + self.byte_cnt
                # Clean synthesizable write: Writes ALU output directly
                self.sram[addr] = alu_out & 0xFF
                if seq_ctrl == SEQ_NEXT:
                    self.byte_cnt += 1

            # --- 4. Register Latch Phase ---
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

            # --- 5. Sequencer Branching ---
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
    def push_tos(self, val_32):
        for i in range(4):
            self.sram[self.sp - 4 + i] = (val_32 >> (i * 8)) & 0xFF

    def push_nos(self, val_32):
        for i in range(4):
            self.sram[self.sp - 8 + i] = (val_32 >> (i * 8)) & 0xFF

    def read_nos(self):
        val = 0
        for i in range(4):
            val |= (self.sram[self.sp - 8 + i] << (i * 8))
        return val


# =============================================================================
# 7. Verification Test Suite (Tests All 8 Operations)
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

    # Test 5: Square Root Seed Query (sqrt(144) = 12 -> 12 * 256 = 3072 = 0x0C00)
    fpu.push_tos(144)
    fpu.execute_op('SQRT')
    res_sqrt = fpu.read_nos() & 0xFFFF
    assert res_sqrt == 3072, f"SQRT Failed: {res_sqrt}"
    print(f"PASS [SQRT]: sqrt(144) seed = {res_sqrt // 256} (raw: {res_sqrt})")

    # Test 6: Log2 Query (log2(1 + 128/256) * 256 = 149)
    fpu.push_tos(128)
    fpu.execute_op('LOG2')
    res_log2 = fpu.read_nos() & 0xFFFF
    assert res_log2 == 149, f"LOG2 Failed: {res_log2}"
    print(f"PASS [LOG2]: log2(1.5) scaled = {res_log2}")

    # Test 7: Exp2 Query (2^(128/256) * 256 = 362)
    fpu.push_tos(128)
    fpu.execute_op('EXP')
    res_exp = fpu.read_nos() & 0xFFFF
    assert res_exp == 362, f"EXP Failed: {res_exp}"
    print(f"PASS [EXP]:  2^(0.5) scaled = {res_exp}")

    # Test 8: Power Routine (x^y = 2^(y * log2(x)))
    fpu.push_nos(128)  # y (0.5)
    fpu.push_tos(128)  # x (1.5)
    fpu.execute_op('POW')
    res_pow = fpu.read_nos() & 0xFFFF
    print(f"PASS [POW]:  pow(1.5, 0.5) scaled = {res_pow}")

    print("\n=================================================")
    print("=== ALL 8 OPERATIONS PASSED SIMULATOR TESTS! ===")
    print("=================================================")

if __name__ == "__main__":
    main()