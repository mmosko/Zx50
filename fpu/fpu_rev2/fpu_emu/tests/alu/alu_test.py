"""Unit tests for Alu top-level coordinator methods."""

from fpu_emu.alu.alu import Alu
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, Registers
from fpu_emu.tests.testharness import RegTestHarness


def test_alu_full():
    hw = Hardware()
    alu = Alu(hw)
    reg = RegTestHarness(hw.reg)

    assert alu.hw is hw

    # Adder 32 / 64
    reg.set(Reg.AL, Registers.from_int(10, 4))
    reg.set(Reg.BL, Registers.from_int(5, 4))
    alu.add32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 15

    alu.adc32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 20

    alu.sub32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 15

    alu.sbb32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 10

    alu.cmp32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 10

    reg.set(Reg.AX, Registers.from_int(100, 8))
    reg.set(Reg.BX, Registers.from_int(50, 8))
    alu.add64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 150

    alu.adc64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 200

    alu.sub64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 150

    alu.sbb64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 100

    alu.cmp64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 100

    # Shifter 32 / 64
    reg.set(Reg.AL, Registers.from_int(0x10, 4))
    alu.lsl32(1)
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x20

    alu.lsr32(1)
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x10

    alu.asr32(1)
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x08

    alu.rrc32()
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x04

    reg.set(Reg.AX, Registers.from_int(0x100, 8))
    alu.lsl64(1)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x200

    alu.lsr64(1)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x100

    alu.asr64(1)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x80

    alu.rrc64()
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x40

    # LZC
    reg.set(Reg.AL, Registers.from_int(0x00010000, 4))
    assert alu.lzc32() == 15

    reg.set(Reg.AX, Registers.from_int(0x0000000100000000, 8))
    assert alu.lzc64() == 31

    # Logic 32 / 64
    reg.set(Reg.AL, Registers.from_int(0xFF, 4))
    reg.set(Reg.BL, Registers.from_int(0x0F, 4))
    alu.and32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x0F

    alu.or32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x0F

    alu.xor32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 0x00

    alu.not32()
    assert Registers.to_int(reg.peek(Reg.AL)) == 0xFFFFFFFF

    reg.set(Reg.AX, Registers.from_int(0xFF, 8))
    reg.set(Reg.BX, Registers.from_int(0x0F, 8))
    alu.and64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x0F

    alu.or64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x0F

    alu.xor64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 0x00

    alu.not64()
    assert Registers.to_int(reg.peek(Reg.AX)) == 0xFFFFFFFFFFFFFFFF

    alu.chs(Reg.AH)
    alu.abs_val(Reg.AH)

    reg.set(Reg.AL, Registers.from_int(-5, 4, signed=True))
    alu.abs_int32(Reg.AL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 5

    reg.set(Reg.AX, Registers.from_int(-50, 8, signed=True))
    alu.abs_int64(Reg.AX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 50

    # Booth Mul 32 / 64
    reg.set(Reg.AL, Registers.from_int(3, 4))
    reg.set(Reg.BL, Registers.from_int(7, 4))
    alu.mul32(Reg.BL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 21

    reg.set(Reg.AX, Registers.from_int(6, 8))
    reg.set(Reg.BX, Registers.from_int(7, 8))
    alu.mul64(Reg.BX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 42

    # FP Mul / Div 32 / 64
    reg.set(Reg.AL, Registers.from_f32(2.5))
    reg.set(Reg.BL, Registers.from_f32(4.0))
    alu.mul_f32()
    assert Registers.to_f32(reg.peek(Reg.AL)) == 10.0

    alu.div_f32()
    assert Registers.to_f32(reg.peek(Reg.AL)) == 2.5

    reg.set(Reg.AX, Registers.from_f64(2.5))
    reg.set(Reg.BX, Registers.from_f64(4.0))
    alu.mul_f64()
    assert Registers.to_f64(reg.peek(Reg.AX)) == 10.0

    alu.div_f64()
    assert Registers.to_f64(reg.peek(Reg.AX)) == 2.5

    # FP Exp
    reg.ea = 10
    reg.eb = 5
    alu.exp_add()
    alu.exp_sub()
    alu.exp_diff()
    alu.exp_add_mul()
    alu.exp_sub_div()
    alu.exp_adj_norm(1)
    alu.exp_inc()
    alu.exp_dec()

    reg.set(Reg.AL, Registers.from_f32(1.5))
    alu.unpack_f32()
    alu.pack_f32()

    reg.set(Reg.AX, Registers.from_f64(1.5))
    alu.unpack_f64()
    alu.pack_f64()

    alu.swap(Reg.AL, Reg.BL)

    # Sqrt Exp / Core
    reg.ea = 128
    reg.eb = 129
    is_odd_a = alu.sqrt_exp32(Reg.EA)
    is_odd_b = alu.sqrt_exp32(Reg.EB)
    assert is_odd_a
    assert not is_odd_b
    alu.sqrt_core32(is_odd_a)

    reg.ea = 1024
    reg.eb = 1025
    is_odd_64_a = alu.sqrt_exp64(Reg.EA)
    is_odd_64_b = alu.sqrt_exp64(Reg.EB)
    assert is_odd_64_a
    assert not is_odd_64_b
    alu.sqrt_core64(is_odd_64_a)
