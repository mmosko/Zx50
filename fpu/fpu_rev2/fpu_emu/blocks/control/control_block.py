from typing import Callable, Optional

from fpu_emu.blocks.control.count_adder import CountAdder
from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.lut_mem import LutRam
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


@fpga_resource(
    approach="Branch condition evaluator, jump routing, and loop control",
    luts=40,
    ffs=4,
    delay_ns=2.5,
    cycles=1,
    shared_unit="control_block",
)
class ControlBlock(FunctionalBlock):
    def __init__(self,
                 name: str,
                 inputs: BlockInputs,
                 memory: Memory,
                 writeback: Callable,
                 clock: Clock,
                 c_reg: Register):
        super().__init__(name, inputs, memory, writeback, clock)
        self._none_bus = Bus(name="none_bus", size_in_bits=4)
        self._upc_bus = Bus(name="upc_bus", size_in_bits=4)
        self._none_bus.set(Reg.NONE.value)
        self._upc_bus.set(Reg.UPC.value)

        # Distributed LUT memory, 8x 10 bits
        self._call_stack = LutRam(name="call_stack", size=8, width=10, clock=clock)
        self._csp = Register(name=Reg.RET_SET, size_in_bits=3, clock=clock)
        self._csp.write(0)

        self._c_reg = c_reg
        self._count_adder = CountAdder(c_reg)

        self._dst_mux = Mux(name="ctrl_dst_mux", inputs=[
            self._none_bus,
            self._upc_bus,
        ])

    def execute(self):
        self._outputs.status_wr_sel.set(0)
        self._outputs.res_status.set(0)
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.JMP:
                self._jmp(instr)
            case MicroOp.JNZ:
                self._jnz(instr)
            case MicroOp.JZ:
                self._jz(instr)
            case MicroOp.DJNZ:
                self._djnz(instr)
            case MicroOp.CALL:
                self._call(instr)
            case MicroOp.RET:
                self._ret(instr)
            case MicroOp.NOP:
                self._nop(instr)
            case MicroOp.HALT:
                self._halt(instr)
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    def _jmp(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.JMP)
        self._inputs.hb_mux.select(Reg.IMM.value)
        addr = self._inputs.hb_mux.read()
        self._outputs.block_res.set(addr)
        self._outputs.block_res_sel.set(Reg.UPC.value)
        self._outputs.exec_done.set(1)
        self._clock.tick()
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _test_condition(self, instr: MicroInstruction) -> bool:
        """Evaluates whether a conditional jump (JZ, JNZ) should be taken.

        For StatusFlag.ZERO:
            JZ branches if ZF == 1 (result is zero).
            JNZ branches if ZF == 0 (result is not zero).
        For all other flags (UNDERFLOW, OVERFLOW, CARRY, ERR, SIGN, etc.):
            JNZ branches if flag == 1 (flag is set / not zero).
            JZ branches if flag == 0 (flag is clear / zero).
        """
        flag_to_test = instr.flag
        bit_is_set = self._inputs.status.is_bit_set(flag_to_test)
        if flag_to_test == StatusFlag.ZERO:
            return bit_is_set if instr.op == MicroOp.JZ else not bit_is_set
        else:
            return not bit_is_set if instr.op == MicroOp.JZ else bit_is_set

    def _jnz(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.JNZ)
        flag = 1 if self._test_condition(instr) else 0
        self._jump_zero(flag)
        self._clock.tick()
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _jz(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.JZ)
        flag = 1 if self._test_condition(instr) else 0
        self._jump_zero(flag)
        self._clock.tick()
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _jump_zero(self, flag: int) -> None:
        self._inputs.hb_mux.select(Reg.IMM.value)
        addr = self._inputs.hb_mux.read()
        self._outputs.block_res.set(addr)
        self._dst_mux.select(flag)
        self._outputs.block_res_sel.set(self._dst_mux.read_int())
        self._outputs.exec_done.set(1)

    def _djnz(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.DJNZ)
        count_adder = self._count_adder
        new_c = count_adder.val
        is_zero = count_adder.is_zero

        # DJNZ branches if NOT zero (!ZF)
        flag = 0 if is_zero else 1
        self._jump_zero(flag)

        # Status writeback for ZERO flag
        zf_mask = 1 << StatusFlag.ZERO.value
        self._outputs.status_wr_sel.set(zf_mask)
        self._outputs.res_status.set(zf_mask if is_zero else 0)

        # Edge-triggered updates on clock edge via writeback
        self._c_reg.write(new_c)
        self._writeback()

    def _call(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.CALL)
        csp = self._csp.read_int()
        next_csp = csp + 1

        # this is hard-wired to UPC register output
        upc = self._inputs.ha_mux.read_int()

        # Absolute microcode jump address
        self._inputs.hb_mux.select(Reg.IMM.value)
        addr = self._inputs.hb_mux.read()
        self._outputs.block_res.set(addr)
        self._outputs.block_res_sel.set(Reg.UPC.value)
        self._outputs.exec_done.set(1)

        # Update the call stack
        self._call_stack.write(csp, upc)
        self._clock.tick()

        # Need a 3-bit adder or state machine to calculate next _csp
        self._csp.write(next_csp)
        # If the csp is 0, we wrapped around
        assert self._csp.read_int() != 0, f"Call stack out of range: {csp}"

        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _ret(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.RET)
        # small adder or state machine for 3-bit CSP
        csp = self._csp.read_int() - 1
        assert 0 <= csp < self._call_stack.size, f"Call stack out of range: {csp}"

        # Absolute microcode address
        addr = self._call_stack.read(csp)
        self._outputs.block_res.set(addr)
        self._outputs.block_res_sel.set(Reg.UPC.value)
        self._outputs.exec_done.set(1)
        self._clock.tick()
        self._csp.write(csp)
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _nop(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.NOP)
        self._outputs.exec_wb.set(0)
        self._outputs.status_wr_sel.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.exec_done.set(1)
        self._clock.tick()

    def _halt(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.HALT)
        bsy_mask = 1 << StatusFlag.BUSY.value
        self._outputs.status_wr_sel.set(bsy_mask)
        self._outputs.res_status.set(0)  # BUSY=0
        self._outputs.block_res.set(0x3FF)
        self._outputs.block_res_sel.set(Reg.UPC.value)
        self._outputs.exec_done.set(1)
        self._csp.write(0)
        self._writeback()
