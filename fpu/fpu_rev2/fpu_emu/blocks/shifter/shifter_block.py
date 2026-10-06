from dataclasses import dataclass
from typing import Callable

from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.blocks.shifter.priority_encoder import PriorityEncoder32
from fpu_emu.blocks.shifter.shifter_adder import ShifterAdder
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


@dataclass
class ShifterResult:
    """Result of a shifter block operation."""

    res: int  # 32-bit integer result
    cf: bool = False
    zf: bool = False
    sf: bool = False
    vf: bool = False


@fpga_resource(
    approach="Shifter controller and sequencer",
    luts=4,
    ffs=4,
    delay_ns=2.4,
    cycles=1,
    shared_unit="shifter_block",
)
class ShifterBlock(FunctionalBlock):
    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, writeback: Callable, clock: Clock):
        super().__init__(name, inputs, memory, writeback, clock)
        assert isinstance(inputs.ha_mux, Mux)
        assert isinstance(inputs.hb_mux, Mux)
        self._ha_mux: Mux = inputs.ha_mux
        self._hb_mux: Mux = inputs.hb_mux
        self._sub_adder: ShifterAdder = ShifterAdder("shifter_sub_adder")
        self._add_adder: ShifterAdder = ShifterAdder("shifter_add_adder")

    def execute(self):
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.LZC:
                self._lzc(instr)
            case MicroOp.LSL:
                self._lsl(instr)
            case MicroOp.LSR:
                self._lsr(instr)
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    def _lzc(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.LZC
        if instr.is_w32():
            self._lzc_32(instr)
        else:
            self._lzc_64(instr)

    def _lzc_32(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not Reg.NONE else Reg.AL
        dst = instr.dst if instr.dst is not Reg.NONE else Reg.C

        self._hb_mux.select(src.value)
        val = self._inputs.hb_mux.read_int() & 0xFFFFFFFF

        enc = PriorityEncoder32.encode(val)
        if not enc.valid:
            count = 32
            zf = True
        else:
            # 5-bit subtraction (31 - bit_pos) using dedicated shifter subtractor
            count = self._sub_adder.sub(31, enc.bit_pos)
            zf = False

        self._outputs.block_res.set(count)
        self._outputs.block_res_sel.set(dst.value)
        self._outputs.res_status.set(int(zf) << StatusFlag.ZERO.value)
        self._outputs.status_wr_sel.set(1 << StatusFlag.ZERO.value)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _lzc_64(self, instr: MicroInstruction) -> None:
        src = instr.src if instr.src is not Reg.NONE else Reg.AL
        dst = instr.dst if instr.dst is not Reg.NONE else Reg.C
        assert src.is_lo_half(), f"64-bit LZC source must be low-half register, got {src}"

        # Cycle 1: Read high half (src | 1)
        src_hi = src.value | 1
        self._hb_mux.select(src_hi)
        val_hi = self._inputs.hb_mux.read_int() & 0xFFFFFFFF

        enc_hi = PriorityEncoder32.encode(val_hi)
        if enc_hi.valid:
            hi_zeros = self._sub_adder.sub(31, enc_hi.bit_pos)
        else:
            hi_zeros = 0

        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.status_wr_sel.set(0)
        self._outputs.exec_done.set(0)
        self._writeback()

        # Cycle 2: Read low half (src)
        src_lo = src.value
        self._hb_mux.select(src_lo)
        val_lo = self._inputs.hb_mux.read_int() & 0xFFFFFFFF

        if enc_hi.valid:
            count = hi_zeros
            zf = False
        else:
            enc_lo = PriorityEncoder32.encode(val_lo)
            if enc_lo.valid:
                # Two separate dedicated adders in the same clock cycle:
                # 1) _sub_adder computes (31 - bit_pos)
                # 2) _add_adder computes (32 + lo_zeros)
                lo_zeros = self._sub_adder.sub(31, enc_lo.bit_pos)
                count = self._add_adder.add(32, lo_zeros)
                zf = False
            else:
                count = 64
                zf = True

        if dst.is_lo_half():
            # Cycle 2 writes count to dst low word
            self._outputs.block_res.set(count)
            self._outputs.block_res_sel.set(dst.value)
            self._outputs.status_wr_sel.set(0)
            self._outputs.exec_done.set(0)
            self._writeback()

            # Cycle 3 writes 0 to dst high word and commits status
            self._outputs.block_res.set(0)
            self._outputs.block_res_sel.set(dst.value | 1)
            self._outputs.res_status.set(int(zf) << StatusFlag.ZERO.value)
            self._outputs.status_wr_sel.set(1 << StatusFlag.ZERO.value)
            self._outputs.exec_done.set(1)
            self._writeback()
        else:
            # Scalar destination (e.g. Reg.C) completes in Cycle 2
            self._outputs.block_res.set(count)
            self._outputs.block_res_sel.set(dst.value)
            self._outputs.res_status.set(int(zf) << StatusFlag.ZERO.value)
            self._outputs.status_wr_sel.set(1 << StatusFlag.ZERO.value)
            self._outputs.exec_done.set(1)
            self._writeback()

    def _lsl(self, instr: MicroInstruction) -> None:
        raise NotImplementedError("LSL is not yet implemented")

    def _lsr(self, instr: MicroInstruction) -> None:
        raise NotImplementedError("LSR is not yet implemented")

