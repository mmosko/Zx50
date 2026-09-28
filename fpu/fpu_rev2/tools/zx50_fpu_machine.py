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
- Operands in $NOS$ ($a_0..a_3$) and $TOS$ ($b_0..b_3$) must not be overwritten until ALL
  cross-product passes requiring those bytes have finished reading.

Strict CPLD Hardware Rules
- Hardware Register Limits: The CPLD contains only ACC (8-bit), OPB (8-bit), TMP0 (16-bit), TMP1 (16-bit),
  BYTE_CNT (2-bit), and U_PC (7-bit).
- Zero Python Procedural Math: High-level operators (*, //, +, %, procedural for loops) are banned inside
  execute_opcode() or algorithm paths.
- SRAM Scratchpad Offloading: All intermediate partial products, multi-byte carries, and accumulation passes must
  read from and write to reserved SRAM scratchpad bytes (0x0000–0x0007).
"""

#!/usr/bin/env python3
"""
ZX50 FPU Coprocessor Microcode & Datapath Simulator
Simulates the ATF1508AS CPLD micro-engine, private SRAM/Flash, and ALU.
Executes operations exclusively via microcode step sequences and Flash ROM LUTs.
"""

import logging

logger = logging.getLogger("ZX50_FPU")

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
from fpu_sim_alu import (
    alu_core,
    MUX_ACC,
    MUX_OPB,
    MUX_TMP0,
    MUX_TMP1,
    MEM_NOP,
    MEM_RD_TOS,
    MEM_RD_NOS,
    MEM_RD_FLASH_QS,
    MEM_RD_FLASH_REC,
    MEM_RD_FLASH_SQRT,
    MEM_RD_FLASH_EXP2,
    MEM_RD_FLASH_LOG2,
    MEM_RD_FLASH_SIN,
    MEM_RD_FLASH_COS,
    MEM_RD_FLASH_TAN,
    MEM_RD_FLASH_LN,
    MEM_RD_FLASH_LOG10,
    MEM_WR_NOS,
    MEM_WR_TOS,
    LD_NONE,
    LD_ACC,
    LD_OPB,
    LD_TMP0,
    LD_TMP1,
    LD_TMP0_LO,
    LD_TMP0_HI,
    LD_TMP1_LO,
    LD_TMP1_HI,
    SEQ_NEXT,
    SEQ_LOOP,
    SEQ_DONE,
    FMT_I32,
    FMT_FX1616,
    FMT_MGMT,
    OP_ADD,
    OP_SUB,
    OP_MUL,
    OP_DIV,
    OP_SQRT,
    OP_CHS,
    OP_SIN,
    OP_COS,
    OP_EXP,
    OP_LN,
    OP_LOG10,
    OP_TAN,
    OP_POW,
    MGMT_CLR_STK,
    MGMT_POP_TOS,
    MGMT_DUP_TOS,
    MGMT_RESET,
    MEM_RD_SCRATCH,
    MEM_WR_SCRATCH,
)
from fpu_sim_microcode import ENTRY_POINTS, UROM


class ZX50FPUMachine:

    def __init__(self, debug: bool = False):
        self.sram = bytearray(32768)
        self.flash = bytearray(32768)

        self.acc = 0
        self.opb = 0
        self.tmp0 = 0
        self.tmp1 = 0
        self.sp = 0x10
        self.byte_cnt = 0
        self.u_pc = 0

        self.flag_zero = False
        self.flag_sign = False
        self.flag_carry = False
        self.flag_error = False
        self.carry_latch = 0

        self._init_flash_tables()
        self.entry_points = ENTRY_POINTS
        self.urom = UROM

        if debug:
            logging.basicConfig(level=logging.DEBUG)

    def _init_flash_tables(self):
        populate_flash_memory(self.flash)

    def run_microcode(self, entry_u_pc):
        max_bytes = 4
        self.u_pc = entry_u_pc
        self.byte_cnt = 0
        self.carry_latch = 0
        step_guard = 0
        prev_mem_cmd = MEM_NOP

        logger.debug(
            f"--- [MICROCODE START] Entry u_pc: {entry_u_pc} (SP: 0x{self.sp:02X}) ---"
        )

        while self.u_pc in self.urom:
            step_guard += 1
            if step_guard > 300:
                logger.error(
                    f"[MICROCODE TIMEOUT] u_pc={self.u_pc} reached 300 steps"
                )
                raise RuntimeError(
                    f"Microcode Execution Timeout (u_pc={self.u_pc})"
                )

            alu_op, src_x, src_y, mem_cmd, reg_ld, seq_ctrl = self.urom[
                self.u_pc
            ]
            is_8bit = (src_x in (MUX_ACC, MUX_OPB)) and (
                src_y in (MUX_ACC, MUX_OPB)
            )

            old_acc = self.acc
            old_opb = self.opb
            old_tmp0 = self.tmp0
            old_tmp1 = self.tmp1
            old_carry = self.carry_latch

            # MEM_NOP does not reset memory target sequence
            if mem_cmd != MEM_NOP:
                if mem_cmd != prev_mem_cmd:
                    self.byte_cnt = 0
                    prev_mem_cmd = mem_cmd

            x_val = (
                self.acc
                if src_x == MUX_ACC
                else (
                    self.opb
                    if src_x == MUX_OPB
                    else (self.tmp0 if src_x == MUX_TMP0 else self.tmp1)
                )
            )

            y_val = (
                self.acc
                if src_y == MUX_ACC
                else (
                    self.opb
                    if src_y == MUX_OPB
                    else (self.tmp0 if src_y == MUX_TMP0 else self.tmp1)
                )
            )

            alu_out, self.carry_latch, self.flag_zero, self.flag_sign = (
                alu_core(
                    alu_op, x_val, y_val, self.carry_latch, is_8bit=is_8bit
                )
            )

            mem_data = 0
            if mem_cmd == MEM_RD_TOS:
                addr = self.sp - 4 + self.byte_cnt
                mem_data = self.sram[addr]
                logger.debug(
                    f"  [SRAM RD TOS] Addr: 0x{addr:04X} -> Val: 0x{mem_data:02X} (byte_cnt={self.byte_cnt})"
                )
                self.byte_cnt += 1
            elif mem_cmd == MEM_RD_NOS:
                addr = self.sp - 8 + self.byte_cnt
                mem_data = self.sram[addr]
                logger.debug(
                    f"  [SRAM RD NOS] Addr: 0x{addr:04X} -> Val: 0x{mem_data:02X} (byte_cnt={self.byte_cnt})"
                )
                self.byte_cnt += 1
            elif mem_cmd == MEM_RD_SCRATCH:
                addr = 0x0000 + self.byte_cnt
                mem_data = self.sram[addr]
                logger.debug(
                    f"  [SRAM RD SCRATCH] Addr: 0x{addr:04X} -> Val: 0x{mem_data:02X} (byte_cnt={self.byte_cnt})"
                )
                self.byte_cnt += 1
            elif MEM_RD_FLASH_QS <= mem_cmd <= MEM_RD_FLASH_LOG10:
                base_table = {
                    MEM_RD_FLASH_QS: FLASH_QS_BASE,
                    MEM_RD_FLASH_REC: FLASH_RECIP_BASE,
                    MEM_RD_FLASH_SQRT: FLASH_SQRT_BASE,
                    MEM_RD_FLASH_EXP2: FLASH_EXP2_BASE,
                    MEM_RD_FLASH_LOG2: FLASH_LOG2_BASE,
                    MEM_RD_FLASH_SIN: FLASH_SIN_BASE,
                    MEM_RD_FLASH_COS: FLASH_COS_BASE,
                    MEM_RD_FLASH_TAN: FLASH_TAN_BASE,
                    MEM_RD_FLASH_LN: FLASH_LN_BASE,
                    MEM_RD_FLASH_LOG10: FLASH_LOG10_BASE,
                }[mem_cmd]

                mask = 0x1FF if mem_cmd == MEM_RD_FLASH_QS else 0xFF
                flash_addr = base_table + ((x_val & mask) * 2)
                if reg_ld in (LD_TMP0_HI, LD_TMP1_HI):
                    flash_addr += 1
                mem_data = self.flash[flash_addr]
                logger.debug(
                    f"  [FLASH RD] Addr: 0x{flash_addr:04X} -> Val: 0x{mem_data:02X}"
                )
            elif mem_cmd == MEM_WR_NOS:
                addr = self.sp - 8 + self.byte_cnt
                val = alu_out & 0xFF
                self.sram[addr] = val
                logger.debug(
                    f"  [SRAM WR NOS] Addr: 0x{addr:04X} <- Val: 0x{val:02X} (byte_cnt={self.byte_cnt})"
                )
                self.byte_cnt += 1
            elif mem_cmd == MEM_WR_TOS:
                addr = self.sp - 4 + self.byte_cnt
                val = alu_out & 0xFF
                self.sram[addr] = val
                logger.debug(
                    f"  [SRAM WR TOS] Addr: 0x{addr:04X} <- Val: 0x{val:02X} (byte_cnt={self.byte_cnt})"
                )
                self.byte_cnt += 1
            elif mem_cmd == MEM_WR_SCRATCH:
                addr = 0x0000 + self.byte_cnt
                val = alu_out & 0xFF
                self.sram[addr] = val
                logger.debug(
                    f"  [SRAM WR SCRATCH] Addr: 0x{addr:04X} <- Val: 0x{val:02X} (byte_cnt={self.byte_cnt})"
                )
                self.byte_cnt += 1

            is_mem_rd = mem_cmd in (
                MEM_RD_TOS,
                MEM_RD_NOS,
                MEM_RD_SCRATCH,
            ) or (MEM_RD_FLASH_QS <= mem_cmd <= MEM_RD_FLASH_LOG10)

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

            if self.acc != old_acc:
                logger.debug(
                    f"  [REG CHANGE] ACC: 0x{old_acc:02X} -> 0x{self.acc:02X}"
                )
            if self.opb != old_opb:
                logger.debug(
                    f"  [REG CHANGE] OPB: 0x{old_opb:02X} -> 0x{self.opb:02X}"
                )
            if self.tmp0 != old_tmp0:
                logger.debug(
                    f"  [REG CHANGE] TMP0: 0x{old_tmp0:04X} -> 0x{self.tmp0:04X}"
                )
            if self.tmp1 != old_tmp1:
                logger.debug(
                    f"  [REG CHANGE] TMP1: 0x{old_tmp1:04X} -> 0x{self.tmp1:04X}"
                )
            if self.carry_latch != old_carry:
                logger.debug(
                    f"  [FLAG CHANGE] CARRY: {old_carry} -> {self.carry_latch}"
                )

            if seq_ctrl == SEQ_NEXT:
                self.u_pc += 1
            elif seq_ctrl == SEQ_DONE:
                logger.debug(
                    f"--- [MICROCODE END] Operation Complete at u_pc: {self.u_pc} ---"
                )
                self.u_pc = 0
                break

    def execute_opcode(self, opcode: int):
        self.flag_error = False
        fmt = (opcode >> 4) & 0x0F
        op = opcode & 0x0F

        logger.debug(
            f"=== [EXECUTE OPCODE] Opcode: 0x{opcode:02X} (FMT: 0x{fmt:X}, OP: 0x{op:X}) ==="
        )

        if fmt == FMT_MGMT:
            if opcode in (MGMT_CLR_STK, MGMT_RESET):
                self.sp = 0x08
            elif opcode == MGMT_POP_TOS:
                self.sp = max(0x08, self.sp - 4)
            elif opcode == MGMT_DUP_TOS:
                tos_bytes = self.read_tos_bytes()
                self.sp += 4
                self.push_tos_bytes(tos_bytes)
            else:
                self.flag_error = True
            logger.debug(f"=== [MGMT OPCODE EXECUTED] SP: 0x{self.sp:02X} ===")
            return

        if fmt not in (FMT_I32, FMT_FX1616):
            logger.error(f"[OPCODE ERROR] Invalid format: 0x{fmt:X}")
            self.flag_error = True
            return

        if op == OP_DIV:
            if all(self.sram[self.sp - 4 + i] == 0 for i in range(4)):
                logger.warning("[OPCODE DIV] Zero division detected on TOS")
                self.flag_error = True
                self.sram[self.sp - 8 + 3] = 0x7F
                for i in range(3):
                    self.sram[self.sp - 8 + i] = 0xFF
                return

        elif op in (OP_SQRT, OP_LN, OP_LOG10, OP_POW):
            msb_byte = self.sram[self.sp - 4 + 3]
            tos_zero = all(self.sram[self.sp - 4 + i] == 0 for i in range(4))
            if (msb_byte & 0x80) or (op in (OP_LN, OP_LOG10) and tos_zero):
                logger.warning(
                    f"[OPCODE GUARD] Domain error on OP 0x{op:X} (TOS MSB: 0x{msb_byte:02X})"
                )
                self.flag_error = True
                for i in range(4):
                    self.sram[self.sp - 8 + i] = 0x00
                return

        entry_point = self._map_op_to_entry(op, is_int=(fmt == FMT_I32))

        if entry_point is not None:
            self.run_microcode(entry_point)

            BINARY_OPS = (OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_POW)
            if op in BINARY_OPS:
                self.sp = max(0x08, self.sp - 4)
                logger.debug(
                    f"=== [OPCODE COMPLETE] SP adjusted to 0x{self.sp:02X} ==="
                )
        else:
            logger.error(
                f"[OPCODE ERROR] No microcode entry point mapped for OP: 0x{op:X}"
            )
            self.flag_error = True

    def _map_op_to_entry(self, op, is_int=False):
        if op == OP_SQRT:
            return (
                self.entry_points["SQRT_INT"]
                if is_int
                else self.entry_points["SQRT_FX"]
            )

        mapping = {
            OP_ADD: self.entry_points["ADD"],
            OP_SUB: self.entry_points["SUB"],
            OP_MUL: self.entry_points["MUL"],
            OP_DIV: self.entry_points["DIV"],
            OP_CHS: self.entry_points["CHS"],
            OP_SIN: self.entry_points["SIN"],
            OP_COS: self.entry_points["COS"],
            OP_TAN: self.entry_points["TAN"],
            OP_EXP: self.entry_points["EXP"],
            OP_LN: self.entry_points["LN"],
            OP_LOG10: self.entry_points["LOG10"],
            OP_POW: self.entry_points["POW"],
        }
        return mapping.get(op, None)

    def push_nos_bytes(self, data_bytes: list):
        for i in range(4):
            self.sram[self.sp - 8 + i] = data_bytes[i] & 0xFF

    def push_tos_bytes(self, data_bytes: list):
        for i in range(4):
            self.sram[self.sp - 4 + i] = data_bytes[i] & 0xFF

    def read_nos_bytes(self) -> list:
        return [self.sram[self.sp - 8 + i] for i in range(4)]

    def read_tos_bytes(self) -> list:
        return [self.sram[self.sp - 4 + i] for i in range(4)]

    def push_nos_i32(self, val: int):
        u32_val = val & 0xFFFFFFFF
        self.push_nos_bytes([(u32_val >> (i * 8)) & 0xFF for i in range(4)])

    def push_tos_i32(self, val: int):
        u32_val = val & 0xFFFFFFFF
        self.push_tos_bytes([(u32_val >> (i * 8)) & 0xFF for i in range(4)])

    def read_nos_i32(self) -> int:
        b = self.read_nos_bytes()
        u32_val = b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)
        return u32_val - 0x100000000 if u32_val >= 0x80000000 else u32_val

    def read_tos_i32(self) -> int:
        b = self.read_tos_bytes()
        u32_val = b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)
        return u32_val - 0x100000000 if u32_val >= 0x80000000 else u32_val

    def push_nos_fx1616(self, val: float):
        self.push_nos_i32(int(round(val * 65536.0)))

    def push_tos_fx1616(self, val: float):
        self.push_tos_i32(int(round(val * 65536.0)))

    def read_nos_fx1616(self) -> float:
        return self.read_nos_i32() / 65536.0

    def read_tos_fx1616(self) -> float:
        return self.read_tos_i32() / 65536.0

