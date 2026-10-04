"""Top-level FPGA system model."""

from fpu_emu.hardware import Hardware
from fpu_emu.alu.alu import Alu


class FpgaModel:
    """Complete FPGA system model combining Hardware, ALU, Sequencer, and Host Interface."""

    def __init__(self):
        self.hw = Hardware()
        self.alu = Alu(self.hw)

    @property
    def reg(self):
        return self.hw.reg

    @property
    def mem(self):
        return self.hw.mem

    @property
    def clock(self):
        return self.hw.clock
