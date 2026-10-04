from typing import Callable

from fpu_emu.blocks.adder.adder_core import AdderCore, AdderResult
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
    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, writeback: Callable, clock: Clock):
        super().__init__(name, inputs, memory, writeback, clock)
        self._none_bus = Bus(name="none_bus", size_in_bits=4)
        self._upc_bus = Bus(name="upc_bus", size_in_bits=4)
        self._none_bus.set(Reg.NONE.value)
        self._upc_bus.set(Reg.UPC.value)
        self._ret_set = Register(name=Reg.RET_SET, size_in_bits=1, clock=clock)
        self._ret = Register(name=Reg.RET, size_in_bits=6, clock=clock)
        self._ret_set.write(0)

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
        # If ZF is set, we want a "0" to select the NONE destination register
        flag = self._inputs.status.is_bit_set(StatusFlag.ZERO)  ^ 1
        self._jump_zero(flag)
        self._clock.tick()
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _jz(self, instr: MicroInstruction):
        assert (instr.op == MicroOp.JZ)
        # If ZF is set, we want a "1" to select the UPC destination register
        flag = self._inputs.status.is_bit_set(StatusFlag.ZERO) ^ 1
        self._jump_zero(flag)
        self._clock.tick()
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _jump_zero(self, flag):
        self._inputs.hb_mux.select(Reg.IMM.value)
        addr = self._inputs.hb_mux.read()
        self._outputs.block_res.set(addr)
        self._dst_mux.select(flag)
        self._outputs.block_res_sel.set(self._dst_mux)
        self._outputs.exec_done.set(1)

    def _djnz(self, instr: MicroInstruction) -> None:
        # TODO: We need a dedicated C subtractor (6 bits)
        raise NotImplementedError()

    def _call(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.CALL)
        assert (self._ret_set.read() == 0)
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
        self._ret.write(upc)
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _ret(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.RET)
        assert (self._ret_set.read() == 1)
        # Absolute microcode address
        addr = self._ret.read_int()
        self._outputs.block_res.set(addr)
        self._outputs.block_res_sel.set(Reg.UPC.value)
        self._outputs.exec_done.set(1)
        self._ret_set.write(0)
        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _trap(self, instr: MicroInstruction) -> None:
        # TODO: Does this need to be here, or is dispatcher catching this?
        raise NotImplementedError()

    def _nop(self, instr: MicroInstruction) -> None:
        raise NotImplementedError()
