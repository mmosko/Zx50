"""Unit tests for ShifterBlock operations (LZC, LSL, LSR)."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


def run_shifter(fpga: FpgaModel, instr: MicroInstruction) -> int:
    """Helper to set up instruction, route writeback mux, and execute shifter block.

    Returns the number of clock cycles elapsed during execution.
    """
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.writeback_mux.set_block((instr.op.value >> 3) & 0x07)
    clk_start = fpga.clock.cycles
    fpga.shifter_block.execute()
    return fpga.clock.cycles - clk_start


# ==============================================================================
# 32-bit LZC Unit Tests
# ==============================================================================


def test_lzc_32_msb_set(fpga: FpgaModel):
    """AL = 0x80000000 -> 0 leading zeros, ZF = False, C = 0."""
    fpga.reg_file.al.write(0x80000000)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W32, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.c.read_int() == 0
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_32_systemref_example(fpga: FpgaModel):
    """SystemReference.md example: AL = 0x00080000 -> 12 leading zeros, C = 12."""
    fpga.reg_file.al.write(0x00080000)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W32, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.c.read_int() == 12
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_32_lsb_set(fpga: FpgaModel):
    """AL = 0x00000001 -> 31 leading zeros, C = 31."""
    fpga.reg_file.al.write(0x00000001)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W32, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.c.read_int() == 31
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_32_zero(fpga: FpgaModel):
    """AL = 0x00000000 -> 32 leading zeros, ZF = True, C = 32."""
    fpga.reg_file.al.write(0x00000000)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W32, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.c.read_int() == 32
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_32_default_registers(fpga: FpgaModel):
    """When src and dst are omitted (Reg.NONE), defaults to src=AL and dst=C."""
    fpga.reg_file.al.write(0x00000080)  # bit 7 -> 24 leading zeros

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W32)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.c.read_int() == 24
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_32_dst_register_override(fpga: FpgaModel):
    """Writing LZC result to a general register (e.g. BL) instead of C."""
    fpga.reg_file.al.write(0x00000004)  # bit 2 -> 29 leading zeros

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W32, dst=Reg.BL, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.bl.read_int() == 29
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_32_src_register_override(fpga: FpgaModel):
    """Counting leading zeros of BL instead of AL."""
    fpga.reg_file.bl.write(0x40000000)  # bit 30 -> 1 leading zero

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W32, dst=Reg.C, src=Reg.BL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.c.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_32_preserves_unrelated_flags(fpga: FpgaModel):
    """Only ZERO flag is modified; CARRY, SIGN, OVERFLOW, etc. are untouched."""
    fpga.reg_file.status.set_bit(StatusFlag.CARRY, True)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, True)
    fpga.reg_file.status.set_bit(StatusFlag.OVERFLOW, True)
    fpga.reg_file.status.set_bit(StatusFlag.DIFF_SIGN, True)

    fpga.reg_file.al.write(0x00000000)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W32, dst=Reg.C, src=Reg.AL)
    run_shifter(fpga, instr)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.DIFF_SIGN)


# ==============================================================================
# 64-bit LZC Unit Tests
# ==============================================================================


def test_lzc_64_msb_set(fpga: FpgaModel):
    """AX = {AH=0x80000000, AL=0x00000000} -> 0 leading zeros, C = 0."""
    fpga.reg_file.ah.write(0x80000000)
    fpga.reg_file.al.write(0x00000000)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W64, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.c.read_int() == 0
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_64_high_word_nonzero(fpga: FpgaModel):
    """AX = {AH=0x00080000, AL=0x12345678} -> 12 leading zeros, C = 12."""
    fpga.reg_file.ah.write(0x00080000)
    fpga.reg_file.al.write(0x12345678)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W64, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.c.read_int() == 12
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_64_boundary_bit31(fpga: FpgaModel):
    """AX = {AH=0x00000000, AL=0x80000000} -> bit 31 set -> 32 leading zeros, C = 32."""
    fpga.reg_file.ah.write(0x00000000)
    fpga.reg_file.al.write(0x80000000)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W64, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.c.read_int() == 32
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_64_low_word_nonzero(fpga: FpgaModel):
    """AX = {AH=0x00000000, AL=0x00080000} -> 32 + 12 = 44 leading zeros, C = 44."""
    fpga.reg_file.ah.write(0x00000000)
    fpga.reg_file.al.write(0x00080000)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W64, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.c.read_int() == 44
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_64_lsb_set(fpga: FpgaModel):
    """AX = {AH=0x00000000, AL=0x00000001} -> bit 0 set -> 63 leading zeros, C = 63."""
    fpga.reg_file.ah.write(0x00000000)
    fpga.reg_file.al.write(0x00000001)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W64, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.c.read_int() == 63
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_64_zero(fpga: FpgaModel):
    """AX = {AH=0x00000000, AL=0x00000000} -> 64 leading zeros, ZF = True."""
    fpga.reg_file.ah.write(0x00000000)
    fpga.reg_file.al.write(0x00000000)

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W64, dst=Reg.C, src=Reg.AL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 2
    # C is a 6-bit register (0..63), 64 & 0x3F = 0
    assert fpga.reg_file.c.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_lzc_64_dst_pair(fpga: FpgaModel):
    """Writing 64-bit LZC result into a 64-bit pair (e.g. AX from BX source)."""
    fpga.reg_file.bh.write(0x00000000)
    fpga.reg_file.bl.write(0x00000008)  # bit 3 set -> 64 - 4 = 60 leading zeros

    instr = MicroInstruction(op=MicroOp.LZC, w=IW.W64, dst=Reg.AL, src=Reg.BL)
    elapsed = run_shifter(fpga, instr)

    assert elapsed == 3
    assert fpga.reg_file.al.read_int() == 60
    assert fpga.reg_file.ah.read_int() == 0
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
