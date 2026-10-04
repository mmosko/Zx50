"""Unit tests for FpgaModel."""

from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware import Hardware
from fpu_emu.alu.alu import Alu


def test_fpga_model_init_and_properties():
    model = FpgaModel()
    assert isinstance(model.hw, Hardware)
    assert isinstance(model.alu, Alu)
    assert model.reg is model.hw.reg
    assert model.mem is model.hw.mem
    assert model.clock is model.hw.clock
