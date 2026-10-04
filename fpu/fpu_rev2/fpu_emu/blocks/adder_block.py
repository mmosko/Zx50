from typing import Tuple

from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.reg import Reg
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


class AdderBlock(FunctionalBlock):
    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, clock: Clock, **kwargs):
        super().__init__(name, inputs, memory, clock)

    def execute(self):
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.ADD:
                pass
            case MicroOp.ADC:
                pass
            case MicroOp.SUB:
                pass
            case MicroOp.SBB:
                pass
            case MicroOp.MUL:
                pass

    def _add(self, instr):
        if instr.is_w32():
            self._add_32(instr)
        else:
            self._add_64(instr)

    def _add_32(self, instr: MicroInstruction) -> None:
        """32-bit Add without carry"""
        assert(instr.op == MicroOp.ADD)
        assert(instr.src is not None)

        # This is all combinatorial in the current clock tick

        self._inputs.ha_mux.select(Reg.AL.value)
        self._inputs.hb_mux.select(instr.src.value)
        ha_bus = self._inputs.ha_mux.read()
        hb_bus = self._inputs.hb_mux.read()
        res, cf, zf, sf, vf = self.adder_core(a=ha_bus, b=hb_bus, cin=0)

        self._outputs.block_res.set(res)
        self._outputs.block_res_sel.set(Reg.AL.value.to_bytes(1, 'big'))

        # TODO: map the cf, zf, sf, vf to the status word
        self._outputs.res_status.set(b'0x00')
        # TODO: set the bitmask to write
        self._outputs.status_wr_sel.set(b'0x00')

        self._clock.tick(1)
        # TODO: Execute the write back
        return

    def _add_64(self, instr):
        raise NotImplementedError

    @classmethod
    def adder_core(cls, a: bytes, b: bytes, cin: int = 0, sub: bool = False) -> Tuple[bytearray, bool, bool, bool, bool]:
        """Pure 32-bit carry-lookahead/ripple adder-subtractor core.

        Models MachXO2 CCU2C dedicated carry chains connected directly to HA_BUS and HB_BUS.

        :param hw: Hardware instance holding registers and datapath buses
        :param cin: Carry-in (0 or 1) for addition; Borrow-in (0 or 1) for subtraction
        :param sub: True for subtraction (HA - HB - cin), False for addition (HA + HB + cin)
        :return: (result, carry_borrow_out, zf, sf, vf)
        """

        if len(a) != 4 or len(b) != 4:
            raise ValueError(f"Operands must be 4 bytes each, got len(a)={len(a)}, len(b)={len(b)}")

        res = bytearray(4)

        # In two's-complement subtraction: A - B - borrow = A + (~B) + (1 - borrow)
        carry = (0 if cin else 1) if sub else cin

        for i in range(4):
            b_val = (b[i] ^ 0xFF) if sub else b[i]
            temp = a[i] + b_val + carry
            res[i] = temp & 0xFF
            carry = (temp >> 8) & 1

        # Zero flag: all 32 bits are 0
        zf = res == b"\x00\x00\x00\x00"

        # Sign flag: bit 31 of result is 1
        sf = bool(res[3] & 0x80)

        a_msb = bool(a[3] & 0x80)
        b_msb = bool(b[3] & 0x80)
        r_msb = sf

        if sub:
            # Borrow out: carry == 0 means borrow occurred (A < B + borrow_in)
            cf = carry == 0
            # Two's complement signed overflow on subtraction:
            # Occurs when operands have different signs and result sign differs from A
            vf = (a_msb != b_msb) and (a_msb != r_msb)
        else:
            # Unsigned carry out of MSB
            cf = bool(carry)
            # Two's complement signed overflow on addition:
            # Occurs when operands have same sign and result sign differs from inputs
            vf = (a_msb == b_msb) and (a_msb != r_msb)

        return res, cf, zf, sf, vf
