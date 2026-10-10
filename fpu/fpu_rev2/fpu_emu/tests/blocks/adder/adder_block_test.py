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


def test_adder_block_exp_add_basic(fpga: FpgaModel):
    fpga.reg_file.ea.write(10)
    fpga.reg_file.eb.write(20)

    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 30
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_adder_block_exp_add_overflow(fpga: FpgaModel):
    # SystemReference.md example: EA = 1000, EB = 50 -> 1050 > +1023 (VF=1, UF=0, ZF=0, SF=0)
    fpga.reg_file.ea.write(1000)
    fpga.reg_file.eb.write(50)

    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 1050
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is False
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_exp_add_underflow(fpga: FpgaModel):
    # EA = -1000 (3096), EB = -30 (4066) -> -1030 < -1022 (UF=1, VF=0, SF=1, ZF=0)
    fpga.reg_file.ea.write((-1000) & 0x0FFF)
    fpga.reg_file.eb.write((-30) & 0x0FFF)

    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == ((-1030) & 0x0FFF)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) is False
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_adder_block_exp_add_zero(fpga: FpgaModel):
    # EA = 50, EB = -50 -> sum = 0
    fpga.reg_file.ea.write(50)
    fpga.reg_file.eb.write((-50) & 0x0FFF)

    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_adder_block_exp_add_imm(fpga: FpgaModel):
    # EA = 100, IMM = 25 -> EA = 125
    fpga.reg_file.ea.write(100)

    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.IMM, imm=25)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 125
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_exp_sub_basic(fpga: FpgaModel):
    fpga.reg_file.ea.write(30)
    fpga.reg_file.eb.write(10)

    instr = MicroInstruction(op=MicroOp.EXP_SUB, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 20
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_adder_block_exp_sub_underflow(fpga: FpgaModel):
    # SystemReference.md example: EA = -1000, EB = 50 -> -1050 < -1022 (UF=1, VF=0, SF=1, ZF=0)
    fpga.reg_file.ea.write((-1000) & 0x0FFF)
    fpga.reg_file.eb.write(50)

    instr = MicroInstruction(op=MicroOp.EXP_SUB, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == ((-1050) & 0x0FFF)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) is False
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_adder_block_exp_sub_overflow(fpga: FpgaModel):
    # EA = 1000, EB = -50 -> 1000 - (-50) = 1050 > 1023 (VF=1, UF=0)
    fpga.reg_file.ea.write(1000)
    fpga.reg_file.eb.write((-50) & 0x0FFF)

    instr = MicroInstruction(op=MicroOp.EXP_SUB, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 1050
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is False


def test_adder_block_exp_sub_zero(fpga: FpgaModel):
    fpga.reg_file.ea.write(100)
    fpga.reg_file.eb.write(100)

    instr = MicroInstruction(op=MicroOp.EXP_SUB, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_exp_preserves_carry_flag(fpga: FpgaModel):
    # CARRY flag must be unaffected by EXP_ADD and EXP_SUB
    fpga.reg_file.status.set_bit(StatusFlag.CARRY, True)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) is True

    fpga.reg_file.ea.write(10)
    fpga.reg_file.eb.write(20)
    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) is True

    instr_sub = MicroInstruction(op=MicroOp.EXP_SUB, src=Reg.EB)
    instr_sub.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) is True


