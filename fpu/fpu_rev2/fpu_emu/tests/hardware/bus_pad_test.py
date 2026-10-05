import pytest

from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.bus_pad import BusPad
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register


def test_bus_pad_properties():
    clock = Clock()
    reg = Register(name=Reg.C, size_in_bits=6, clock=clock)
    pad = BusPad(reg, 32, name="test_pad_c")

    assert pad.name == "test_pad_c"
    assert pad.source is reg
    assert pad.size_in_bits == 32
    assert pad.size_in_bytes == 4


def test_bus_pad_read_int_and_bytes():
    clock = Clock()
    reg = Register(name=Reg.IMM, size_in_bits=10, clock=clock)
    pad = BusPad(reg, 32)

    reg.write(0x2AA)  # 682 in decimal
    assert pad.read_int() == 0x2AA
    raw = pad.read()
    assert len(raw) == 4
    assert raw == b"\xAA\x02\x00\x00"

    clock.tick(1)
    reg.write(0x3FF)  # 1023 (max 10-bit)
    assert pad.read_int() == 0x3FF
    assert pad.read() == b"\xFF\x03\x00\x00"


def test_bus_pad_c_register_zero_extension():
    clock = Clock()
    c_reg = Register(name=Reg.C, size_in_bits=6, clock=clock)
    pad = BusPad(c_reg, 32)

    c_reg.write(0x3F)  # 63 (max 6-bit)
    assert pad.read_int() == 63
    assert pad.read() == b"\x3F\x00\x00\x00"


def test_bus_pad_with_bus():
    bus = Bus(name="narrow_bus", size_in_bits=4)
    pad = BusPad(bus, 16)

    assert pad.size_in_bits == 16
    assert pad.size_in_bytes == 2

    bus.set(0x0E)
    assert pad.read_int() == 14
    assert pad.read() == b"\x0E\x00"


def test_bus_pad_invalid_size():
    bus = Bus(name="b", size_in_bits=8)
    with pytest.raises(AssertionError):
        BusPad(bus, 0)
    with pytest.raises(AssertionError):
        BusPad(bus, 4)  # Target smaller than source


def test_bus_pad_signed_extension():
    clock = Clock()
    reg = Register(name=Reg.EA, size_in_bits=12, clock=clock)
    pad = BusPad(reg, 32, signed=True)

    # Positive value: bit 11 is 0
    reg.write(50)
    assert pad.read_int() == 50
    assert pad.read() == b"\x32\x00\x00\x00"

    # Negative value: -1000 in 12-bit is 0xC18 (bit 11 is 1)
    clock.tick(1)
    reg.write((-1000) & 0x0FFF)
    assert pad.read_int() == 0xFFFFFC18
    assert pad.read() == b"\x18\xFC\xFF\xFF"

