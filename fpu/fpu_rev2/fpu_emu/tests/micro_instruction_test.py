from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp


def test_micro_instruction_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode ADD AL, BL
    orig = MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL, flag=None, imm=0)
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.ADD
    assert decoded.w == IW.W32
    assert decoded.dst == Reg.AL
    assert decoded.src == Reg.BL
    assert decoded.src1 == Reg.NONE
    assert decoded.flag == None


def test_micro_instruction_jump_with_flag():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode JNZ with StatusFlag.UNDERFLOW and imm=42
    orig = MicroInstruction(
        op=MicroOp.JNZ,
        w=IW.W32,
        flag=StatusFlag.UNDERFLOW,
        imm=42,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.JNZ
    assert decoded.flag == StatusFlag.UNDERFLOW.value
    assert imm_reg.read_int() == 42


def test_micro_instruction_three_address_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode EXP_SUB C, EA, EB (C <- EA - EB)
    orig = MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.C, src1=Reg.EA, src=Reg.EB)
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.EXP_SUB
    assert decoded.dst == Reg.C
    assert decoded.src1 == Reg.EA
    assert decoded.src == Reg.EB


def test_micro_instruction_ldi_flag_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode LDI ERR, 1: dst=NONE, src=IMM, flag=ERR, imm=1
    orig = MicroInstruction(
        op=MicroOp.LDI,
        dst=Reg.NONE,
        src=Reg.IMM,
        flag=StatusFlag.ERR,
        imm=1,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.LDI
    assert decoded.dst == Reg.NONE
    assert decoded.flag == StatusFlag.ERR
    assert imm_reg.read_int() == 1


def test_micro_instruction_ldc_immediate_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode LDC AL, CONST, PI_F32 (imm=0)
    from fpu_emu.rom.fpu_const_map import FpuTable, FpuConst
    orig = MicroInstruction(
        op=MicroOp.LDC,
        dst=Reg.AL,
        src=FpuTable.CONST,
        imm=FpuConst.PI_F32,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.LDC
    assert decoded.dst == Reg.AL
    assert decoded.src == FpuTable.CONST
    assert decoded.src1 == Reg.IMM
    assert imm_reg.read_int() == FpuConst.PI_F32


def test_micro_instruction_ldc_dynamic_reg_round_trip():
    clock = Clock()
    instr_reg = Register(name=Reg.INSTR, size_in_bits=21, clock=clock)
    imm_reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

    # Encode LDC AH, SQRT, C
    from fpu_emu.rom.fpu_const_map import FpuTable
    orig = MicroInstruction(
        op=MicroOp.LDC,
        dst=Reg.AH,
        src=FpuTable.SQRT,
        src1=Reg.C,
    )
    orig.to_register(instr_reg, imm_reg)

    decoded = MicroInstruction.from_register(instr_reg)
    assert decoded.op == MicroOp.LDC
    assert decoded.dst == Reg.AH
    assert decoded.src == FpuTable.SQRT
    assert decoded.src1 == Reg.C


def test_micro_instruction_to_bytes_little_endian():
    # ADD AL, BL (W=0, DST=AL(0), SRC=BL(6), SRC1=AL(0), IMM=0)
    # Word: 0x000C0000
    # Little-endian stores lowest byte at address 0: [0x00, 0x00, 0x0C, 0x00]
    inst = MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL)
    raw = inst.to_bytes()
    assert len(raw) == 4
    assert raw == bytes([0x00, 0x00, 0x0C, 0x00])


def test_micro_instruction_to_bytes_bit_fields():
    # Construct an instruction exercising all fields:
    # JNZ flag=UNDERFLOW(2), imm=42 (0x2A)
    # OPCODE = JNZ (25 = 0b011001) -> 25 << 26 = 0x64000000
    # W = 0
    # DST = Reg.NONE (15) -> 15 << 21 = 0x01E00000
    # SRC2 = Reg.NONE (15) -> 15 << 17 = 0x001E0000
    # FLAG_COND = UNDERFLOW (2) -> 2 << 14 = 0x00008000
    # SRC1 = AL (0) -> 0 << 11 = 0
    # RESERVED = 0 -> 0 << 10 = 0
    # IMM = 42 -> 0x0000002A
    # Sum = 0x65FE802A
    # In little-endian: [0x2A, 0x80, 0xFE, 0x65]
    inst = MicroInstruction(
        op=MicroOp.JNZ,
        w=IW.W32,
        flag=StatusFlag.UNDERFLOW,
        imm=42,
    )
    assert inst.to_int() == 0x65FE802A
    assert inst.to_bytes() == bytes([0x2A, 0x80, 0xFE, 0x65])


def test_micro_instruction_to_bytes_three_operand_and_w64():
    # SUB.64 DL, AL, BL
    # OPCODE = SUB (2 = 0b000010) -> 2 << 26 = 0x08000000
    # W = 1 -> 1 << 25 = 0x02000000
    # DST = DL (8) -> 8 << 21 = 0x01000000
    # SRC2 = BL (6) -> 6 << 17 = 0x000C0000
    # FLAG = 0 -> 0
    # SRC1 = AL (0) -> 0 << 11 = 0
    # IMM = 0
    # Expected word: 0x0B0C0000
    # In little-endian: [0x00, 0x00, 0x0C, 0x0B]
    inst = MicroInstruction(
        op=MicroOp.SUB,
        w=IW.W64,
        dst=Reg.DL,
        src1=Reg.AL,
        src=Reg.BL,
    )
    assert inst.to_int() == 0x0B0C0000
    assert inst.to_bytes() == bytes([0x00, 0x00, 0x0C, 0x0B])


def test_micro_instruction_round_trip_bytes():
    from fpu_emu.rom.fpu_const_map import FpuTable, FpuConst

    test_cases = [
        MicroInstruction(op=MicroOp.ADD, w=IW.W32, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(op=MicroOp.SUB, w=IW.W64, dst=Reg.DL, src1=Reg.AL, src=Reg.BL),
        MicroInstruction(op=MicroOp.JNZ, flag=StatusFlag.UNDERFLOW, imm=1023),
        MicroInstruction(op=MicroOp.EXP_SUB, dst=Reg.C, src1=Reg.EA, src=Reg.EB),
        MicroInstruction(op=MicroOp.LDI, dst=Reg.NONE, src=Reg.IMM, flag=StatusFlag.ERR, imm=1),
        MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.PI_F32),
        MicroInstruction(op=MicroOp.LDC, dst=Reg.AH, src=FpuTable.SQRT, src1=Reg.C),
        MicroInstruction(op=MicroOp.HALT),
        MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
        MicroInstruction(op=MicroOp.POP, w=IW.W64, dst=Reg.DL),
    ]

    for orig in test_cases:
        encoded = orig.to_bytes()
        assert len(encoded) == 4
        decoded = MicroInstruction.from_bytes(encoded)
        assert decoded.op == orig.op
        assert decoded.w == orig.w
        assert decoded.dst == orig.dst
        assert decoded.src == orig.src
        if orig.op == MicroOp.LDC and orig.src1 is Reg.NONE:
            assert decoded.src1 == Reg.IMM
        else:
            assert decoded.src1 == orig.src1
        assert decoded.flag == orig.flag
        assert decoded.imm == (orig.imm & 0x3FF)


def test_micro_instruction_emit_bin_rom_image():
    from fpu_emu.rom.fpu_const_map import FpuTable, FpuConst

    # Emulate a small routine: PUSH_PI_32
    routine = [
        MicroInstruction(op=MicroOp.LDC, dst=Reg.FL, src=FpuTable.CONST, imm=FpuConst.PI_F32),
        MicroInstruction(op=MicroOp.PUSH, src=Reg.FL),
        MicroInstruction(op=MicroOp.HALT),
    ]

    # Emit binary ROM image (4 bytes per instruction in little-endian order)
    rom_bin = b"".join(inst.to_bytes() for inst in routine)
    assert len(rom_bin) == 3 * 4  # 12 bytes

    # Read back binary ROM image word by word
    recovered = []
    for offset in range(0, len(rom_bin), 4):
        chunk = rom_bin[offset : offset + 4]
        recovered.append(MicroInstruction.from_bytes(chunk))

    assert len(recovered) == 3
    assert recovered[0].op == MicroOp.LDC
    assert recovered[0].dst == Reg.FL
    assert recovered[0].src == FpuTable.CONST
    assert recovered[0].imm == FpuConst.PI_F32
    assert recovered[1].op == MicroOp.PUSH
    assert recovered[1].src == Reg.FL
    assert recovered[2].op == MicroOp.HALT


def test_micro_instruction_from_bytes_invalid_length():
    import pytest

    with pytest.raises(ValueError, match="MicroInstruction requires at least 4 bytes"):
        MicroInstruction.from_bytes(b"\x00\x01\x02")




