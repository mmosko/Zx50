import pytest
from pathlib import Path
from fpu_emu.blocks.adder.adder_core import AdderCore
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


def test_adder_core_basic_addition():
    # 0x10 + 0x25 = 0x35
    a = (0x00000010).to_bytes(4, "little")
    b = (0x00000025).to_bytes(4, "little")
    res = AdderCore.adder_core(a=a, b=b, cin=0, sub=False)
    assert int.from_bytes(res.res, "little") == 0x35
    assert not res.cf
    assert not res.zf
    assert not res.sf
    assert not res.vf


def test_adder_core_carry_and_overflow():
    # 0xFFFFFFFF + 1 = 0 (carry out = 1, zero = 1)
    a = (0xFFFFFFFF).to_bytes(4, "little")
    b = (0x00000001).to_bytes(4, "little")
    res = AdderCore.adder_core(a=a, b=b, cin=0, sub=False)
    assert int.from_bytes(res.res, "little") == 0
    assert res.cf
    assert res.zf
    assert not res.sf
    assert not res.vf

    # Signed overflow: 0x7FFFFFFF + 1 = 0x80000000 (positive + positive = negative)
    a = (0x7FFFFFFF).to_bytes(4, "little")
    res = AdderCore.adder_core(a=a, b=b, cin=0, sub=False)
    assert int.from_bytes(res.res, "little") == 0x80000000
    assert not res.cf
    assert not res.zf
    assert res.sf
    assert res.vf


def test_adder_core_subtraction():
    # 0x50 - 0x20 = 0x30
    a = (0x00000050).to_bytes(4, "little")
    b = (0x00000020).to_bytes(4, "little")
    res = AdderCore.adder_core(a=a, b=b, cin=0, sub=True)
    assert int.from_bytes(res.res, "little") == 0x30
    assert not res.cf
    assert not res.zf

    # 0x20 - 0x50 = borrow out
    res_borrow = AdderCore.adder_core(a=b, b=a, cin=0, sub=True)
    assert res_borrow.cf  # Borrow occurred
    assert res_borrow.sf  # Negative result


@pytest.fixture
def fpga(tmp_path: Path):
    rom = Rom(size=16, rom_path=tmp_path / "dummy.rom")
    return FpgaModel(rom=rom)


def test_adder_block_add_32(fpga: FpgaModel):
    # AL = 0x1000, BL = 0x2345 -> ADD AL, BL -> AL = 0x3345
    fpga.reg_file.al.write(0x1000)
    fpga.reg_file.bl.write(0x2345)

    instr = MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0x3345
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_sub_32_flags(fpga: FpgaModel):
    # AL = 0x10, BL = 0x10 -> SUB AL, BL -> AL = 0, ZF = 1
    fpga.reg_file.al.write(0x10)
    fpga.reg_file.bl.write(0x10)

    instr = MicroInstruction(op=MicroOp.SUB, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)


def test_adder_block_cmp_32(fpga: FpgaModel):
    # AL = 0x20, BL = 0x50 -> CMP AL, BL -> AL remains 0x20, CF = 1, SF = 1
    fpga.reg_file.al.write(0x20)
    fpga.reg_file.bl.write(0x50)

    instr = MicroInstruction(op=MicroOp.CMP, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    fpga.adder.execute()

    # AL must be unmodified
    assert fpga.reg_file.al.read_int() == 0x20
    # Flags updated for 0x20 - 0x50
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)  # Borrow
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_add_64(fpga: FpgaModel):
    # AX = 0x00000001_FFFFFFFF, BX = 0x00000002_00000001
    # Result should be: AX = 0x00000004_00000000
    fpga.reg_file.al.write(0xFFFFFFFF)
    fpga.reg_file.ah.write(0x00000001)
    fpga.reg_file.bl.write(0x00000001)
    fpga.reg_file.bh.write(0x00000002)

    instr = MicroInstruction(op=MicroOp.ADD, w=IW.W64, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0x00000000
    assert fpga.reg_file.ah.read_int() == 0x00000004
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_sub_64(fpga: FpgaModel):
    # AX = 0x00000004_00000000, BX = 0x00000002_00000001
    # Result: AX = 0x00000001_FFFFFFFF (low word borrow from high word)
    fpga.reg_file.al.write(0x00000000)
    fpga.reg_file.ah.write(0x00000004)
    fpga.reg_file.bl.write(0x00000001)
    fpga.reg_file.bh.write(0x00000002)

    instr = MicroInstruction(op=MicroOp.SUB, w=IW.W64, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0xFFFFFFFF
    assert fpga.reg_file.ah.read_int() == 0x00000001
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)  # No 64-bit borrow out
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)

