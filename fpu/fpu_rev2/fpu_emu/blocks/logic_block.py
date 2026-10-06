import operator
from dataclasses import dataclass
from typing import Callable, Optional

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
    """Result of a logic block operation."""

    res: int  # 32-bit integer result
    cf: bool = False
    zf: bool = False
    sf: bool = False
    vf: bool = False


@fpga_resource(
    approach="Logic controller, 32/64-bit bitwise logic operations (AND, OR, XOR, NOT) and FP sign manipulation (FABS, FCHS)",
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
        assert isinstance(inputs.hb_mux, Mux)
        self._ha_mux: Mux = inputs.ha_mux
        self._hb_mux: Mux = inputs.hb_mux

    def execute(self):
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.AND:
                self._and(instr)
            case MicroOp.OR:
                self._or(instr)
            case MicroOp.XOR:
                self._xor(instr)
            case MicroOp.NOT:
                self._not(instr)
            case MicroOp.FABS:
                self._fabs(instr)
            case MicroOp.FCHS:
                self._fchs(instr)
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    def _and(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.AND
        if instr.is_w32():
            self._logic_32(instr, operator.and_)
        else:
            self._logic_64(instr, operator.and_)

    def _or(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.OR
        if instr.is_w32():
            self._logic_32(instr, operator.or_)
        else:
            self._logic_64(instr, operator.or_)

    def _xor(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.XOR
        if instr.is_w32():
            self._logic_32(instr, operator.xor)
        else:
            self._logic_64(instr, operator.xor)

    def _not(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.NOT
        assert instr.dst is not Reg.NONE

        wr_mask = (1 << StatusFlag.ZERO.value) | (1 << StatusFlag.SIGN.value)

        if instr.is_w32():
            self._ha_mux.select(instr.dst.value)
            a_val = self._inputs.ha_mux.read_int()
            res = (~a_val) & 0xFFFFFFFF
            result = LogicResult(
                res=res,
                zf=(res == 0),
                sf=bool(res & 0x80000000),
            )
            self._outputs.block_res.set(result.res)
            self._outputs.block_res_sel.set(instr.dst.value)
            self._outputs.exec_done.set(1)
            self._wb_flags(result, wr_mask=wr_mask)
            self._writeback()
        else:
            assert instr.dst.is_lo_half()
            # Cycle 1: invert low word
            self._ha_mux.select(instr.dst.value)
            a_lo = self._inputs.ha_mux.read_int()
            res_lo = (~a_lo) & 0xFFFFFFFF
            self._outputs.block_res.set(res_lo)
            self._outputs.block_res_sel.set(instr.dst.value)
            self._writeback()

            # Cycle 2: invert high word and commit flags
            self._ha_mux.select(instr.dst.value | 1)
            a_hi = self._inputs.ha_mux.read_int()
            res_hi = (~a_hi) & 0xFFFFFFFF
            result_64 = LogicResult(
                res=res_hi,
                zf=(res_lo == 0 and res_hi == 0),
                sf=bool(res_hi & 0x80000000),
            )
            self._outputs.block_res.set(res_hi)
            self._outputs.block_res_sel.set(instr.dst.value | 1)
            self._outputs.exec_done.set(1)
            self._wb_flags(result_64, wr_mask=wr_mask)
            self._writeback()

    def _fabs(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.FABS
        assert instr.dst is not Reg.NONE

        wr_mask = (1 << StatusFlag.ZERO.value) | (1 << StatusFlag.SIGN.value)

        if instr.is_w32():
            # 32-bit: 1 cycle, clear bit 31
            self._ha_mux.select(instr.dst.value)
            a_val = self._inputs.ha_mux.read_int()
            res = a_val & 0x7FFFFFFF
            result = LogicResult(
                res=res,
                zf=(res == 0),
                sf=False,
            )
            self._outputs.block_res.set(result.res)
            self._outputs.block_res_sel.set(instr.dst.value)
            self._outputs.exec_done.set(1)
            self._wb_flags(result, wr_mask=wr_mask)
            self._writeback()
        else:
            # 64-bit: 1 cycle, clear bit 31 of high half (bit 63 of float64)
            assert instr.dst.is_lo_half()
            self._ha_mux.select(instr.dst.value | 1)
            self._hb_mux.select(instr.dst.value)
            a_hi = self._inputs.ha_mux.read_int()
            a_lo = self._inputs.hb_mux.read_int()
            res_hi = a_hi & 0x7FFFFFFF
            result = LogicResult(
                res=res_hi,
                zf=(res_hi == 0 and a_lo == 0),
                sf=False,
            )
            self._outputs.block_res.set(res_hi)
            self._outputs.block_res_sel.set(instr.dst.value | 1)
            self._outputs.exec_done.set(1)
            self._wb_flags(result, wr_mask=wr_mask)
            self._writeback()

    def _fchs(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.FCHS
        assert instr.dst is not Reg.NONE

        # Inverts sign bit and sets STATUS.S; other flags unaffected
        wr_mask = 1 << StatusFlag.SIGN.value

        if instr.is_w32():
            # 32-bit: 1 cycle, toggle bit 31
            self._ha_mux.select(instr.dst.value)
            a_val = self._inputs.ha_mux.read_int()
            res = a_val ^ 0x80000000
            result = LogicResult(
                res=res,
                sf=bool(res & 0x80000000),
            )
            self._outputs.block_res.set(result.res)
            self._outputs.block_res_sel.set(instr.dst.value)
            self._outputs.exec_done.set(1)
            self._wb_flags(result, wr_mask=wr_mask)
            self._writeback()
        else:
            # 64-bit: 1 cycle, toggle bit 31 of high half (bit 63 of float64)
            assert instr.dst.is_lo_half()
            self._ha_mux.select(instr.dst.value | 1)
            a_hi = self._inputs.ha_mux.read_int()
            res_hi = a_hi ^ 0x80000000
            result = LogicResult(
                res=res_hi,
                sf=bool(res_hi & 0x80000000),
            )
            self._outputs.block_res.set(res_hi)
            self._outputs.block_res_sel.set(instr.dst.value | 1)
            self._outputs.exec_done.set(1)
            self._wb_flags(result, wr_mask=wr_mask)
            self._writeback()

    def _logic_core(self, op: Callable) -> LogicResult:
        a_val = self._inputs.ha_mux.read_int()
        b_val = self._inputs.hb_mux.read_int()
        res = op(a_val, b_val) & 0xFFFFFFFF
        return LogicResult(
            res=res,
            cf=False,
            zf=(res == 0),
            sf=bool(res & 0x80000000),
            vf=False,
        )

    def _logic_32(self, instr: MicroInstruction, op: Callable) -> None:
        """32-bit generic binary logic operation (1 cycle)."""
        assert instr.src is not Reg.NONE
        assert instr.dst is not Reg.NONE

        self._ha_mux.select(instr.dst.value)
        self._hb_mux.select(instr.src.value)
        result = self._logic_core(op)
        self._outputs.block_res.set(result.res)
        self._outputs.block_res_sel.set(instr.dst.value)
        self._outputs.exec_done.set(1)
        self._wb_flags(result)
        self._writeback()

    def _logic_64(self, instr: MicroInstruction, op: Callable) -> None:
        """64-bit generic binary logic operation (2 cycles)."""
        assert instr.src is not Reg.NONE
        assert instr.dst is not Reg.NONE
        assert instr.src.is_lo_half()
        assert instr.dst.is_lo_half()

        # Cycle 1: low word
        self._ha_mux.select(instr.dst.value)
        self._hb_mux.select(instr.src.value)
        result_lo = self._logic_core(op)
        self._outputs.block_res.set(result_lo.res)
        self._outputs.block_res_sel.set(instr.dst.value)
        self._writeback()

        # Cycle 2: high word
        self._ha_mux.select(instr.dst.value | 1)
        self._hb_mux.select(instr.src.value | 1)
        result_hi = self._logic_core(op)
        result_hi.zf &= result_lo.zf
        self._outputs.block_res.set(result_hi.res)
        self._outputs.block_res_sel.set(instr.dst.value | 1)
        self._outputs.exec_done.set(1)
        self._wb_flags(result_hi)
        self._writeback()

    def _wb_flags(self, result: LogicResult, wr_mask: Optional[int] = None) -> None:
        status_byte = 0
        status_byte |= int(result.cf) << StatusFlag.CARRY.value
        status_byte |= int(result.sf) << StatusFlag.SIGN.value
        status_byte |= int(result.vf) << StatusFlag.OVERFLOW.value
        status_byte |= int(result.zf) << StatusFlag.ZERO.value
        err = getattr(result, "err", False)
        status_byte |= int(err) << StatusFlag.ERR.value
        self._outputs.res_status.set(status_byte)

        if wr_mask is None:
            wr_mask = (
                (1 << StatusFlag.CARRY.value)
                | (1 << StatusFlag.SIGN.value)
                | (1 << StatusFlag.OVERFLOW.value)
                | (1 << StatusFlag.ZERO.value)
            )
        if hasattr(result, "err"):
            wr_mask |= 1 << StatusFlag.ERR.value

        self._outputs.status_wr_sel.set(wr_mask)