import pytest
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.upc_adder import UpcAdder


def test_upc_adder_basic_increment():
    clock = Clock()
    upc_reg = Register(name=Reg.UPC, size_in_bits=10, clock=clock)
    adder = UpcAdder(upc_reg)

    upc_reg.write(0)
    assert adder.val == 1
    assert adder.carry is False
    assert adder.read_int() == 1

    clock.tick(1)
    upc_reg.write(100)
    assert adder.val == 101
    assert adder.carry is False
    assert adder.read_int() == 101

    clock.tick(1)
    upc_reg.write(1022)
    assert adder.val == 1023
    assert adder.carry is False
    assert adder.read_int() == 1023


def test_upc_adder_overflow_carry():
    clock = Clock()
    upc_reg = Register(name=Reg.UPC, size_in_bits=10, clock=clock)
    adder = UpcAdder(upc_reg)

    # 10-bit limit is 1023 (0x3FF). Incrementing 1023 must assert carry
    upc_reg.write(1023)
    assert adder.val == 0
    assert adder.carry is True
    assert adder.read_int() == 1024  # 11-bit output with bit 10 set


def test_upc_adder_bus_read():
    clock = Clock()
    upc_reg = Register(name=Reg.UPC, size_in_bits=10, clock=clock)
    adder = UpcAdder(upc_reg)

    upc_reg.write(5)
    raw_bytes = adder.read()
    assert int.from_bytes(raw_bytes, byteorder="little") == 6