def test_adder_block_exp_boundary_conditions(fpga: FpgaModel):
    # Max valid exponent: +1023 (VF=0)
    fpga.reg_file.ea.write(1023)
    fpga.reg_file.eb.write(0)
    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    # Overflow threshold: +1024 (VF=1)
    fpga.clock.tick(1)
    fpga.reg_file.ea.write(1023)
    fpga.reg_file.eb.write(1)
    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) is True

    # Min valid exponent: -1022 (UF=0)
    fpga.clock.tick(1)
    fpga.reg_file.ea.write((-1022) & 0x0FFF)
    fpga.reg_file.eb.write(0)
    instr = MicroInstruction(op=MicroOp.EXP_ADD, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Underflow threshold: -1023 (UF=1)
    fpga.clock.tick(1)
    fpga.reg_file.ea.write((-1022) & 0x0FFF)
    fpga.reg_file.eb.write(1)
    instr = MicroInstruction(op=MicroOp.EXP_SUB, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_adder_block_mul_signed_basic(fpga: FpgaModel):
    # AL = 3, BL = 5 -> MUL AL, BL -> AL = 15, AH = 0 (16 cycles)
    fpga.reg_file.al.write(3)
    fpga.reg_file.bl.write(5)

    start_ticks = fpga.clock.cycles
    instr = MicroInstruction(op=MicroOp.MUL, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 15
    assert fpga.reg_file.ah.read_int() == 0
    assert fpga.clock.cycles - start_ticks == 16
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)


def test_adder_block_mul_signed_overflow(fpga: FpgaModel):
    # SystemReference.md example: AL = 65536, BL = 131072
    # Product = 8,589,934,592 = 0x00000002_00000000 -> AH = 2, AL = 0, VF = 1
    fpga.reg_file.al.write(65536)
    fpga.reg_file.bl.write(131072)

    instr = MicroInstruction(op=MicroOp.MUL, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0
    assert fpga.reg_file.ah.read_int() == 2
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_mul_signed_negative(fpga: FpgaModel):
    # AL = -20, BL = 5 -> Product = -100 (AH = 0xFFFFFFFF, AL = 0xFFFFFF9C, VF = 0, SF = 1)
    fpga.reg_file.al.write((-20) & 0xFFFFFFFF)
    fpga.reg_file.bl.write(5)

    instr = MicroInstruction(op=MicroOp.MUL, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == ((-100) & 0xFFFFFFFF)
    assert fpga.reg_file.ah.read_int() == 0xFFFFFFFF
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) is True


def test_adder_block_mulu_unsigned(fpga: FpgaModel):
    # AL = 0xFFFFFFFF, BL = 2 -> Product = 0x1_FFFFFFFE -> AH = 1, AL = 0xFFFFFFFE, VF = 1
    fpga.reg_file.al.write(0xFFFFFFFF)
    fpga.reg_file.bl.write(2)

    instr = MicroInstruction(op=MicroOp.MULU, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0xFFFFFFFE
    assert fpga.reg_file.ah.read_int() == 1
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) is True


def test_adder_block_mul_with_fl_src(fpga: FpgaModel):
    # AL = 10, FL = 20 -> MUL AL, FL -> AL = 200, AH = 0
    fpga.reg_file.al.write(10)
    fpga.reg_file.fl.write(20)

    instr = MicroInstruction(op=MicroOp.MUL, w=IW.W32, dst=Reg.AL, src=Reg.FL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 200
    assert fpga.reg_file.ah.read_int() == 0


def test_adder_block_mul_default_dst(fpga: FpgaModel):
    # dst=Reg.NONE defaults to Reg.AL
    fpga.reg_file.al.write(6)
    fpga.reg_file.bl.write(7)

    instr = MicroInstruction(op=MicroOp.MUL, w=IW.W32, dst=Reg.NONE, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 42
    assert fpga.reg_file.ah.read_int() == 0


def test_adder_block_mul_invalid_dst(fpga: FpgaModel):
    # Only AL is valid destination for MUL on HA_MUX
    from fpu_emu.hardware.registers import HardwareBusError

    instr = MicroInstruction(op=MicroOp.MUL, w=IW.W32, dst=Reg.DL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    with pytest.raises(HardwareBusError, match="MUL destination on HA_MUX must be AL"):
        fpga.adder.execute()


def test_adder_block_mul_w64_not_implemented(fpga: FpgaModel):
    # 64-bit multiplication is orchestrated via microcode
    instr = MicroInstruction(op=MicroOp.MUL, w=IW.W64, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    with pytest.raises(NotImplementedError, match="orchestrated via microcode"):
        fpga.adder.execute()


def test_adder_block_div_32_basic(fpga: FpgaModel):
    # 23 / 5 = 4 rem 3 (32 cycles)
    fpga.reg_file.al.write(23)
    fpga.reg_file.bl.write(5)

    instr = MicroInstruction(op=MicroOp.DIV, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    clk_start = fpga.clock.cycles
    fpga.adder.execute()

    assert fpga.clock.cycles - clk_start == 32
    assert fpga.reg_file.al.read_int() == 4
    assert fpga.reg_file.dl.read_int() == 3
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_adder_block_div_32_signed_negative(fpga: FpgaModel):
    # (-23) / 5 = -4 rem -3
    fpga.reg_file.al.write((-23) & 0xFFFFFFFF)
    fpga.reg_file.bl.write(5)

    instr = MicroInstruction(op=MicroOp.DIV, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == ((-4) & 0xFFFFFFFF)
    assert fpga.reg_file.dl.read_int() == ((-3) & 0xFFFFFFFF)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_adder_block_divu_32(fpga: FpgaModel):
    # Unsigned 0xFFFFFFFF / 2 = 0x7FFFFFFF rem 1
    fpga.reg_file.al.write(0xFFFFFFFF)
    fpga.reg_file.bl.write(2)

    instr = MicroInstruction(op=MicroOp.DIVU, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0x7FFFFFFF
    assert fpga.reg_file.dl.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_div_by_zero(fpga: FpgaModel):
    # Divide-by-zero: aborts immediately (1 cycle), AL and DL unmodified, sets ERR and V
    fpga.reg_file.al.write(42)
    fpga.reg_file.dl.write(99)
    fpga.reg_file.bl.write(0)

    instr = MicroInstruction(op=MicroOp.DIV, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    clk_start = fpga.clock.cycles
    fpga.adder.execute()

    assert fpga.clock.cycles - clk_start == 1
    assert fpga.reg_file.al.read_int() == 42
    assert fpga.reg_file.dl.read_int() == 99
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)


def test_adder_block_div_default_dst(fpga: FpgaModel):
    # dst=Reg.NONE defaults to Reg.AL
    fpga.reg_file.al.write(10)
    fpga.reg_file.bl.write(2)

    instr = MicroInstruction(op=MicroOp.DIV, w=IW.W32, dst=Reg.NONE, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 5
    assert fpga.reg_file.dl.read_int() == 0


def test_adder_block_div_invalid_dst(fpga: FpgaModel):
    from fpu_emu.hardware.registers import HardwareBusError

    instr = MicroInstruction(op=MicroOp.DIV, w=IW.W32, dst=Reg.DL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    with pytest.raises(HardwareBusError, match="DIV destination on HA_MUX must be AL"):
        fpga.adder.execute()


def test_adder_block_div_w64_not_implemented(fpga: FpgaModel):
    instr = MicroInstruction(op=MicroOp.DIV, w=IW.W64, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    with pytest.raises(NotImplementedError, match="orchestrated via microcode"):
        fpga.adder.execute()


# =============================================================================
# UNPACK and PACK Tests
# =============================================================================

def test_adder_block_unpack_f32_one(fpga: FpgaModel):
    # +1.0f = 0x3F800000: EA -> 127, AL -> 0x00800000
    fpga.reg_file.al.write(0x3F800000)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, True)  # Previous sign negative

    instr = MicroInstruction(op=MicroOp.UNPACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    clk_start = fpga.clock.cycles
    fpga.adder.execute()

    assert fpga.clock.cycles - clk_start == 2
    assert fpga.reg_file.ea.read_int() == 127
    assert fpga.reg_file.al.read_int() == 0x00800000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    # DIFF_SIGN: prev_s(1) ^ current_sign(0) == 1
    assert fpga.reg_file.status.is_bit_set(StatusFlag.DIFF_SIGN)


def test_adder_block_unpack_f32_negative(fpga: FpgaModel):
    # -1.5f = 0xBFC00000 (sign=1, exp=127, frac=0x400000)
    fpga.reg_file.al.write(0xBFC00000)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, False)

    instr = MicroInstruction(op=MicroOp.UNPACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 127
    assert fpga.reg_file.al.read_int() == 0x00C00000  # (1 << 23) | 0x400000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.DIFF_SIGN)


def test_adder_block_unpack_f32_zero(fpga: FpgaModel):
    # -0.0f = 0x80000000
    fpga.reg_file.al.write(0x80000000)
    instr = MicroInstruction(op=MicroOp.UNPACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 0
    assert fpga.reg_file.al.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_adder_block_unpack_f32_secondary_regs(fpga: FpgaModel):
    # Test unpacking into BL and EB
    fpga.reg_file.bl.write(0x40000000)  # +2.0f (exp=128, frac=0)
    instr = MicroInstruction(op=MicroOp.UNPACK, w=IW.W32, dst=Reg.BL, src=Reg.EB)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.eb.read_int() == 128
    assert fpga.reg_file.bl.read_int() == 0x00800000


def test_adder_block_unpack_f64_one(fpga: FpgaModel):
    # +1.0 double = 0x3FF00000_00000000 (exp=1023, frac=0)
    fpga.reg_file.ah.write(0x3FF00000)
    fpga.reg_file.al.write(0x00000000)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, False)

    instr = MicroInstruction(op=MicroOp.UNPACK, w=IW.W64, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    clk_start = fpga.clock.cycles
    fpga.adder.execute()

    assert fpga.clock.cycles - clk_start == 2
    assert fpga.reg_file.ea.read_int() == 1023
    assert fpga.reg_file.ah.read_int() == 0x00100000  # (1 << 20)
    assert fpga.reg_file.al.read_int() == 0x00000000  # Unchanged
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.DIFF_SIGN)


def test_adder_block_unpack_f64_negative_zero(fpga: FpgaModel):
    # -0.0 double = 0x80000000_00000000
    fpga.reg_file.ah.write(0x80000000)
    fpga.reg_file.al.write(0x00000000)

    instr = MicroInstruction(op=MicroOp.UNPACK, w=IW.W64, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ea.read_int() == 0
    assert fpga.reg_file.ah.read_int() == 0
    assert fpga.reg_file.al.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_adder_block_pack_f32_normal(fpga: FpgaModel):
    # Mantissa = 0x00800000, EA = 127, SIGN = 0 -> 0x3F800000 (+1.0f)
    fpga.reg_file.al.write(0x00800000)
    fpga.reg_file.ea.write(127)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, False)

    instr = MicroInstruction(op=MicroOp.PACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    clk_start = fpga.clock.cycles
    fpga.adder.execute()

    assert fpga.clock.cycles - clk_start == 1
    assert fpga.reg_file.al.read_int() == 0x3F800000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_adder_block_pack_f32_negative(fpga: FpgaModel):
    # Mantissa = 0x00C00000, EA = 127, SIGN = 1 -> 0xBFC00000 (-1.5f)
    fpga.reg_file.al.write(0x00C00000)
    fpga.reg_file.ea.write(127)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, True)

    instr = MicroInstruction(op=MicroOp.PACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0xBFC00000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_adder_block_pack_f32_zero_mantissa(fpga: FpgaModel):
    # Zero mantissa -> signed zero
    fpga.reg_file.al.write(0)
    fpga.reg_file.ea.write(127)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, True)

    instr = MicroInstruction(op=MicroOp.PACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0x80000000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_adder_block_pack_f32_overflow(fpga: FpgaModel):
    # Exponent >= 255 -> overflow to +/- inf
    fpga.reg_file.al.write(0x00800000)
    fpga.reg_file.ea.write(255)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, False)

    instr = MicroInstruction(op=MicroOp.PACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0x7F800000  # +inf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_adder_block_pack_f32_underflow(fpga: FpgaModel):
    # Exponent <= 0 -> underflow to signed zero
    fpga.reg_file.al.write(0x00800000)
    fpga.reg_file.ea.write(0)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, True)

    instr = MicroInstruction(op=MicroOp.PACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == 0x80000000  # -0.0f
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_pack_f64_normal(fpga: FpgaModel):
    # Mantissa AH = 0x00100000, AL = 0x00000000, EA = 1023 -> 0x3FF00000_00000000 (+1.0)
    fpga.reg_file.ah.write(0x00100000)
    fpga.reg_file.al.write(0x00000000)
    fpga.reg_file.ea.write(1023)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, False)

    instr = MicroInstruction(op=MicroOp.PACK, w=IW.W64, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    clk_start = fpga.clock.cycles
    fpga.adder.execute()

    assert fpga.clock.cycles - clk_start == 2
    assert fpga.reg_file.ah.read_int() == 0x3FF00000
    assert fpga.reg_file.al.read_int() == 0x00000000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_adder_block_pack_f64_overflow(fpga: FpgaModel):
    # Overflow: exp >= 2047 -> +inf (0x7FF00000_00000000)
    fpga.reg_file.ah.write(0x00100000)
    fpga.reg_file.al.write(0x12345678)
    fpga.reg_file.ea.write(2047)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, False)

    instr = MicroInstruction(op=MicroOp.PACK, w=IW.W64, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ah.read_int() == 0x7FF00000
    assert fpga.reg_file.al.read_int() == 0x00000000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)


def test_adder_block_pack_f64_underflow(fpga: FpgaModel):
    # Underflow: exp <= 0 -> -0.0 (0x80000000_00000000)
    fpga.reg_file.ah.write(0x00100000)
    fpga.reg_file.al.write(0x12345678)
    fpga.reg_file.ea.write(0)
    fpga.reg_file.status.set_bit(StatusFlag.SIGN, True)

    instr = MicroInstruction(op=MicroOp.PACK, w=IW.W64, dst=Reg.AL, src=Reg.EA)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.ah.read_int() == 0x80000000
    assert fpga.reg_file.al.read_int() == 0x00000000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_adder_block_unpack_pack_roundtrip(fpga: FpgaModel):
    # Verify exact round-trip for arbitrary float32 value: 12.375f = 0x41460000
    original = 0x41460000
    fpga.reg_file.al.write(original)

    # UNPACK AL, EA
    unpack_instr = MicroInstruction(op=MicroOp.UNPACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    unpack_instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    # PACK AL, EA
    pack_instr = MicroInstruction(op=MicroOp.PACK, w=IW.W32, dst=Reg.AL, src=Reg.EA)
    pack_instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.al.read_int() == original


def test_adder_block_add_64_cx_general(fpga: FpgaModel):
    # CX = 0x00000001_FFFFFFFF, DX = 0x00000002_00000001
    # ADD CX, DX -> CX = 0x00000004_00000000
    fpga.reg_file.cl.write(0xFFFFFFFF)
    fpga.reg_file.ch.write(0x00000001)
    fpga.reg_file.dl.write(0x00000001)
    fpga.reg_file.dh.write(0x00000002)

    instr = MicroInstruction(op=MicroOp.ADD, w=IW.W64, dst=Reg.CL, src=Reg.DL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.cl.read_int() == 0x00000000
    assert fpga.reg_file.ch.read_int() == 0x00000004
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)


def test_adder_block_sub_64_three_operand_with_cx(fpga: FpgaModel):
    # SUB CX, AX, BX: CX = AX - BX
    # AX = 0x00000005_00000000, BX = 0x00000002_00000001
    # CX should be: 0x00000002_FFFFFFFF
    fpga.reg_file.al.write(0x00000000)
    fpga.reg_file.ah.write(0x00000005)
    fpga.reg_file.bl.write(0x00000001)
    fpga.reg_file.bh.write(0x00000002)

    instr = MicroInstruction(op=MicroOp.SUB, w=IW.W64, dst=Reg.CL, src1=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.adder.execute()

    assert fpga.reg_file.cl.read_int() == 0xFFFFFFFF
    assert fpga.reg_file.ch.read_int() == 0x00000002
    # Ensure source registers were unmodified
    assert fpga.reg_file.al.read_int() == 0x00000000
    assert fpga.reg_file.ah.read_int() == 0x00000005




