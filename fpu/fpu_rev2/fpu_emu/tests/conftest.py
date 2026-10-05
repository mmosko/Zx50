"""Pytest fixtures for FPGA and FPU emulator tests."""

from pathlib import Path
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.rom import Rom


@pytest.fixture
def fpga(tmp_path: Path) -> FpgaModel:
    rom = Rom(size=16, rom_path=tmp_path / "dummy.rom")
    return FpgaModel(rom=rom)
