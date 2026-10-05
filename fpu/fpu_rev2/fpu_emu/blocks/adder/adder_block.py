from typing import Callable
from unittest import case

from fpu_emu.blocks.adder.adder_core import AdderCore, AdderResult
from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


class AdderBlock(FunctionalBlock):
    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, writeback: Callable, clock: Clock):
        super().__init__(name, inputs, memory, writeback, clock)
        assert isinstance(inputs.ha_mux, Mux)
        self._ha_mux: Mux = inputs.ha_mux

    def execute(self):
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.ADD:
                self._add(instr)
            case MicroOp.ADC:
                self._adc(instr)
            case MicroOp.SUB:
                self._sub(instr)
            case MicroOp.SBB:
                self._sbb(instr)
            case MicroOp.CMP:
                self._cmp32(instr)
            case MicroOp.EXP_ADD:
                raise NotImplementedError
            case MicroOp.EXP_SUB:
                raise NotImplementedError
            case MicroOp.MOD:
                raise NotImplementedError
            case MicroOp.PACK:
                raise NotImplementedError
            case MicroOp.MUL:
                raise NotImplementedError
            case MicroOp.DIV:
                raise NotImplementedError
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    def _add(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.ADD)
        if instr.is_w32():
            self._add_32(instr, cin=0, sub=False)
        else:
            self._add_64(instr, cin=0, sub=False)

    def _adc(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.ADC)
        cin = 1 if self._inputs.status.is_bit_set(StatusFlag.CARRY) else 0
        if instr.is_w32():
            self._add_32(instr, cin=cin, sub=False)
        else:
            self._add_64(instr, cin=cin, sub=False)

    def _sub(self, instr: MicroInstruction):
        if instr.is_w32():
            self._add_32(instr, cin=0, sub=True)
        else:
            self._add_64(instr, cin=0, sub=True)

    def _sbb(self, instr: MicroInstruction):
        borrow_in = 1 if self._inputs.status.is_bit_set(StatusFlag.CARRY) else 0
        if instr.is_w32():
            self._add_32(instr, cin=borrow_in, sub=True)
        else:
            self._add_64(instr, cin=borrow_in, sub=True)

    def _combinatorial_add(self, cin: int, sub: bool) -> AdderResult:
        ha_bus = self._inputs.ha_mux.read()
        hb_bus = self._inputs.hb_mux.read()
        return AdderCore.adder_core(a=ha_bus, b=hb_bus, cin=cin, sub=sub)

    def _add_32(self, instr: MicroInstruction, cin: int, sub: bool) -> None:
        """
        32-bit Add with carry

            instr.dst <- instr.dst - instr.src

        This allows 32-bit math on EA, EB, and C, in addition to AL or AH

        :param instr:
        :param cin:
        :param sub:
        :return:
        """
        assert (instr.src is not Reg.NONE)
        assert (instr.dst is not Reg.NONE)

        # Combinatorial setup in current cycle
        self._ha_mux.select(instr.dst.value)
        self._inputs.hb_mux.select(instr.src.value)
        adder_result = self._combinatorial_add(cin=cin, sub=sub)

        # Writeback AL (edge-triggered tick in writeback)
        self._outputs.block_res.set(adder_result.res)
        self._outputs.block_res_sel.set(instr.dst.value)
        self._wb_flags(adder_result)
        self._writeback()

    def _add_64(self, instr: MicroInstruction, cin: int, sub: bool) -> None:
        """ADD AX, src: 64-bit addition with carry (2 cycles)."""
        assert (instr.src is not Reg.NONE)
        self._validate_src64(instr.src)

        # Low word (AL)
        self._ha_mux.select(Reg.AL.value)
        self._inputs.hb_mux.select(instr.src.value)
        low_result = self._combinatorial_add(cin=cin, sub=sub)

        # Writeback AL (status write disabled for intermediate low word)
        self._outputs.status_wr_sel.set(0)
        self._outputs.block_res.set(low_result.res)
        self._outputs.block_res_sel.set(Reg.AL.value)
        self._writeback()

        # Upper word (AH) with carry from lower word
        cin_high = 1 if low_result.cf else 0
        self._ha_mux.select(Reg.AH.value)
        src_h = instr.src.value | 0b0001
        self._inputs.hb_mux.select(src_h)
        high_result = self._combinatorial_add(cin=cin_high, sub=sub)

        # Writeback AH and commit final status flags (ZF is 1 only if both halves are zero)
        final_result = AdderResult(
            res=high_result.res,
            cf=high_result.cf,
            zf=low_result.zf and high_result.zf,
            sf=high_result.sf,
            vf=high_result.vf,
        )
        self._wb_flags(final_result)
        self._outputs.block_res.set(high_result.res)
        self._outputs.block_res_sel.set(Reg.AH.value)
        self._writeback()

    @staticmethod
    def _validate_src64(src: Reg):
        # must be the low word of a 64-bit pair
        assert(src in [Reg.AL, Reg.BL, Reg.DL, Reg.FL])

    def _cmp32(self, instr: MicroInstruction):
        """CMP dst, src: 32-bit compare dst - src without modifying dst (1 cycle)."""
        assert (instr.src is not None)
        assert (instr.dst is not None)
        self._ha_mux.select(instr.dst.value)
        self._inputs.hb_mux.select(instr.src.value)
        adder_result = self._combinatorial_add(cin=0, sub=True)

        self._outputs.block_res_sel.set(Reg.NONE.value)  # No register writeback
        self._wb_flags(adder_result)
        self._writeback()

    def _wb_flags(self, result: AdderResult):
        status_byte = 0
        status_byte |= result.cf << StatusFlag.CARRY.value
        status_byte |= result.sf << StatusFlag.SIGN.value
        status_byte |= result.vf << StatusFlag.OVERFLOW.value
        status_byte |= result.zf << StatusFlag.ZERO.value
        self._outputs.res_status.set(status_byte)

        status_wr_select = (1 << StatusFlag.CARRY.value) | \
                           (1 << StatusFlag.SIGN.value) | \
                           (1 << StatusFlag.OVERFLOW.value) | \
                           (1 << StatusFlag.ZERO.value)

        self._outputs.status_wr_sel.set(status_wr_select)

