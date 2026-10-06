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


def get_reg(fpga: FpgaModel, reg: Reg):
    return getattr(fpga.reg_file, reg.name.lower())


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


@pytest.mark.parametrize(
    "src,dst,val,desc",
    [
        (Reg.AL, Reg.BL, 0x12345678, "standard 32-bit value AL -> BL"),
        (Reg.BL, Reg.DL, 0x00000000, "zero value BL -> DL"),
        (Reg.DL, Reg.FL, 0xFFFFFFFF, "all ones DL -> FL"),
        (Reg.FL, Reg.AL, 0x80000000, "sign bit set FL -> AL"),
        (Reg.AH, Reg.BH, 0x5555AAAA, "high-half registers AH -> BH"),
        (Reg.EA, Reg.EB, 0x0ABC, "12-bit register EA -> EB"),
    ],
)
def test_push_pop_32_roundtrip(fpga: FpgaModel, src, dst, val, desc):
    """Test 32-bit PUSH and POP preserves values across various registers."""
    get_reg(fpga, src).write(val)
    initial_sp = fpga.reg_file.sp.read_int()

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=src, w=IW.W32),
        MicroInstruction(op=MicroOp.POP, dst=dst, w=IW.W32),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == initial_sp
    assert get_reg(fpga, dst).read_int() == val
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


@pytest.mark.parametrize(
    "src_lo,dst_lo,val_lo,val_hi,desc",
    [
        (Reg.AL, Reg.BL, 0x11112222, 0x33334444, "AX -> BX standard 64-bit pair"),
        (Reg.BL, Reg.DL, 0x00000000, 0x00000000, "BX -> DX zeros"),
        (Reg.DL, Reg.FL, 0xFFFFFFFF, 0xFFFFFFFF, "DX -> FX all ones"),
        (Reg.FL, Reg.AL, 0x12345678, 0x9ABCDEF0, "FX -> AX distinct half-words"),
    ],
)
def test_push_pop_64_roundtrip(fpga: FpgaModel, src_lo, dst_lo, val_lo, val_hi, desc):
    """Test 64-bit PUSH and POP preserves values across 64-bit register pairs."""
    src_hi = Reg(src_lo.value | 1)
    dst_hi = Reg(dst_lo.value | 1)

    get_reg(fpga, src_lo).write(val_lo)
    get_reg(fpga, src_hi).write(val_hi)
    initial_sp = fpga.reg_file.sp.read_int()

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=src_lo, w=IW.W64),
        MicroInstruction(op=MicroOp.POP, dst=dst_lo, w=IW.W64),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == initial_sp
    assert get_reg(fpga, dst_lo).read_int() == val_lo
    assert get_reg(fpga, dst_hi).read_int() == val_hi
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_pop32_underflow(fpga: FpgaModel):
    """POP when SP=0 should assert UNDERFLOW and ERR, without altering SP or dst."""
    fpga.reg_file.bl.write(0xCAFEBABE)
    assert fpga.reg_file.sp.read_int() == 0

    microcode = [
        MicroInstruction(op=MicroOp.POP, dst=Reg.BL, w=IW.W32),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.bl.read_int() == 0xCAFEBABE
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_pop64_underflow_empty(fpga: FpgaModel):
    """64-bit POP when SP=0 asserts UNDERFLOW and ERR; neither dst register is modified."""
    fpga.reg_file.bl.write(0x11111111)
    fpga.reg_file.bh.write(0x22222222)
    assert fpga.reg_file.sp.read_int() == 0

    microcode = [
        MicroInstruction(op=MicroOp.POP, dst=Reg.BL, w=IW.W64),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.bl.read_int() == 0x11111111
    assert fpga.reg_file.bh.read_int() == 0x22222222
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_pop64_underflow_one_item(fpga: FpgaModel):
    """64-bit POP when SP=1 pops HI word into BH, but underflows on LO word (BL untouched)."""
    fpga.reg_file.al.write(0x55556666)
    fpga.reg_file.bl.write(0xAAAAAAAA)
    fpga.reg_file.bh.write(0xBBBBBBBB)

    # Push 1 32-bit word, so SP becomes 1
    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL, w=IW.W32),
        MicroInstruction(op=MicroOp.POP, dst=Reg.BL, w=IW.W64),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.bh.read_int() == 0x55556666  # Hi word popped from TOS
    assert fpga.reg_file.bl.read_int() == 0xAAAAAAAA  # Lo word untouched on underflow
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_push64_overflow_at_127(fpga: FpgaModel):
    """64-bit PUSH when SP=127 overflows on word 1; memory and SP untouched."""
    fpga.reg_file.sp.write(127)
    fpga.reg_file.al.write(0x12345678)
    fpga.reg_file.ah.write(0x9ABCDEF0)

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL, w=IW.W64),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == 127
    assert fpga.memory.read(0, 127) == 0
    assert fpga.memory.read(1, 127) == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_push64_overflow_at_126(fpga: FpgaModel):
    """64-bit PUSH when SP=126 pushes word 1 at 126, but overflows on word 2 at 127."""
    fpga.reg_file.sp.write(126)
    fpga.reg_file.al.write(0x12345678)
    fpga.reg_file.ah.write(0x9ABCDEF0)

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL, w=IW.W64),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.sp.read_int() == 127  # Incremented once by low word
    assert fpga.memory.read(0, 126) == 0x5678  # Low word was written
    assert fpga.memory.read(1, 126) == 0x1234
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_pop32_clears_previous_underflow(fpga: FpgaModel):
    """A successful 32-bit POP clears previously asserted UNDERFLOW and ERR flags."""
    fpga.reg_file.status.set_bit(StatusFlag.UNDERFLOW, True)
    fpga.reg_file.status.set_bit(StatusFlag.ERR, True)
    fpga.reg_file.al.write(0x1234)

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL, w=IW.W32),
        MicroInstruction(op=MicroOp.POP, dst=Reg.BL, w=IW.W32),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.bl.read_int() == 0x1234
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_pop64_clears_previous_underflow(fpga: FpgaModel):
    """A successful 64-bit POP clears previously asserted UNDERFLOW and ERR flags."""
    fpga.reg_file.status.set_bit(StatusFlag.UNDERFLOW, True)
    fpga.reg_file.status.set_bit(StatusFlag.ERR, True)
    fpga.reg_file.al.write(0x11112222)
    fpga.reg_file.ah.write(0x33334444)

    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=Reg.AL, w=IW.W64),
        MicroInstruction(op=MicroOp.POP, dst=Reg.BL, w=IW.W64),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.bl.read_int() == 0x11112222
    assert fpga.reg_file.bh.read_int() == 0x33334444
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


