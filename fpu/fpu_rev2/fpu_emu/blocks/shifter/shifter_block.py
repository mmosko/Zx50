from dataclasses import dataclass
from typing import Callable

from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.blocks.shifter.barrel_shifter import BarrelShifter, ShiftResult
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
    approach="Shifter controller, sequencer, and pipeline registers",
    luts=16,
    ffs=42,
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
        assert instr.op == MicroOp.LSL
        if instr.is_w32():
            self._shift_32(instr, BarrelShifter.lsl_32)
        else:
            self._shift_64(instr, BarrelShifter.lsl_64)

    def _lsr(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.LSR
        if instr.is_w32():
            self._shift_32(instr, BarrelShifter.lsr_32)
        else:
            self._shift_64(instr, BarrelShifter.lsr_64)

    def _shift_32(self, instr: MicroInstruction, shift_fn: Callable[[int, int, ShifterAdder], ShiftResult]) -> None:
        assert instr.dst is not Reg.NONE, "Shift destination register must be specified"
        src = instr.src if instr.src is not Reg.NONE else Reg.C
        dst = instr.dst

        # Read shift count from HA_MUX (src or C)
        self._ha_mux.select(src.value)
        count = self._inputs.ha_mux.read_int() & 0x3F

        # Read operand from HB_MUX (dst)
        self._hb_mux.select(dst.value)
        val = self._inputs.hb_mux.read_int() & 0xFFFFFFFF

        shift_res = shift_fn(val, count, self._sub_adder)

        wr_mask = (
            (1 << StatusFlag.ZERO.value)
            | (1 << StatusFlag.SIGN.value)
            | (1 << StatusFlag.CARRY.value)
        )
        status_val = (
            (int(shift_res.zf) << StatusFlag.ZERO.value)
            | (int(shift_res.sf) << StatusFlag.SIGN.value)
            | (int(shift_res.cf) << StatusFlag.CARRY.value)
        )

        self._outputs.block_res.set(shift_res.res)
        self._outputs.block_res_sel.set(dst.value)
        self._outputs.res_status.set(status_val)
        self._outputs.status_wr_sel.set(wr_mask)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _shift_64(self, instr: MicroInstruction, shift_fn: Callable[[int, int, ShifterAdder], ShiftResult]) -> None:
        assert instr.dst is not Reg.NONE, "Shift destination register must be specified"
        assert instr.dst.is_lo_half(), f"64-bit shift destination must be low-half register, got {instr.dst}"
        src = instr.src if instr.src is not Reg.NONE else Reg.C
        dst = instr.dst

        # Cycle 1: Latch shift count from HA_MUX and low half from HB_MUX
        self._ha_mux.select(src.value)
        count = self._inputs.ha_mux.read_int() & 0x3F

        self._hb_mux.select(dst.value)
        val_lo = self._inputs.hb_mux.read_int() & 0xFFFFFFFF

        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.status_wr_sel.set(0)
        self._outputs.exec_done.set(0)
        self._writeback()

        # Cycle 2: Read high half from HB_MUX, compute 64-bit shift, write low half
        self._hb_mux.select(dst.value | 1)
        val_hi = self._inputs.hb_mux.read_int() & 0xFFFFFFFF

        val_64 = (val_hi << 32) | val_lo
        shift_res = shift_fn(val_64, count, self._sub_adder)

        self._outputs.block_res.set(shift_res.res & 0xFFFFFFFF)
        self._outputs.block_res_sel.set(dst.value)
        self._outputs.status_wr_sel.set(0)
        self._outputs.exec_done.set(0)
        self._writeback()

        # Cycle 3: Write high half and commit status flags
        wr_mask = (
            (1 << StatusFlag.ZERO.value)
            | (1 << StatusFlag.SIGN.value)
            | (1 << StatusFlag.CARRY.value)
        )
        status_val = (
            (int(shift_res.zf) << StatusFlag.ZERO.value)
            | (int(shift_res.sf) << StatusFlag.SIGN.value)
            | (int(shift_res.cf) << StatusFlag.CARRY.value)
        )

        self._outputs.block_res.set((shift_res.res >> 32) & 0xFFFFFFFF)
        self._outputs.block_res_sel.set(dst.value | 1)
        self._outputs.res_status.set(status_val)
        self._outputs.status_wr_sel.set(wr_mask)
        self._outputs.exec_done.set(1)
        self._writeback()

