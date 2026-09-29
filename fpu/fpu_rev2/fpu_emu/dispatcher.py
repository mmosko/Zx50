"""Command Dispatcher and Micro-sequencer execution engine."""

from typing import List
from fpu_emu.alu.alu import Alu
from fpu_emu.hardware import Hardware
from fpu_emu.memory import stack
from fpu_emu.memory.ram import CMD_STACK_BASE, CMD_STACK_SIZE
from fpu_emu.memory.registers import StatusFlag, Reg
from fpu_emu.micro_code import MicroCode
from fpu_emu.micro_opcodes import MicroOp, MicroInstruction
from fpu_emu.user_opcodes import UserOpcode


class Dispatcher:
    """Dispatches user opcodes and executes microcode instruction streams."""

    def __init__(self, hw: Hardware, alu: Alu):
        self._hw = hw
        self._alu = alu
        self._batch_mode: bool = False
        self._blocking_mode: bool = True
        self._sqrt_is_odd: bool = False

    @property
    def batch_mode(self) -> bool:
        """Returns True if FPU is in BATCH execution mode."""
        return self._batch_mode

    @property
    def blocking_mode(self) -> bool:
        """Returns True if FPU asserts ~BWAIT on busy (blocking mode)."""
        return self._blocking_mode

    @property
    def bwait_n(self) -> bool:
        """Active-low ~BWAIT line to host CPU: 0 (False) = hold CPU, 1 (True) = ready."""
        is_busy = self._hw.reg.get_flag(StatusFlag.BUSY)
        # BWAIT_N is driven low (0) when BLOCKING and BUSY
        return not (self._blocking_mode and is_busy)

    def execute(self, user_opcode: UserOpcode):
        """Executes a user opcode or enqueues it if in batch mode.

        :param user_opcode: UserOpcode command to execute.
        """
        # 1-cycle command dispatch overhead
        self._hw.clock.tick(1)

        # Handle mode & control commands directly
        if user_opcode == UserOpcode.SET_BATCH:
            self._batch_mode = True
            return
        elif user_opcode == UserOpcode.SET_IMMEDIATE:
            self._batch_mode = False
            return
        elif user_opcode == UserOpcode.SET_BLOCKING:
            self._blocking_mode = True
            return
        elif user_opcode == UserOpcode.SET_NONBLOCKING:
            self._blocking_mode = False
            return
        elif user_opcode == UserOpcode.CLEAR_STACK:
            self._hw.reg.sp = 0
            return
        elif user_opcode == UserOpcode.RESET:
            self._hw.reset()
            self._batch_mode = False
            self._blocking_mode = True
            return
        elif user_opcode == UserOpcode.EXEC_BATCH:
            self._execute_batch()
            return

        # If in batch mode, enqueue into command queue
        if self._batch_mode:
            self._enqueue_command(user_opcode)
            return

        # Immediate computational execution
        self._execute_immediate(user_opcode)

    def _execute_immediate(self, user_opcode: UserOpcode):
        """Executes a single computational opcode immediately with BUSY management."""
        self._hw.reg.set_flag(StatusFlag.BUSY, True)
        try:
            ucode = MicroCode.get(user_opcode)
            self._run(ucode)
        finally:
            self._hw.reg.set_flag(StatusFlag.BUSY, False)

    def _execute_batch(self):
        """Executes all queued commands in RAM sequentially with BUSY held high."""
        self._hw.reg.set_flag(StatusFlag.BUSY, True)
        try:
            osp = self._hw.reg.osp
            for i in range(osp):
                opcode_val = self._hw.mem[CMD_STACK_BASE + i]
                try:
                    opcode = UserOpcode(opcode_val)
                    ucode = MicroCode.get(opcode)
                    self._run(ucode)
                    # Halt batch early if error occurred
                    if self._hw.reg.get_flag(StatusFlag.ERR):
                        break
                except (ValueError, NotImplementedError):
                    self._hw.reg.set_flag(StatusFlag.ERR, True)
                    break
            # Reset command queue pointer
            self._hw.reg.osp = 0
        finally:
            self._hw.reg.set_flag(StatusFlag.BUSY, False)

    def _enqueue_command(self, user_opcode: UserOpcode):
        """Enqueues a user opcode into SysMEM command queue (0x0340..0x035F)."""
        self._hw.clock.tick(1)
        osp = self._hw.reg.osp
        if osp >= CMD_STACK_SIZE:
            self._hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            self._hw.reg.set_flag(StatusFlag.ERR, True)
            return

        self._hw.mem[CMD_STACK_BASE + osp] = user_opcode.value
        self._hw.reg.osp = osp + 1

    def _run(self, microcode: List[MicroInstruction]):
        """Micro-sequencer execution loop.

        Fetches each micro-instruction (1 tick), then executes it.
        """
        pc = 0
        while pc < len(microcode):
            # 1 cycle micro-instruction fetch
            self._hw.clock.tick(1)
            inst = microcode[pc]
            pc += 1

            match inst.op:
                case MicroOp.POP:
                    if inst.dst is not None:
                        stack.pop32(self._hw, inst.dst)
                case MicroOp.PUSH:
                    if inst.src is not None:
                        stack.push32(self._hw, inst.src)
                case MicroOp.POP64:
                    if inst.dst is not None:
                        stack.pop64(self._hw, inst.dst)
                case MicroOp.PUSH64:
                    if inst.src is not None:
                        stack.push64(self._hw, inst.src)
                case MicroOp.ADD:
                    if inst.src is not None:
                        self._alu.add32(inst.src)
                case MicroOp.ADC:
                    if inst.src is not None:
                        self._alu.adc32(inst.src)
                case MicroOp.SUB:
                    if inst.src is not None:
                        self._alu.sub32(inst.src)
                case MicroOp.SBB:
                    if inst.src is not None:
                        self._alu.sbb32(inst.src)
                case MicroOp.CMP:
                    if inst.src is not None:
                        self._alu.cmp32(inst.src)
                case MicroOp.ADD64:
                    if inst.src is not None:
                        self._alu.add64(inst.src)
                case MicroOp.ADC64:
                    if inst.src is not None:
                        self._alu.adc64(inst.src)
                case MicroOp.SUB64:
                    if inst.src is not None:
                        self._alu.sub64(inst.src)
                case MicroOp.SBB64:
                    if inst.src is not None:
                        self._alu.sbb64(inst.src)
                case MicroOp.CMP64:
                    if inst.src is not None:
                        self._alu.cmp64(inst.src)
                case MicroOp.LSL:
                    reg = inst.dst if inst.dst is not None else Reg.AL
                    self._alu.lsl32(shift=inst.imm if inst.imm else None, reg=reg)
                case MicroOp.LSR:
                    reg = inst.dst if inst.dst is not None else Reg.AL
                    self._alu.lsr32(shift=inst.imm if inst.imm else None, reg=reg)
                case MicroOp.ASR:
                    reg = inst.dst if inst.dst is not None else Reg.AL
                    self._alu.asr32(shift=inst.imm if inst.imm else None, reg=reg)
                case MicroOp.RRC:
                    reg = inst.dst if inst.dst is not None else Reg.AL
                    if reg in (Reg.AX, Reg.BX, Reg.DX, Reg.FX):
                        self._alu.rrc64(reg=reg)
                    else:
                        self._alu.rrc32(reg=reg)
                case MicroOp.RRC64:
                    reg = inst.dst if inst.dst is not None else Reg.AX
                    self._alu.rrc64(reg=reg)
                case MicroOp.LSL64:
                    reg = inst.dst if inst.dst is not None else Reg.AX
                    self._alu.lsl64(shift=inst.imm if inst.imm else None, reg=reg)
                case MicroOp.LSR64:
                    reg = inst.dst if inst.dst is not None else Reg.AX
                    self._alu.lsr64(shift=inst.imm if inst.imm else None, reg=reg)
                case MicroOp.ASR64:
                    reg = inst.dst if inst.dst is not None else Reg.AX
                    self._alu.asr64(shift=inst.imm if inst.imm else None, reg=reg)
                case MicroOp.LZC:
                    reg = inst.src if inst.src is not None else Reg.AL
                    self._alu.lzc32(reg=reg)
                case MicroOp.LZC64:
                    reg = inst.src if inst.src is not None else Reg.AX
                    self._alu.lzc64(reg=reg)
                case MicroOp.AND:
                    if inst.src is not None:
                        dst = inst.dst if inst.dst is not None else Reg.AL
                        self._alu.and32(inst.src, dst=dst)
                case MicroOp.OR:
                    if inst.src is not None:
                        dst = inst.dst if inst.dst is not None else Reg.AL
                        self._alu.or32(inst.src, dst=dst)
                case MicroOp.XOR:
                    if inst.src is not None:
                        dst = inst.dst if inst.dst is not None else Reg.AL
                        self._alu.xor32(inst.src, dst=dst)
                case MicroOp.NOT:
                    dst = inst.dst if inst.dst is not None else Reg.AL
                    self._alu.not32(dst=dst)
                case MicroOp.AND64:
                    if inst.src is not None:
                        dst = inst.dst if inst.dst is not None else Reg.AX
                        self._alu.and64(inst.src, dst=dst)
                case MicroOp.OR64:
                    if inst.src is not None:
                        dst = inst.dst if inst.dst is not None else Reg.AX
                        self._alu.or64(inst.src, dst=dst)
                case MicroOp.XOR64:
                    if inst.src is not None:
                        dst = inst.dst if inst.dst is not None else Reg.AX
                        self._alu.xor64(inst.src, dst=dst)
                case MicroOp.NOT64:
                    dst = inst.dst if inst.dst is not None else Reg.AX
                    self._alu.not64(dst=dst)
                case MicroOp.CHS:
                    reg = inst.dst if inst.dst is not None else Reg.AH
                    self._alu.chs(reg=reg)
                case MicroOp.ABS:
                    reg = inst.dst if inst.dst is not None else Reg.AH
                    self._alu.abs_val(reg=reg)
                case MicroOp.MUL:
                    src = inst.src if inst.src is not None else Reg.BL
                    self._alu.mul32(src=src)
                case MicroOp.MUL64:
                    src = inst.src if inst.src is not None else Reg.BX
                    self._alu.mul64(src=src)
                case MicroOp.EXP_ADD:
                    self._alu.exp_add()
                case MicroOp.EXP_SUB:
                    self._alu.exp_sub()
                case MicroOp.EXP_DIFF:
                    reg = inst.src if inst.src is not None else (inst.dst if inst.dst is not None else Reg.AL)
                    self._alu.exp_diff(reg=reg)
                case MicroOp.EXP_NORM:
                    self._alu.exp_adj_norm()
                case MicroOp.EXP_INC:
                    self._alu.exp_inc()
                case MicroOp.EXP_DEC:
                    self._alu.exp_dec()
                case MicroOp.UNPACK_F32:
                    src = inst.src if inst.src is not None else Reg.AL
                    dst_exp = inst.dst if inst.dst is not None else Reg.EA
                    self._alu.unpack_f32(src=src, dst_mantissa=src, dst_exp=dst_exp)
                case MicroOp.PACK_F32:
                    dst = inst.dst if inst.dst is not None else Reg.AL
                    src_exp = inst.src if inst.src is not None else Reg.EA
                    self._alu.pack_f32(src_mantissa=dst, src_exp=src_exp, dst=dst)
                case MicroOp.UNPACK_F64:
                    src = inst.src if inst.src is not None else Reg.AX
                    dst_exp = inst.dst if inst.dst is not None else Reg.EA
                    self._alu.unpack_f64(src=src, dst_mantissa=src, dst_exp=dst_exp)
                case MicroOp.PACK_F64:
                    dst = inst.dst if inst.dst is not None else Reg.AX
                    src_exp = inst.src if inst.src is not None else Reg.EA
                    self._alu.pack_f64(src_mantissa=dst, src_exp=src_exp, dst=dst)
                case MicroOp.SQRT_EXP:
                    exp_reg = inst.dst if inst.dst is not None else Reg.EA
                    self._sqrt_is_odd = self._alu.sqrt_exp32(exp_reg=exp_reg)
                case MicroOp.SQRT_CORE:
                    dst = inst.dst if inst.dst is not None else Reg.AL
                    self._alu.sqrt_core32(is_odd=self._sqrt_is_odd, dst=dst)
                case MicroOp.SQRT_EXP64:
                    exp_reg = inst.dst if inst.dst is not None else Reg.EA
                    self._sqrt_is_odd = self._alu.sqrt_exp64(exp_reg=exp_reg)
                case MicroOp.SQRT_CORE64:
                    dst = inst.dst if inst.dst is not None else Reg.AX
                    self._alu.sqrt_core64(is_odd=self._sqrt_is_odd, dst=dst)
                case MicroOp.ABS_INT:
                    reg = inst.dst if inst.dst is not None else Reg.AL
                    self._alu.abs_int32(reg=reg)
                case MicroOp.ABS_INT64:
                    reg = inst.dst if inst.dst is not None else Reg.AX
                    self._alu.abs_int64(reg=reg)
                case MicroOp.MUL_F32:
                    dst = inst.dst if inst.dst is not None else Reg.AL
                    src = inst.src if inst.src is not None else Reg.BL
                    self._alu.mul_f32(dst=dst, src=src)
                case MicroOp.DIV_F32:
                    dst = inst.dst if inst.dst is not None else Reg.AL
                    src = inst.src if inst.src is not None else Reg.BL
                    self._alu.div_f32(dst=dst, src=src)
                case MicroOp.MUL_F64:
                    dst = inst.dst if inst.dst is not None else Reg.AX
                    src = inst.src if inst.src is not None else Reg.BX
                    self._alu.mul_f64(dst=dst, src=src)
                case MicroOp.DIV_F64:
                    dst = inst.dst if inst.dst is not None else Reg.AX
                    src = inst.src if inst.src is not None else Reg.BX
                    self._alu.div_f64(dst=dst, src=src)
                case MicroOp.LN_F32:
                    self._alu.ln_f32()
                case MicroOp.LN_F64:
                    self._alu.ln_f64()
                case MicroOp.EXP_F32:
                    self._alu.exp_f32()
                case MicroOp.EXP_F64:
                    self._alu.exp_f64()
                case MicroOp.POW_F32:
                    dst = inst.dst if inst.dst is not None else Reg.AL
                    src = inst.src if inst.src is not None else Reg.BL
                    self._alu.pow_f32(dst=dst, src=src)
                case MicroOp.POW_F64:
                    dst = inst.dst if inst.dst is not None else Reg.AX
                    src = inst.src if inst.src is not None else Reg.BX
                    self._alu.pow_f64(dst=dst, src=src)
                case MicroOp.LOAD_CONST:
                    opcode = inst.imm
                    if opcode is not None:
                        if opcode & 1:
                            val = self._hw.rom.load_const64(opcode)
                            self._hw.reg.set(Reg.FX, val)
                        else:
                            val = self._hw.rom.load_const32(opcode)
                            self._hw.reg.set(Reg.FL, val)
                case MicroOp.CP_MEM_TOS:
                    slot = inst.imm if inst.imm is not None else 0
                    if self._hw.reg.sp < 4:
                        self._hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
                        self._hw.reg.set_flag(StatusFlag.ERR, True)
                    else:
                        tos_data = stack.peek32(self._hw)
                        self._hw.mem.store_user_mem(slot, tos_data)
                case MicroOp.CP_TOS_MEM:
                    slot = inst.imm if inst.imm is not None else 0
                    if self._hw.reg.sp + 4 > 256:
                        self._hw.reg.set_flag(StatusFlag.OVERFLOW, True)
                        self._hw.reg.set_flag(StatusFlag.ERR, True)
                    else:
                        data = self._hw.mem.load_user_mem(slot, 4)
                        self._hw.reg.set(Reg.FL, data)
                        stack.push32(self._hw, Reg.FL)
                case MicroOp.ZERO_MEM:
                    self._hw.mem.zero_user_mem()
                case MicroOp.SWAP:
                    if inst.dst is not None and inst.src is not None:
                        self._alu.swap(inst.dst, inst.src)
                case MicroOp.MOV:
                    if inst.dst is not None and inst.src is not None:
                        self._hw.reg.set(inst.dst, self._hw.reg.get(inst.src))
                case MicroOp.JMP:
                    pc = inst.target
                case MicroOp.JZ:
                    if inst.flag is not None and not self._hw.reg.get_flag(inst.flag):
                        pc = inst.target
                case MicroOp.JNZ:
                    if inst.flag is not None and self._hw.reg.get_flag(inst.flag):
                        pc = inst.target
                case MicroOp.RET:
                    break
                case MicroOp.TRAP:
                    self._hw.reg.set_flag(StatusFlag.ERR, True)
                    break
                case MicroOp.NOP:
                    pass