@pytest.mark.parametrize(
    "invalid_reg",
    [Reg.AH, Reg.BH, Reg.DH, Reg.FH, Reg.EA, Reg.EB, Reg.IMM, Reg.C],
)
def test_push64_invalid_src_raises(fpga: FpgaModel, invalid_reg):
    """PUSH64 requires a low-half register (AL, BL, DL, FL); others raise AssertionError."""
    microcode = [
        MicroInstruction(op=MicroOp.PUSH, src=invalid_reg, w=IW.W64),
    ]
    with pytest.raises(AssertionError):
        fpga.dispatcher._run(microcode)


@pytest.mark.parametrize(
    "invalid_reg",
    [Reg.AH, Reg.BH, Reg.DH, Reg.FH, Reg.EA, Reg.EB, Reg.IMM, Reg.C],
)
def test_pop64_invalid_dst_raises(fpga: FpgaModel, invalid_reg):
    """POP64 requires a low-half register (AL, BL, DL, FL); others raise AssertionError."""
    microcode = [
        MicroInstruction(op=MicroOp.POP, dst=invalid_reg, w=IW.W64),
    ]
    with pytest.raises(AssertionError):
        fpga.dispatcher._run(microcode)


def test_mov_32(fpga: FpgaModel):
    """MOV copies 32-bit register without affecting flags."""
    fpga.reg_file.bl.write(0xDEADBEEF)
    microcode = [
        MicroInstruction(op=MicroOp.MOV, dst=Reg.AL, src=Reg.BL),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.al.read_int() == 0xDEADBEEF


def test_mov_64(fpga: FpgaModel):
    """MOV copies 64-bit register pair (LO then HI) without affecting flags."""
    fpga.reg_file.bl.write(0x12345678)
    fpga.reg_file.bh.write(0x9ABCDEF0)
    microcode = [
        MicroInstruction(op=MicroOp.MOV, dst=Reg.DL, src=Reg.BL, w=IW.W64),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.dl.read_int() == 0x12345678
    assert fpga.reg_file.dh.read_int() == 0x9ABCDEF0


def test_scratchpad_ld_sto_32(fpga: FpgaModel):
    """STO writes 32-bit word to scratchpad and LD reads it back."""
    fpga.reg_file.al.write(0xCAFEBABE)
    microcode = [
        MicroInstruction(op=MicroOp.STO, src=Reg.AL, imm=4),
        MicroInstruction(op=MicroOp.LD, dst=Reg.BL, imm=4),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.bl.read_int() == 0xCAFEBABE


def test_scratchpad_ld_sto_64(fpga: FpgaModel):
    """STO writes 64-bit pair to scratchpad and LD reads it back."""
    fpga.reg_file.al.write(0x11223344)
    fpga.reg_file.ah.write(0x55667788)
    microcode = [
        MicroInstruction(op=MicroOp.STO, src=Reg.AL, imm=8, w=IW.W64),
        MicroInstruction(op=MicroOp.LD, dst=Reg.BL, imm=8, w=IW.W64),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.bl.read_int() == 0x11223344
    assert fpga.reg_file.bh.read_int() == 0x55667788


def test_scratchpad_ld_64_odd_base_raises(fpga: FpgaModel):
    """64-bit LD with odd base address must raise AssertionError."""
    microcode = [
        MicroInstruction(op=MicroOp.LD, dst=Reg.BL, imm=3, w=IW.W64),
    ]
    with pytest.raises(AssertionError, match="64-bit LD must use even base"):
        fpga.dispatcher._run(microcode)


def test_scratchpad_sto_64_odd_base_raises(fpga: FpgaModel):
    """64-bit STO with odd base address must raise AssertionError."""
    microcode = [
        MicroInstruction(op=MicroOp.STO, src=Reg.AL, imm=5, w=IW.W64),
    ]
    with pytest.raises(AssertionError, match="64-bit STO must use even base"):
        fpga.dispatcher._run(microcode)


def test_swap_basic(fpga: FpgaModel):
    """SWAP AL, BL exchanges the contents of AL and BL."""
    fpga.reg_file.al.write(0x11112222)
    fpga.reg_file.bl.write(0x33334444)
    microcode = [
        MicroInstruction(op=MicroOp.SWAP, dst=Reg.AL, src=Reg.BL),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.al.read_int() == 0x33334444
    assert fpga.reg_file.bl.read_int() == 0x11112222


def test_swap_ea_eb(fpga: FpgaModel):
    """SWAP EA, EB exchanges 12-bit exponent registers."""
    fpga.reg_file.ea.write(127)
    fpga.reg_file.eb.write(140)
    microcode = [
        MicroInstruction(op=MicroOp.SWAP, dst=Reg.EA, src=Reg.EB),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.ea.read_int() == 140
    assert fpga.reg_file.eb.read_int() == 127


def test_swap_same_reg(fpga: FpgaModel):
    """SWAP AL, AL is a no-op."""
    fpga.reg_file.al.write(0x12345678)
    microcode = [
        MicroInstruction(op=MicroOp.SWAP, dst=Reg.AL, src=Reg.AL),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.al.read_int() == 0x12345678


def test_swap_with_fl(fpga: FpgaModel):
    """SWAP FL, BL uses DL as fallback intermediary."""
    fpga.reg_file.fl.write(0xAAAAAAAA)
    fpga.reg_file.bl.write(0xBBBBBBBB)
    microcode = [
        MicroInstruction(op=MicroOp.SWAP, dst=Reg.FL, src=Reg.BL),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.fl.read_int() == 0xBBBBBBBB
    assert fpga.reg_file.bl.read_int() == 0xAAAAAAAA


def test_ssav_sres_basic(fpga: FpgaModel):
    """SSAV saves status flags and SRES restores condition flags."""
    # Set initial flags: ZERO, CARRY, SIGN
    fpga.reg_file.status.set_bit(StatusFlag.ZERO, True)
    fpga.reg_file.status.set_bit(StatusFlag.CARRY, True)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, True)

    microcode = [
        MicroInstruction(op=MicroOp.SSAV),
    ]
    fpga.dispatcher._run(microcode)

    # Change flags in status register
    fpga.reg_file.status.set_bit(StatusFlag.ZERO, False)
    fpga.reg_file.status.set_bit(StatusFlag.CARRY, False)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, False)
    fpga.reg_file.status.set_bit(StatusFlag.OVERFLOW, True)

    # SRES should restore ZERO, CARRY, SIGN, and clear OVERFLOW
    fpga.reg_file.upc.write(0)
    microcode = [
        MicroInstruction(op=MicroOp.SRES),
    ]
    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)


def test_sres_preserves_err_and_busy(fpga: FpgaModel):
    """SRES mask 0x7D does not overwrite ERR (bit 1) or BUSY (bit 7)."""
    # Initially ERR is 0
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # SSAV with ERR = 0
    microcode = [
        MicroInstruction(op=MicroOp.SSAV),
    ]
    fpga.dispatcher._run(microcode)

    # Simulate subroutine encountering an error (ERR set to 1)
    fpga.reg_file.status.set_bit(StatusFlag.ERR, True)

    # SRES should NOT clear ERR because mask 0x7D excludes bit 1
    fpga.reg_file.upc.write(0)
    microcode = [
        MicroInstruction(op=MicroOp.SRES),
    ]
    fpga.dispatcher._run(microcode)

    # ERR must still be set
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_ldi_register_32(fpga: FpgaModel):
    """LDI dst, imm loads a 10-bit immediate into a 32-bit register."""
    microcode = [
        MicroInstruction(op=MicroOp.LDI, dst=Reg.AL, src=Reg.IMM, imm=0x2AB),
        MicroInstruction(op=MicroOp.LDI, dst=Reg.C, src=Reg.IMM, imm=24),
        MicroInstruction(op=MicroOp.LDI, dst=Reg.EA, src=Reg.IMM, imm=127),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.al.read_int() == 0x2AB
    assert fpga.reg_file.c.read_int() == 24
    assert fpga.reg_file.ea.read_int() == 127


def test_ldi_register_64(fpga: FpgaModel):
    """LDI dst, imm with W64 loads imm into low half and 0 into high half."""
    fpga.reg_file.ah.write(0xFFFFFFFF)
    microcode = [
        MicroInstruction(op=MicroOp.LDI, w=IW.W64, dst=Reg.AL, src=Reg.IMM, imm=42),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.al.read_int() == 42
    assert fpga.reg_file.ah.read_int() == 0


def test_ldi_flag_set_and_clear(fpga: FpgaModel):
    """LDI flag, imm with dst=Reg.NONE sets or clears the specified status flag."""
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)

    # Set ERR=1 and ZERO=1
    microcode = [
        MicroInstruction(op=MicroOp.LDI, dst=Reg.NONE, src=Reg.IMM, flag=StatusFlag.ERR, imm=1),
        MicroInstruction(op=MicroOp.LDI, dst=Reg.NONE, src=Reg.IMM, flag=StatusFlag.ZERO, imm=1),
    ]
    fpga.dispatcher._run(microcode)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)

    # Clear ERR=0 while leaving ZERO=1
    fpga.reg_file.upc.write(0)
    microcode = [
        MicroInstruction(op=MicroOp.LDI, dst=Reg.NONE, src=Reg.IMM, flag=StatusFlag.ERR, imm=0),
    ]
    fpga.dispatcher._run(microcode)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)

