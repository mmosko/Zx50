from pathlib import Path

import pytest

from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


@pytest.fixture
def fpga(tmp_path: Path):
    rom = Rom(size=16, rom_path=tmp_path / "dummy.rom")
    return FpgaModel(rom=rom)


def test_push_basic(fpga: FpgaModel):
    """PUSH AL should write to EBR and increment SP by 1, clearing ERR/VF."""
    fpga.reg_file.al.write(0x12345678)
    assert fpga.reg_file.sp.read_int() == 0

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
    ]

    fpga.dispatcher._run(microcode)

    # SP should now be 1
    assert fpga.reg_file.sp.read_int() == 1

    # EBR 0 has lower 16 bits, EBR 1 has upper 16 bits
    assert fpga.memory.read(0, 0) == 0x5678
    assert fpga.memory.read(1, 0) == 0x1234

    # Status flags VF and ERR should be clear
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_push_multiple(fpga: FpgaModel):
    """Multiple sequential PUSH instructions."""
    fpga.reg_file.al.write(0xAAAAAAAA)
    fpga.reg_file.bl.write(0xBBBBBBBB)
    fpga.reg_file.dl.write(0xCCCCCCCC)

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
        MicroInstruction(op=MicroOp.PUSH, src=Reg.BL),
        MicroInstruction(op=MicroOp.PUSH, src=Reg.DL),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == 3

    assert fpga.memory.read(0, 0) == 0xAAAA
    assert fpga.memory.read(1, 0) == 0xAAAA

    fpga.clock.tick(1)
    assert fpga.memory.read(0, 1) == 0xBBBB
    assert fpga.memory.read(1, 1) == 0xBBBB

    fpga.clock.tick(1)
    assert fpga.memory.read(0, 2) == 0xCCCC
    assert fpga.memory.read(1, 2) == 0xCCCC


def test_push_overflow(fpga: FpgaModel):
    """PUSH when SP=127 should assert OVERFLOW and ERR, without updating SP or memory."""
    # Set SP to max value (127)
    fpga.reg_file.sp.write(127)
    fpga.reg_file.al.write(0xDEADBEEF)

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
    ]

    fpga.dispatcher._run(microcode)

    # SP should remain clamped at 127
    assert fpga.reg_file.sp.read_int() == 127

    # Memory at address 127 should NOT have been written
    assert fpga.memory.read(0, 127) == 0
    assert fpga.memory.read(1, 127) == 0

    # Status flags should indicate overflow and error
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_push_clears_previous_overflow(fpga: FpgaModel):
    """A successful PUSH clears previously raised OVERFLOW and ERR flags."""
    fpga.reg_file.status.set_bit(StatusFlag.OVERFLOW, True)
    fpga.reg_file.status.set_bit(StatusFlag.ERR, True)
    fpga.reg_file.sp.write(0)
    fpga.reg_file.al.write(0x42)

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
