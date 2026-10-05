from typing import Callable

from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.blocks.memory.stack_adder import StackAdder
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


class MemoryBlock(FunctionalBlock):
    """
    Manipulates the math Stack, the scratch memory and the user memory.

    EBR 0 & EBR 1 (paired 512 words x 36 bits)
      - Hardware Math Stack (128 words x 32-bit)
      - Scratchpad RAM SCR[0..63] (64 x 32-bit)
      - User Word Storage (16 words x 32-bit)
      - Reserved / Working Headroom (304 words)
    """

    # TODO: For these to be pure prefixes (not adds), we need the prefix to align at 7 bits, so
    # we get 2 prefix bits
    MTH_BASE = 0b0_0000_0000
    SCR_BASE = 0b0_1000_0000
    USR_BASE = 0b1_0000_0000
    EXT_BASE = 0b1_1000_0000

    def __init__(self,
                 name: str,
                 inputs: BlockInputs,
                 memory: Memory,
                 writeback: Callable,
                 clock: Clock,
                 sp_reg: Register):
        super().__init__(name, inputs, memory, writeback, clock)
        self._none_bus = Bus(name="none_bus", size_in_bits=4)
        self._upc_bus = Bus(name="upc_bus", size_in_bits=4)
        self._none_bus.set(Reg.NONE.value)

        self._sp = sp_reg
        self._stack_adder = StackAdder(sp_reg)

    def execute(self):
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.PUSH:
                self._push(instr)
            case MicroOp.POP:
                self._pop(instr)
            case MicroOp.LDC:
                self._ldc(instr)
            case MicroOp.LDI:
                self._ldi(instr)
            case MicroOp.LD:
                self._ld(instr)
            case MicroOp.STO:
                self._sto(instr)
            case MicroOp.LDU:
                self._ldu(instr)
            case MicroOp.STU:
                self._stu(instr)
            case MicroOp.MOV:
                self._mov(instr)
            case MicroOp.SWAP:
                self._swap(instr)
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    STATUS_OVERFLOW_ERR_MASK = (1 << StatusFlag.OVERFLOW.value) | (1 << StatusFlag.ERR.value)
    STATUS_UNDERFLOW_ERR_MASK = (1 << StatusFlag.UNDERFLOW.value) | (1 << StatusFlag.ERR.value)

    def _push(self, instr: MicroInstruction) -> None:
        """push src to TOS"""
        assert (instr.op == MicroOp.PUSH)
        assert (instr.src is not Reg.NONE)
        if instr.is_w32():
            self._push32(instr)
        else:
            self._push64(instr)

    def _push32(self, instr: MicroInstruction) -> None:
        """push src to TOS"""
        assert instr.src is not Reg.NONE
        self._inputs.hb_mux.select(instr.src.value)
        self._inner_push32()
        self._outputs.exec_done.set(1)
        self._writeback()

    def _push64(self, instr: MicroInstruction) -> None:
        """push src to TOS, pushes low order bytes first"""
        assert instr.src is not Reg.NONE
        assert (instr.src.is_lo_half())
        self._inputs.hb_mux.select(instr.src.value)
        self._inner_push32()
        self._writeback()

        if self._outputs.res_status.read_int() != 0:
            # It was an error, we abort
            self._outputs.exec_done.set(1)
            return

        # select the HI register
        self._inputs.hb_mux.select(instr.src.value | 1)
        self._inner_push32()
        self._outputs.exec_done.set(1)
        self._writeback()

    def _inner_push32(self):
        value = self._inputs.hb_mux.read_int()

        # Set it up to calculate SP+1
        self._stack_adder.set_op(StackAdder.OP_INC)

        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.status_wr_sel.set(self.STATUS_OVERFLOW_ERR_MASK)

        if self._stack_adder.is_overflow:
            # Stack overflow: set VF and ERR, do not write memory or update SP
            self._outputs.res_status.set(self.STATUS_OVERFLOW_ERR_MASK)
            # calls to _writeback() done in caller
            return

        # No overflow: clear VF and ERR
        self._outputs.res_status.set(0)

        # 1 cycle to present address and data
        addr = self.MTH_BASE | self._sp.read_int()
        self._memory.write(0, addr, value & 0xFFFF)
        self._memory.write(1, addr, (value >> 16) & 0xFFFF)
        self._clock.tick()

        # Writeback the updated SP
        self._sp.write(self._stack_adder.read())
        # Calls to _writeback() are always done in the caller

    def _pop(self, instr: MicroInstruction) -> None:
        """Pops TOS to dst"""
        assert instr.op == MicroOp.POP
        assert instr.dst is not Reg.NONE
        if instr.is_w32():
            self._pop32(instr)
        else:
            self._pop64(instr)

    def _pop32(self, instr: MicroInstruction) -> None:
        """Pops TOS to dst (32-bit)"""
        assert instr.dst is not Reg.NONE
        self._inner_pop32()
        self._outputs.exec_done.set(1)
        if self._outputs.res_status.read_int() != 0:
            # Underflow error: commit UF/ERR without writing dst
            self._writeback()
            return

        self._outputs.block_res_sel.set(instr.dst.value)
        self._writeback()

    def _pop64(self, instr: MicroInstruction) -> None:
        """Pops TOS to dst (64-bit), pops high order word first"""
        assert instr.dst is not Reg.NONE
        assert instr.dst.is_lo_half()

        # 1. Read HI word from TOS
        self._inner_pop32()
        if self._outputs.res_status.read_int() != 0:
            self._outputs.exec_done.set(1)
            self._writeback()
            return

        self._outputs.block_res_sel.set(instr.dst.value | 1)
        self._writeback()

        # 2. Read LO word from TOS
        self._inner_pop32()
        self._outputs.exec_done.set(1)
        if self._outputs.res_status.read_int() != 0:
            self._writeback()
            return

        self._outputs.block_res_sel.set(instr.dst.value)
        self._writeback()

    def _inner_pop32(self) -> None:
        # Set it up to calculate SP-1
        self._stack_adder.set_op(StackAdder.OP_DEC)

        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.status_wr_sel.set(self.STATUS_UNDERFLOW_ERR_MASK)

        if self._stack_adder.is_underflow:
            # Stack underflow: set UF and ERR, do not write memory or update SP
            self._outputs.res_status.set(self.STATUS_UNDERFLOW_ERR_MASK)
            return

        new_sp = self._stack_adder.read_int()

        # No underflow: clear UF and ERR
        self._outputs.res_status.set(0)
        self._clock.tick()

        # 1 cycle to present address and data
        addr = self.MTH_BASE | new_sp
        val_lo = self._memory.read(0, addr)
        val_hi = self._memory.read(1, addr)

        # Writeback the updated SP
        self._sp.write(self._stack_adder.read())

        # writeback the destination register
        self._outputs.block_res.set(val_hi << 16 | val_lo)


    def _ldc(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.LDC)
        raise NotImplementedError

    def _ldi(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.LDI)
        raise NotImplementedError

    def _ld(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.LD)
        raise NotImplementedError

    def _sto(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.STO)
        raise NotImplementedError

    def _ldu(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.LDU)
        raise NotImplementedError

    def _stu(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.STU)
        raise NotImplementedError

    def _mov(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.MOV)
        raise NotImplementedError

    def _swap(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.SWAP)
        raise NotImplementedError
