from typing import Callable, Optional

from fpu_emu.blocks.control.count_adder import CountAdder
from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


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
        self._ret_set = Register(name=Reg.RET_SET, size_in_bits=1, clock=clock)
        self._ret_reg = Register(name=Reg.RET, size_in_bits=10, clock=clock)
        self._ret_set.write(0)

        self._c_reg = c_reg
        self._count_adder = CountAdder(c_reg)

        self._dst_mux = Mux(name="ctrl_dst_mux", inputs=[
            self._none_bus,
            self._upc_bus,
        ])

    def execute(self):
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
            case MicroOp.TRAP:
                self._trap(instr)
            case MicroOp.NOP:
                self._nop(instr)
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

    def _jnz(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.JNZ)
        assert instr.flag is not None
        # If ZF is 0 (not zero), select UPC (index 1), else NONE (index 0)
        flag = 0 if self._inputs.status.is_bit_set(instr.flag) else 1
        self._jump_zero(flag)
        self._clock.tick()
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _jz(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.JZ)
        assert instr.flag is not None
        # If ZF is 1 (zero), select UPC (index 1), else NONE (index 0)
        flag = 1 if self._inputs.status.is_bit_set(instr.flag) else 0
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
        c_reg = self._c_reg
        count_adder = self._count_adder
        new_c = count_adder.val
        is_zero = count_adder.is_zero

        # DJNZ branches if NOT zero (!ZF)
        flag = 0 if is_zero else 1
        self._jump_zero(flag)
        self._clock.tick()

        # Edge-triggered updates on clock edge
        c_reg.write(new_c)
        self._inputs.status.set_bit(StatusFlag.ZERO, is_zero)
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _call(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.CALL)
        assert self._ret_set.read_int() == 0, "Nested microcode CALL is unsupported"
        # this is hard-wired to UPC register output
        upc = self._inputs.ha_mux.read()

        # Absolute microcode jump address
        self._inputs.hb_mux.select(Reg.IMM.value)
        addr = self._inputs.hb_mux.read()
        self._outputs.block_res.set(addr)
        self._outputs.block_res_sel.set(Reg.UPC.value)
        self._outputs.exec_done.set(1)
        self._clock.tick()
        self._ret_set.write(1)
        self._ret_reg.write(upc)
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _ret(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.RET)
        assert self._ret_set.read_int() == 1, "Microcode RET without prior CALL"
        # Absolute microcode address
        addr = self._ret_reg.read_int()
        self._outputs.block_res.set(addr)
        self._outputs.block_res_sel.set(Reg.UPC.value)
        self._outputs.exec_done.set(1)
        self._clock.tick()
        self._ret_set.write(0)
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _trap(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.TRAP)
        self._inputs.status.set_bit(StatusFlag.ERR, True)
        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.exec_done.set(1)
        self._clock.tick()

    def _nop(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.NOP)
        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.exec_done.set(1)
        self._clock.tick()
