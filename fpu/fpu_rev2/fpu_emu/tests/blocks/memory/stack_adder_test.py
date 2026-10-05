from fpu_emu.blocks.memory.stack_adder import StackAdder
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register


def test_stack_adder_basic_increment():
    clock = Clock()
    sp = Register(name=Reg.SP, size_in_bits=7, clock=clock)
    adder = StackAdder(sp)

    sp.write(0)
    adder.set_op(StackAdder.OP_INC)
    assert adder.val == 1
    assert adder.read_int() == 1
    assert adder.is_overflow is False
    assert adder.is_underflow is False
    assert adder.is_zero is False

    clock.tick(1)
    sp.write(10)
    assert adder.val == 11
    assert adder.is_overflow is False
    assert adder.is_underflow is False


def test_stack_adder_overflow():
    clock = Clock()
    sp = Register(name=Reg.SP, size_in_bits=7, clock=clock)
    adder = StackAdder(sp)

    sp.write(126)
    adder.set_op(StackAdder.OP_INC)
    assert adder.val == 127
    assert adder.is_overflow is False

    clock.tick(1)
    sp.write(127)
    adder.set_op(StackAdder.OP_INC)
    # 127 + 1 = 128 (bit 7 set)
    assert adder.read_int() == 128
    assert adder.val == 0
    assert adder.is_overflow is True
    assert adder.is_underflow is False
    assert adder.is_zero is False


def test_stack_adder_decrement_and_zero():
    clock = Clock()
    sp = Register(name=Reg.SP, size_in_bits=7, clock=clock)
    adder = StackAdder(sp)
    adder.set_op(StackAdder.OP_DEC)

    sp.write(5)
    assert adder.val == 4
    assert adder.read_int() == 4
    assert adder.is_zero is False
    assert adder.is_underflow is False

    clock.tick(1)
    sp.write(1)
    assert adder.val == 0
    assert adder.read_int() == 0
    assert adder.is_zero is True
    assert adder.is_underflow is False


def test_stack_adder_underflow():
    clock = Clock()
    sp = Register(name=Reg.SP, size_in_bits=7, clock=clock)
    adder = StackAdder(sp)
    adder.set_op(StackAdder.OP_DEC)

    # 0 - 1 = 255 (bit 7 set)
    sp.write(0)
    assert adder.read_int() == 255
    assert adder.is_underflow is True
    assert adder.is_overflow is False
    assert adder.is_zero is False


def test_stack_adder_read_bytes():
    clock = Clock()
    sp = Register(name=Reg.SP, size_in_bits=7, clock=clock)
    adder = StackAdder(sp)
    adder.set_op(StackAdder.OP_INC)

    sp.write(42)
    raw = adder.read()
    assert int.from_bytes(raw, byteorder="little") == 43
