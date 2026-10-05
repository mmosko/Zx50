import operator
from dataclasses import dataclass
from typing import Callable

from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


@dataclass
class LogicResult:
    """Result of a 32-bit Radix-4 Booth multiplication."""

    res: int  # 4 bytes l
    cf: bool  # Always False
    zf: bool  # True if entire 64-bit product is zero
    sf: bool  # True if MSB of 64-bit product (bit 63) is 1
    vf: bool  # True if product overflows 32-bit representation


@fpga_resource(
    approach="Logic controller, 32/64-bit logic operations",
    luts=45,
    ffs=8,
    delay_ns=2.5,
    cycles=1,
    shared_unit="logic_block",
)
class LogicBlock(FunctionalBlock):
    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, writeback: Callable, clock: Clock):
        super().__init__(name, inputs, memory, writeback, clock)
        assert isinstance(inputs.ha_mux, Mux)

    def execute(self):
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.AND:
                self._and(instr)
            case MicroOp.OR:
                self._or(instr)
            case MicroOp.XOR:
                self._xor(instr)
            case MicroOp.ABS:
                self._abs(instr)
            case MicroOp.CHS:
                self._chs(instr)
            case MicroOp.NOT:
                self._not(instr)
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    def _and(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.AND)
        if instr.is_w32():
            self._logic_32(instr, operator.and_)
        else:
            self._logic_64(instr, operator.and_)

    def _or(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.OR)
        if instr.is_w32():
            self._logic_32(instr, operator.or_)
        else:
            self._logic_64(instr, operator.or_)

    def _xor(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.XOR)
        if instr.is_w32():
            self._logic_32(instr, operator.xor)
        else:
            self._logic_64(instr, operator.xor)

    def _chs(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.CHS)
        raise NotImplementedError

    def _abs(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.ABS)
        raise NotImplementedError

    def _not(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.NOT)
        raise NotImplementedError

    def _logic_core(self, op: Callable) -> LogicResult:
        a_val = self._inputs.ha_mux.read_int()
        b_val = self._inputs.hb_mux.read_int()
        res = op(a_val, b_val)
        return LogicResult(
            res = res,
            cf = False,
            zf = True if res == 0 else False,
            sf = False,
            vf = False,
        )

    def _logic_32(self, instr: MicroInstruction, op: Callable) -> None:
        """32-bit generic binary logic operation"""
        assert (instr.src is not Reg.NONE)
        assert (instr.dst is not Reg.NONE)

        # Combinatorial setup in current cycle
        self._inputs.ha_mux.select(instr.dst.value)
        self._inputs.hb_mux.select(instr.src.value)
        result = self._logic_core(op)
        self._outputs.block_res.set(result.res)
        self._outputs.block_res_sel.set(instr.dst.value)
        self._outputs.exec_done.set(1)
        self._wb_flags(result)
        self._writeback()

    def _logic_64(self, instr: MicroInstruction, op: Callable) -> None:
        """32-bit generic binary logic operation"""
        assert (instr.src is not Reg.NONE)
        assert (instr.dst is not Reg.NONE)
        assert (instr.src.is_lo_half())
        assert (instr.dst.is_lo_half())

        # Combinatorial setup in current cycle
        self._inputs.ha_mux.select(instr.dst.value)
        self._inputs.hb_mux.select(instr.src.value)
        result_lo = self._logic_core(op)
        self._outputs.block_res.set(result_lo.res)
        self._outputs.block_res_sel.set(instr.dst.value)
        self._writeback()
        self._clock.tick()

        self._inputs.ha_mux.select(instr.dst.value | 1)
        self._inputs.hb_mux.select(instr.src.value | 1)
        result_hi = self._logic_core(op)
        result_hi.zf &= result_lo.zf
        self._outputs.block_res.set(result_hi.res)
        self._outputs.block_res_sel.set(instr.dst.value | 1)
        self._wb_flags(result_hi)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _wb_flags(self, result: LogicResult):
        status_byte = 0
        status_byte |= result.cf << StatusFlag.CARRY.value
        status_byte |= result.sf << StatusFlag.SIGN.value
        status_byte |= result.vf << StatusFlag.OVERFLOW.value
        status_byte |= result.zf << StatusFlag.ZERO.value
        err = getattr(result, "err", False)
        status_byte |= err << StatusFlag.ERR.value
        self._outputs.res_status.set(status_byte)

        status_wr_select = (1 << StatusFlag.CARRY.value) | \
                           (1 << StatusFlag.SIGN.value) | \
                           (1 << StatusFlag.OVERFLOW.value) | \
                           (1 << StatusFlag.ZERO.value)
        if hasattr(result, "err"):
            status_wr_select |= (1 << StatusFlag.ERR.value)

        self._outputs.status_wr_sel.set(status_wr_select)