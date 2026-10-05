from fpu_emu.blocks.control.count_adder import CountAdder
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register


def test_count_adder_basic_decrement():
    clock = Clock()
    c_reg = Register(name=Reg.C, size_in_bits=6, clock=clock)
    adder = CountAdder(c_reg)

    c_reg.write(5)
    assert adder.val == 4
    assert adder.is_zero is False
    assert adder.read_int() == 4

    clock.tick(1)
    c_reg.write(1)
    assert adder.val == 0
    assert adder.is_zero is True
    assert adder.read_int() == 0


def test_count_adder_wrap_around():
    clock = Clock()
    c_reg = Register(name=Reg.C, size_in_bits=6, clock=clock)
    adder = CountAdder(c_reg)

    # 0 decremented in 6 bits wraps to 63 (0x3F)
    c_reg.write(0)
    assert adder.val == 63
    assert adder.is_zero is False
    assert adder.read_int() == 63


def test_count_adder_bus_read():
    clock = Clock()
    c_reg = Register(name=Reg.C, size_in_bits=6, clock=clock)
    adder = CountAdder(c_reg)

    c_reg.write(10)
    raw_bytes = adder.read()
    assert int.from_bytes(raw_bytes, byteorder="little") == 9
