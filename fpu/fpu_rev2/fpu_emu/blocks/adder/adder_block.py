from typing import Callable

from fpu_emu.blocks.adder.adder_core import AdderCore, AdderResult
from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


class AdderBlock(FunctionalBlock):
    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, writeback: Callable, clock: Clock, **kwargs):
        super().__init__(name, inputs, memory, writeback, clock)

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
                raise NotImplementedError
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
            self._add_32(instr, cin=0, sub=True)

    def _sbb(self, instr: MicroInstruction):
        borrow_in = 1 if self._inputs.status.is_bit_set(StatusFlag.CARRY) else 0
        if instr.is_w32():
            self._add_32(instr, cin=borrow_in, sub=True)
        else:
            self._add_32(instr, cin=borrow_in, sub=True)

    def _combinatorial_add(self, cin: int, sub: bool) -> AdderResult:
        ha_bus = self._inputs.ha_mux.read()
        hb_bus = self._inputs.hb_mux.read()
        return AdderCore.adder_core(a=ha_bus, b=hb_bus, cin=cin, sub=sub)

        self._outputs.block_res.set(adder_result.res)
        self._outputs.block_res_sel.set(Reg.AL.value.to_bytes(1, 'big'))

    def _add_32(self, instr: MicroInstruction, cin: int, sub: bool) -> None:
        """32-bit Add with carry"""
        assert (instr.src is not None)

        # This is all combinatorial in the current clock tick

        self._inputs.ha_mux.select(Reg.AL.value)
        self._inputs.hb_mux.select(instr.src.value)
        adder_result = self._combinatorial_add(cin=cin, sub=sub)
        self._clock.tick(1)

        # Writeback AL (implicit tick)
        self._outputs.block_res.set(adder_result.res)
        self._outputs.block_res_sel.set(Reg.AL.value.to_bytes(1, 'big'))
        self._wb_flags(adder_result)
        self._writeback()

        return

    def _add_64(self, instr: MicroInstruction, cin: int, sub: bool) -> None:
        """ADC AX, src: 64-bit addition with carry (2 cycles)."""
        assert (instr.src is not None)
        self._validate_src64(instr.src)

        self._inputs.ha_mux.select(Reg.AL.value)
        self._inputs.hb_mux.select(instr.src.value)
        adder_result = self._combinatorial_add(cin=cin, sub=sub)
        self._clock.tick(1)

        # Writeback AL (implicit tick)
        # If we latch the result, this could be done in parallel with the upper word
        self._outputs.status_wr_sel.set(b'0x00')
        self._outputs.block_res.set(adder_result.res)
        self._outputs.block_res_sel.set(Reg.AL.value.to_bytes(1, 'big'))
        self._writeback()

        # Upper word
        self._inputs.ha_mux.select(Reg.AH.value)
        src_h = instr.src.value | 0b0001
        self._inputs.hb_mux.select(src_h)
        adder_result = self._combinatorial_add(cin=cin, sub=sub)
        self._clock.tick(1)

        # Writeback AH (implicit tick)
        self._wb_flags(adder_result)
        self._outputs.block_res.set(adder_result.res)
        self._outputs.block_res_sel.set(Reg.AH.value.to_bytes(1, 'big'))
        self._writeback()

    @staticmethod
    def _validate_src64(src: Reg):
        # must be the low word of a 64-bit pair
        assert(src in [Reg.AL, Reg.BL, Reg.DL, Reg.FL])

    def cmp32(self, instr: MicroInstruction):
        """CMP AL, src: 32-bit compare AL - src without modifying AL (1 cycle)."""
        assert (instr.src is not None)
        self._inputs.ha_mux.select(Reg.AL.value)
        self._inputs.hb_mux.select(instr.src.value)
        adder_result = self._combinatorial_add(cin=0, sub=True)

        self._clock.tick(1)
        self._wb_flags(adder_result)

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

