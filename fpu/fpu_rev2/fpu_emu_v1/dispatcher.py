"""Command Dispatcher and Micro-sequencer execution engine."""

from typing import Callable, List
from fpu_emu.alu.alu import Alu
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware import Hardware
from fpu_emu.memory import ld, mov, stack, swap
from fpu_emu.hardware.memory import CMD_STACK_BASE, CMD_STACK_SIZE
from fpu_emu.hardware.registers import Reg, StatusFlag
from fpu_emu.micro_code import MicroCode
from fpu_emu.micro_opcodes import MicroInstruction, MicroOp
from fpu_emu.user_opcodes import UserOpcode


class Dispatcher:
    """Dispatches user opcodes and executes microcode instruction streams."""

    @fpga_resource(
        approach="Host Z80 bus interface, Port 0x70/0x71 decoder, BWAIT_N generator, and mode flags",
        luts=95,
        ffs=45,
        delay_ns=2.5,
        cycles=1,
        shared_unit="host_bus_interface",
    )
    def __init__(self, hw: Hardware, alu: Alu):
        self._hw = hw
        self._alu = alu
        self._batch_mode: bool = False
        self._blocking_mode: bool = True
        self._sqrt_is_odd: bool = False
        self._pc: int = 0
        self._halted: bool = False

        self._FUNCTORS: dict[MicroOp, Callable[[MicroInstruction], None]] = {
            MicroOp.ABS: self._run_abs,
            MicroOp.ABS_INT: self._run_abs_int,
            MicroOp.ABS_INT64: self._run_abs_int64,
            MicroOp.ADC: self._run_adc,
            MicroOp.ADC64: self._run_adc64,
            MicroOp.ADD: self._run_add,
            MicroOp.ADD64: self._run_add64,
            MicroOp.AND: self._run_and,
            MicroOp.AND64: self._run_and64,
            MicroOp.ASR: self._run_asr,
            MicroOp.ASR64: self._run_asr64,
            MicroOp.CHS: self._run_chs,
            MicroOp.CMP: self._run_cmp,
            MicroOp.CMP64: self._run_cmp64,
            MicroOp.CP_MEM_TOS: self._run_cp_mem_tos,
            MicroOp.CP_TOS_MEM: self._run_cp_tos_mem,
            MicroOp.DIV_F32: self._run_div_f32,
            MicroOp.DIV_F64: self._run_div_f64,
            MicroOp.EXP_ADD: self._run_exp_add,
            MicroOp.EXP_DEC: self._run_exp_dec,
            MicroOp.EXP_DIFF: self._run_exp_diff,
            MicroOp.EXP_F32: self._run_exp_f32,
            MicroOp.EXP_F64: self._run_exp_f64,
            MicroOp.EXP_INC: self._run_exp_inc,
            MicroOp.EXP_NORM: self._run_exp_norm,
            MicroOp.EXP_SUB: self._run_exp_sub,
            MicroOp.JMP: self._run_jmp,
            MicroOp.JNZ: self._run_jnz,
            MicroOp.JZ: self._run_jz,
            MicroOp.LD: self._run_ld,
            MicroOp.LN_F32: self._run_ln_f32,
            MicroOp.LN_F64: self._run_ln_f64,
            MicroOp.LOAD_CONST: self._run_load_const,
            MicroOp.LSL: self._run_lsl,
            MicroOp.LSL64: self._run_lsl64,
            MicroOp.LSR: self._run_lsr,
            MicroOp.LSR64: self._run_lsr64,
            MicroOp.LZC: self._run_lzc,
            MicroOp.LZC64: self._run_lzc64,
            MicroOp.MOV: self._run_mov,
            MicroOp.MUL: self._run_mul,
            MicroOp.MUL64: self._run_mul64,
            MicroOp.MUL_F32: self._run_mul_f32,
            MicroOp.MUL_F64: self._run_mul_f64,
            MicroOp.NOP: self._run_nop,
            MicroOp.NOT: self._run_not,
            MicroOp.NOT64: self._run_not64,
            MicroOp.OR: self._run_or,
            MicroOp.OR64: self._run_or64,
            MicroOp.PACK_F32: self._run_pack_f32,
            MicroOp.PACK_F64: self._run_pack_f64,
            MicroOp.POP: self._run_pop,
            MicroOp.POP64: self._run_pop64,
            MicroOp.POW_F32: self._run_pow_f32,
            MicroOp.POW_F64: self._run_pow_f64,
            MicroOp.PUSH: self._run_push,
            MicroOp.PUSH64: self._run_push64,
            MicroOp.RET: self._run_ret,
            MicroOp.RRC: self._run_rrc,
            MicroOp.RRC64: self._run_rrc64,
            MicroOp.SBB: self._run_sbb,
            MicroOp.SBB64: self._run_sbb64,
            MicroOp.SQRT_CORE: self._run_sqrt_core,
            MicroOp.SQRT_CORE64: self._run_sqrt_core64,
            MicroOp.SQRT_EXP: self._run_sqrt_exp,
            MicroOp.SQRT_EXP64: self._run_sqrt_exp64,
            MicroOp.SUB: self._run_sub,
            MicroOp.SUB64: self._run_sub64,
            MicroOp.SWAP: self._run_swap,
            MicroOp.TRAP: self._run_trap,
            MicroOp.UNPACK_F32: self._run_unpack_f32,
            MicroOp.UNPACK_F64: self._run_unpack_f64,
            MicroOp.XOR: self._run_xor,
            MicroOp.XOR64: self._run_xor64,
            MicroOp.ZERO_MEM: self._run_zero_mem,
        }

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

    @fpga_resource(
        approach="Distributed LUT-RAM in PFU slices for 32-byte host command queue",
        luts=12,
        ffs=0,
        delay_ns=2.0,
        cycles=1,
        shared_unit="lutram_command_stack",
    )
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

    @fpga_resource(
        approach="Microcode execution engine: PC sequencer, branch MUX, and horizontal control word decoder",
        luts=125,
        ffs=24,
        delay_ns=3.4,
        cycles=1,
        shared_unit="micro_sequencer",
    )
    def _run(self, microcode: List[MicroInstruction]):
        """Micro-sequencer execution loop.

        Fetches each micro-instruction (1 tick), then executes it.
        """
        saved_pc, saved_halted = self._pc, self._halted
        self._pc = 0
        self._halted = False
        try:
            while not self._halted and self._pc < len(microcode):
                # 1 cycle micro-instruction fetch
                self._hw.clock.tick(1)
                inst = microcode[self._pc]
                self._pc += 1

                self._FUNCTORS[inst.op](inst)
        finally:
            self._pc, self._halted = saved_pc, saved_halted

    def _run_pop(self, instr: MicroInstruction) -> None:
        if instr.dst is not None:
            stack.pop32(self._hw, instr.dst)

    def _run_push(self, instr: MicroInstruction) -> None:
        if instr.src is not None:
            stack.push32(self._hw, instr.src)

    def _run_pop64(self, instr: MicroInstruction) -> None:
        if instr.dst is not None:
            stack.pop64(self._hw, instr.dst)

    def _run_push64(self, instr: MicroInstruction) -> None:
        if instr.src is not None:
            stack.push64(self._hw, instr.src)

    def _run_add(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.add32(instr.src)

    def _run_adc(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.adc32(instr.src)

    def _run_sub(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.sub32(instr.src)

    def _run_sbb(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.sbb32(instr.src)

    def _run_cmp(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.cmp32(instr.src)

    def _run_add64(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.add64(instr.src)

    def _run_adc64(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.adc64(instr.src)

    def _run_sub64(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.sub64(instr.src)

    def _run_sbb64(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.sbb64(instr.src)

    def _run_cmp64(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.cmp64(instr.src)

    def _run_lsl(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.dst != Reg.AL:
            self._alu.lsl32(shift=instr.imm if instr.imm else None, reg=instr.dst)
        else:
            self._alu.lsl32(shift=instr.imm if instr.imm else None)

    def _run_lsr(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.dst != Reg.AL:
            self._alu.lsr32(shift=instr.imm if instr.imm else None, reg=instr.dst)
        else:
            self._alu.lsr32(shift=instr.imm if instr.imm else None)

    def _run_asr(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.dst != Reg.AL:
            self._alu.asr32(shift=instr.imm if instr.imm else None, reg=instr.dst)
        else:
            self._alu.asr32(shift=instr.imm if instr.imm else None)

    def _run_rrc(self, instr: MicroInstruction) -> None:
        if instr.dst in (Reg.AX, Reg.BX, Reg.DX, Reg.FX):
            self._alu.rrc64(reg=instr.dst)
        elif instr.dst is not None and instr.dst != Reg.AL:
            self._alu.rrc32(reg=instr.dst)
        else:
            self._alu.rrc32()

    def _run_rrc64(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.dst != Reg.AX:
            self._alu.rrc64(reg=instr.dst)
        else:
            self._alu.rrc64()

    def _run_lsl64(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.dst != Reg.AX:
            self._alu.lsl64(shift=instr.imm if instr.imm else None, reg=instr.dst)
        else:
            self._alu.lsl64(shift=instr.imm if instr.imm else None)

    def _run_lsr64(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.dst != Reg.AX:
            self._alu.lsr64(shift=instr.imm if instr.imm else None, reg=instr.dst)
        else:
            self._alu.lsr64(shift=instr.imm if instr.imm else None)

    def _run_asr64(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.dst != Reg.AX:
            self._alu.asr64(shift=instr.imm if instr.imm else None, reg=instr.dst)
        else:
            self._alu.asr64(shift=instr.imm if instr.imm else None)

    def _run_lzc(self, instr: MicroInstruction) -> None:
        if instr.src is not None and instr.src != Reg.AL:
            self._alu.lzc32(reg=instr.src)
        else:
            self._alu.lzc32()

    def _run_lzc64(self, instr: MicroInstruction) -> None:
        if instr.src is not None and instr.src != Reg.AX:
            self._alu.lzc64(reg=instr.src)
        else:
            self._alu.lzc64()

    def _run_and(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.and32(instr.src)

    def _run_or(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.or32(instr.src)

    def _run_xor(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.xor32(instr.src)

    def _run_not(self, _: MicroInstruction) -> None:
        self._alu.not32()

    def _run_and64(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.and64(instr.src)

    def _run_or64(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.or64(instr.src)

    def _run_xor64(self, instr: MicroInstruction) -> None:
        assert instr.src is not None
        self._alu.xor64(instr.src)

    def _run_not64(self, _: MicroInstruction) -> None:
        self._alu.not64()

    def _run_chs(self, instr: MicroInstruction) -> None:
        if instr.dst is None:
            raise ValueError("MicroOp.CHS requires a target register in instr.dst")
        self._alu.chs(instr.dst)

    def _run_abs(self, instr: MicroInstruction) -> None:
        if instr.dst is None:
            raise ValueError("MicroOp.ABS requires a target register in instr.dst")
        self._alu.abs_val(instr.dst)

    def _run_abs_int(self, instr: MicroInstruction) -> None:
        if instr.dst is None:
            raise ValueError("MicroOp.ABS_INT requires a target register in instr.dst")
        self._alu.abs_int32(instr.dst)

    def _run_abs_int64(self, instr: MicroInstruction) -> None:
        if instr.dst is None:
            raise ValueError("MicroOp.ABS_INT64 requires a target register in instr.dst")
        self._alu.abs_int64(instr.dst)

    def _run_mul(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.BL
        self._alu.mul32(src=src)

    def _run_mul64(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.BX
        self._alu.mul64(src=src)

    def _run_mul_f32(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.BL
        self._alu.mul_f32(src=src)

    def _run_div_f32(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.BL
        self._alu.div_f32(src=src)

    def _run_mul_f64(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.BX
        self._alu.mul_f64(src=src)

    def _run_div_f64(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.BX
        self._alu.div_f64(src=src)

    def _run_ln_f32(self, _: MicroInstruction) -> None:
        self._alu.ln_f32()

    def _run_ln_f64(self, _: MicroInstruction) -> None:
        self._alu.ln_f64()

    def _run_exp_f32(self, _: MicroInstruction) -> None:
        self._alu.exp_f32()

    def _run_exp_f64(self, _: MicroInstruction) -> None:
        self._alu.exp_f64()

    def _run_pow_f32(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.BL
        self._alu.pow_f32(src=src)

    def _run_pow_f64(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.BX
        self._alu.pow_f64(src=src)

    def _run_load_const(self, instr: MicroInstruction) -> None:
        opcode = instr.imm
        if opcode is not None:
            if opcode & 1:
                val = self._hw.rom.load_const64(opcode)
                self._hw.clock.tick(1)
                self._hw.reg.set_res_bus(Reg.FL, val[:4])
                self._hw.clock.tick(1)
                self._hw.reg.set_res_bus(Reg.FH, val[4:8])
            else:
                val = self._hw.rom.load_const32(opcode)
                self._hw.clock.tick(1)
                self._hw.reg.set_res_bus(Reg.FL, val[:4])

    def _run_cp_mem_tos(self, instr: MicroInstruction) -> None:
        slot = instr.imm if instr.imm is not None else 0
        if self._hw.reg.sp < 4:
            self._hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
            self._hw.reg.set_flag(StatusFlag.ERR, True)
        else:
            tos_data = stack.peek32(self._hw)
            self._hw.mem.store_user_mem(slot, tos_data)

    def _run_cp_tos_mem(self, instr: MicroInstruction) -> None:
        slot = instr.imm if instr.imm is not None else 0
        if self._hw.reg.sp + 4 > 256:
            self._hw.reg.set_flag(StatusFlag.OVERFLOW, True)
            self._hw.reg.set_flag(StatusFlag.ERR, True)
        else:
            data = self._hw.mem.load_user_mem(slot, 4)
            self._hw.clock.tick(1)
            self._hw.reg.set_res_bus(Reg.FL, data[:4])
            stack.push32(self._hw, Reg.FL)

    def _run_zero_mem(self, _: MicroInstruction) -> None:
        self._hw.mem.zero_user_mem()

    def _run_exp_add(self, _: MicroInstruction) -> None:
        self._alu.exp_add()

    def _run_exp_sub(self, _: MicroInstruction) -> None:
        self._alu.exp_sub()

    def _run_exp_diff(self, instr: MicroInstruction) -> None:
        reg = instr.src if instr.src is not None else (instr.dst if instr.dst is not None else Reg.AL)
        self._alu.exp_diff(reg=reg)

    def _run_exp_norm(self, _: MicroInstruction) -> None:
        self._alu.exp_adj_norm()

    def _run_exp_inc(self, _: MicroInstruction) -> None:
        self._alu.exp_inc()

    def _run_exp_dec(self, _: MicroInstruction) -> None:
        self._alu.exp_dec()

    def _run_unpack_f32(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.AL
        dst_exp = instr.dst if instr.dst is not None else Reg.EA
        self._alu.unpack_f32(src=src, dst_mantissa=src, dst_exp=dst_exp)

    def _run_pack_f32(self, instr: MicroInstruction) -> None:
        src_exp = instr.src if instr.src is not None else Reg.EA
        self._alu.pack_f32(src_exp=src_exp)

    def _run_unpack_f64(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not None else Reg.AX
        dst_exp = instr.dst if instr.dst is not None else Reg.EA
        self._alu.unpack_f64(src=src, dst_mantissa=src, dst_exp=dst_exp)

    def _run_pack_f64(self, instr: MicroInstruction) -> None:
        src_exp = instr.src if instr.src is not None else Reg.EA
        self._alu.pack_f64(src_exp=src_exp)

    def _run_sqrt_exp(self, instr: MicroInstruction) -> None:
        exp_reg = instr.dst if instr.dst is not None else Reg.EA
        self._sqrt_is_odd = self._alu.sqrt_exp32(exp_reg=exp_reg)

    def _run_sqrt_core(self, _: MicroInstruction) -> None:
        self._alu.sqrt_core32(is_odd=self._sqrt_is_odd)

    def _run_sqrt_exp64(self, instr: MicroInstruction) -> None:
        exp_reg = instr.dst if instr.dst is not None else Reg.EA
        self._sqrt_is_odd = self._alu.sqrt_exp64(exp_reg=exp_reg)

    def _run_sqrt_core64(self, _: MicroInstruction) -> None:
        self._alu.sqrt_core64(is_odd=self._sqrt_is_odd)

    def _run_ld(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.imm is not None:
            ld.ld(self._hw, instr.dst, instr.imm)

    def _run_mov(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.src is not None:
            mov.mov(self._hw, instr.dst, instr.src)

    def _run_swap(self, instr: MicroInstruction) -> None:
        if instr.dst is not None and instr.src is not None:
            swap.swap(self._hw, instr.dst, instr.src)

    def _run_jmp(self, instr: MicroInstruction) -> None:
        self._pc = instr.target

    def _run_jz(self, instr: MicroInstruction) -> None:
        if instr.flag is not None and not self._hw.reg.get_flag(instr.flag):
            self._pc = instr.target

    def _run_jnz(self, instr: MicroInstruction) -> None:
        if instr.flag is not None and self._hw.reg.get_flag(instr.flag):
            self._pc = instr.target

    def _run_ret(self, _: MicroInstruction) -> None:
        self._halted = True

    def _run_trap(self, _: MicroInstruction) -> None:
        self._hw.reg.set_flag(StatusFlag.ERR, True)
        self._halted = True

    def _run_nop(self, _: MicroInstruction) -> None:
        pass




