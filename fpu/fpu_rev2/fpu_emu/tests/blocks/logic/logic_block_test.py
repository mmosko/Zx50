import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


def run_logic(fpga: FpgaModel, instr: MicroInstruction) -> int:
    """Helper to set up instruction, route writeback mux, and execute logic block.

    Returns the number of clock cycles elapsed during execution.
    """
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)
    fpga.writeback_mux.set_block((instr.op.value >> 3) & 0x07)
    clk_start = fpga.clock.cycles
    fpga.logic_block.execute()
    return fpga.clock.cycles - clk_start


def test_and_32_basic(fpga: FpgaModel):
    fpga.reg_file.al.write(0x0000FFFF)
    fpga.reg_file.bl.write(0x00FF00FF)

    instr = MicroInstruction(op=MicroOp.AND, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.al.read_int() == 0x000000FF
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)


def test_and_32_zero_and_sign(fpga: FpgaModel):
    # Test zero flag
    fpga.reg_file.al.write(0x0F0F0F0F)
    fpga.reg_file.bl.write(0xF0F0F0F0)

    instr = MicroInstruction(op=MicroOp.AND, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    run_logic(fpga, instr)

    assert fpga.reg_file.al.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)

    # Test sign flag
    fpga.clock.tick()
    fpga.reg_file.al.write(0x80000000)
    fpga.reg_file.bl.write(0xFFFFFFFF)
    run_logic(fpga, instr)

    assert fpga.reg_file.al.read_int() == 0x80000000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_and_64(fpga: FpgaModel):
    # AX = {0x80000000, 0x0000FFFF}, BX = {0xFFFFFFFF, 0x00FF00FF}
    fpga.reg_file.al.write(0x0000FFFF)
    fpga.reg_file.ah.write(0x80000000)
    fpga.reg_file.bl.write(0x00FF00FF)
    fpga.reg_file.bh.write(0xFFFFFFFF)

    instr = MicroInstruction(op=MicroOp.AND, w=IW.W64, dst=Reg.AL, src=Reg.BL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.al.read_int() == 0x000000FF
    assert fpga.reg_file.ah.read_int() == 0x80000000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)  # bit 63 is 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)


def test_or_32_basic(fpga: FpgaModel):
    fpga.reg_file.al.write(0x12000000)
    fpga.reg_file.bl.write(0x00000034)

    instr = MicroInstruction(op=MicroOp.OR, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.al.read_int() == 0x12000034
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_or_64(fpga: FpgaModel):
    fpga.reg_file.al.write(0x00001111)
    fpga.reg_file.ah.write(0x80000000)
    fpga.reg_file.bl.write(0x22220000)
    fpga.reg_file.bh.write(0x00003333)

    instr = MicroInstruction(op=MicroOp.OR, w=IW.W64, dst=Reg.AL, src=Reg.BL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.al.read_int() == 0x22221111
    assert fpga.reg_file.ah.read_int() == 0x80003333
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_xor_32_basic(fpga: FpgaModel):
    fpga.reg_file.al.write(0xAAAAAAAA)
    fpga.reg_file.bl.write(0xAAAAAAAA)

    instr = MicroInstruction(op=MicroOp.XOR, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.al.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_xor_64(fpga: FpgaModel):
    fpga.reg_file.al.write(0x12345678)
    fpga.reg_file.ah.write(0x87654321)
    fpga.reg_file.bl.write(0x12345678)
    fpga.reg_file.bh.write(0x07654321)

    instr = MicroInstruction(op=MicroOp.XOR, w=IW.W64, dst=Reg.AL, src=Reg.BL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.al.read_int() == 0
    assert fpga.reg_file.ah.read_int() == 0x80000000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_not_32(fpga: FpgaModel):
    # Set CARRY and OVERFLOW to 1 before NOT to verify they are unaffected
    fpga.reg_file.status.set_bit(StatusFlag.CARRY, 1)
    fpga.reg_file.status.set_bit(StatusFlag.OVERFLOW, 1)

    fpga.reg_file.al.write(0x00000000)
    instr = MicroInstruction(op=MicroOp.NOT, w=IW.W32, dst=Reg.AL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.al.read_int() == 0xFFFFFFFF
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    # C and V unaffected
    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)


def test_not_64(fpga: FpgaModel):
    fpga.reg_file.al.write(0xFFFFFFFF)
    fpga.reg_file.ah.write(0xFFFFFFFF)

    instr = MicroInstruction(op=MicroOp.NOT, w=IW.W64, dst=Reg.AL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 2
    assert fpga.reg_file.al.read_int() == 0
    assert fpga.reg_file.ah.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_fabs_32(fpga: FpgaModel):
    # -1.0f = 0xBF800000 -> +1.0f = 0x3F800000
    fpga.reg_file.al.write(0xBF800000)
    instr = MicroInstruction(op=MicroOp.FABS, w=IW.W32, dst=Reg.AL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.al.read_int() == 0x3F800000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)

    # -0.0f = 0x80000000 -> +0.0f = 0x00000000
    fpga.clock.tick()
    fpga.reg_file.al.write(0x80000000)
    run_logic(fpga, instr)

    assert fpga.reg_file.al.read_int() == 0x00000000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_fabs_64(fpga: FpgaModel):
    # -1.0 double = 0xBFF00000_00000000 -> +1.0 = 0x3FF00000_00000000
    # 1 cycle, low half untouched
    fpga.reg_file.al.write(0x12345678)
    fpga.reg_file.ah.write(0xBFF00000)

    instr = MicroInstruction(op=MicroOp.FABS, w=IW.W64, dst=Reg.AL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.al.read_int() == 0x12345678
    assert fpga.reg_file.ah.read_int() == 0x3FF00000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_fchs_32(fpga: FpgaModel):
    # +1.0f = 0x3F800000 -> -1.0f = 0xBF800000
    fpga.reg_file.al.write(0x3F800000)
    instr = MicroInstruction(op=MicroOp.FCHS, w=IW.W32, dst=Reg.AL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.al.read_int() == 0xBF800000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)

    # -1.0f = 0xBF800000 -> +1.0f = 0x3F800000
    run_logic(fpga, instr)

    assert fpga.reg_file.al.read_int() == 0x3F800000
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_fchs_64(fpga: FpgaModel):
    # Double: 0x3FF00000_12345678 -> 0xBFF00000_12345678 (1 cycle, low half untouched)
    fpga.reg_file.al.write(0x12345678)
    fpga.reg_file.ah.write(0x3FF00000)

    instr = MicroInstruction(op=MicroOp.FCHS, w=IW.W64, dst=Reg.AL)
    elapsed = run_logic(fpga, instr)

    assert elapsed == 1
    assert fpga.reg_file.al.read_int() == 0x12345678
    assert fpga.reg_file.ah.read_int() == 0xBFF00000
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_unsupported_opcode_raises(fpga: FpgaModel):
    instr = MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    instr.to_register(fpga.reg_file.instr, fpga.reg_file.imm)

    with pytest.raises(HardwareBusError, match="Unsupported opcode"):
        fpga.logic_block.execute()


def test_dispatcher_and_execution(fpga: FpgaModel):
    fpga.reg_file.al.write(0xFF00FF00)
    fpga.reg_file.bl.write(0x12345678)

    microcode = [
        MicroInstruction(op=MicroOp.AND, w=IW.W32, dst=Reg.AL, src=Reg.BL),
    ]

    fpga.dispatcher._run(microcode)

    assert fpga.reg_file.al.read_int() == 0x12005600
