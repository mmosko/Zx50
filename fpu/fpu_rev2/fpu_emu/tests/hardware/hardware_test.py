import pytest
from pathlib import Path
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register, StatusRegister
from fpu_emu.hardware.registers import Registers, StatusFlag
from fpu_emu.hardware.ebr import EBR
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.rom import Rom


def test_clock():
    clock = Clock()
    assert clock.cycles == 0
    clock.tick()
    assert clock.cycles == 1
    clock.tick(3)
    assert clock.cycles == 4
    clock.reset()
    assert clock.cycles == 0


def test_bus():
    bus = Bus(name="test_bus", size_in_bits=12)
    assert bus.name == "test_bus"
    assert bus.size_in_bits == 12
    assert bus.size_in_bytes == 2
    assert bus.read() == b"\x00\x00"
    assert bus.read_int() == 0

    # Set using int
    bus.set(0x1ABC)  # 0x1ABC & 0x0FFF == 0x0ABC
    assert bus.read_int() == 0x0ABC
    assert bus.read() == (0x0ABC).to_bytes(2, "little")

    # Set using bytes
    bus.set(b"\xFF\x0F")  # 0x0FFF & 0x0FFF == 0x0FFF
    assert bus.read_int() == 0x0FFF

    # Assert byte length mismatch
    with pytest.raises(AssertionError):
        bus.set(b"\x01")


def test_mux():
    bus0 = Bus("b0", 8)
    bus1 = Bus("b1", 8)
    bus0.set(0x42)
    bus1.set(0x99)

    mux = Mux(name="test_mux", inputs=[bus0, bus1])
    with pytest.raises(AssertionError):
        mux.read()  # before select

    mux.select(0)
    assert mux.read_int() == 0x42
    assert mux.read() == b"\x42"

    mux.select(1)
    assert mux.read_int() == 0x99

    with pytest.raises(AssertionError):
        mux.select(2)  # out of range


def test_register():
    clock = Clock()
    reg = Register(name=Reg.AL, size_in_bits=32, clock=clock)
    assert reg.name == Reg.AL
    assert reg.size_in_bits == 32
    assert reg.size_in_bytes == 4
    assert reg.read_int() == 0

    # Write in cycle 0
    reg.write(0x7F)
    assert reg.read_int() == 0x7F

    # Multiple writes in same cycle should assert
    with pytest.raises(AssertionError):
        reg.write(b"\x00\x00\x00\x80")

    # Next cycle
    clock.tick()
    reg.write(b"\x78\x56\x34\x12")
    assert reg.read_int() == 0x12345678

    reg.reset()
    assert reg.read_int() == 0


def test_status_register():
    clock = Clock()
    sreg = StatusRegister(name=Reg.STATUS, size_in_bits=8, clock=clock)
    assert sreg.read_int() == 0

    # Set ZERO flag in cycle 0
    sreg.set_bit(StatusFlag.ZERO, True)
    assert sreg.is_bit_set(StatusFlag.ZERO) is True
    assert sreg.is_bit_set(StatusFlag.CARRY) is False

    # Second write to same bit in cycle 0 should fail
    with pytest.raises(AssertionError):
        sreg.set_bit(StatusFlag.ZERO, False)

    # Different bit in same cycle is allowed
    sreg.set_bit(StatusFlag.CARRY, True)
    assert sreg.is_bit_set(StatusFlag.CARRY) is True

    # Next cycle
    clock.tick()
    sreg.set_bit(StatusFlag.ZERO, False)
    assert sreg.is_bit_set(StatusFlag.ZERO) is False
    assert sreg.is_bit_set(StatusFlag.CARRY) is True

    sreg.reset()
    assert sreg.read_int() == 0


def test_registers_file():
    clock = Clock()
    regs = Registers(clock=clock)
    assert regs.al.size_in_bits == 32
    assert regs.cl.size_in_bits == 32
    assert regs.ch.size_in_bits == 32
    assert regs.ea.size_in_bits == 12
    assert regs.c.size_in_bits == 6
    assert regs.status.size_in_bits == 8
    assert regs.upc.size_in_bits == 10
    assert regs.instr.size_in_bits == 22
    assert regs.imm.size_in_bits == 10


def test_ebr():
    clock = Clock()
    ebr = EBR(name="ebr0", size=512, width=18, read_only_buffer=None, clock=clock)
    assert ebr.name == "ebr0"

    # Write in cycle 0
    ebr.write(addr=0x10, data=0x3FFFF)
    assert ebr.read(addr=0x10) == 0x3FFFF

    # Multiple reads in cycle 0 fails
    with pytest.raises(AssertionError):
        ebr.read(addr=0x10)

    # Next cycle
    clock.tick()
    assert ebr.read(addr=0x10) == 0x3FFFF

    # Test read-only EBR
    ro_buf = [i for i in range(512)]
    ro_ebr = EBR(name="ro", size=512, width=18, read_only_buffer=ro_buf, clock=clock)
    assert ro_ebr.read(addr=42) == 42
    with pytest.raises(AssertionError):
        ro_ebr.write(addr=42, data=100)


def test_memory():
    clock = Clock()
    mem = Memory(rom_blocks=[None] * 8, clock=clock)
    mem.write(block=0, addr=5, data=0x1234)
    assert mem.read(block=0, addr=5) == 0x1234


def test_rom(tmp_path: Path):
    rom_file = tmp_path / "test.rom"
    rom_file.write_bytes(bytes([0x10, 0x20, 0x30, 0x40]))

    rom = Rom(size=4, rom_path=rom_file)
    assert rom.size == 4
    assert rom.load_byte(0) == 0x10
    assert rom.load_byte(3) == 0x40
    assert rom.load(1, 2) == bytearray([0x20, 0x30])

    with pytest.raises(IndexError):
        rom.load_byte(4)


def test_datapath_muxes():
    from fpu_emu.fpga_model import DatapathMuxes

    clock = Clock()
    regs = Registers(clock=clock)
    muxes = DatapathMuxes(regs)

    # Verify both muxes have 14 inputs (0..13)
    assert len(muxes.ha_mux._inputs) == 14
    assert len(muxes.hb_mux._inputs) == 14

    # Write distinct values into registers
    regs.al.write(0x11111111)
    regs.ah.write(0x22222222)
    regs.bl.write(0x33333333)
    regs.bh.write(0x44444444)
    regs.cl.write(0x55555555)
    regs.ch.write(0x66666666)
    regs.dl.write(0x77777777)
    regs.dh.write(0x88888888)
    regs.fl.write(0x99999999)
    regs.fh.write(0xAAAAAAAA)
    regs.ea.write(0x123)
    regs.eb.write(0x456)
    regs.c.write(0x1F)
    regs.imm.write(0x2AA)

    expected = {
        Reg.AL.value: 0x11111111,
        Reg.AH.value: 0x22222222,
        Reg.BL.value: 0x33333333,
        Reg.BH.value: 0x44444444,
        Reg.CL.value: 0x55555555,
        Reg.CH.value: 0x66666666,
        Reg.DL.value: 0x77777777,
        Reg.DH.value: 0x88888888,
        Reg.FL.value: 0x99999999,
        Reg.FH.value: 0xAAAAAAAA,
        Reg.EA.value: 0x123,
        Reg.EB.value: 0x456,
        Reg.C.value: 0x1F,
        Reg.IMM.value: 0x2AA,
    }

    for sel, exp_val in expected.items():
        muxes.ha_mux.select(sel)
        assert muxes.ha_mux.read_int() == exp_val, f"HA_MUX failed for sel={sel}"
        muxes.hb_mux.select(sel)
        assert muxes.hb_mux.read_int() == exp_val, f"HB_MUX failed for sel={sel}"

    # UPC and NONE are not inputs to HA or HB MUX, selecting them must raise AssertionError
    with pytest.raises(AssertionError):
        muxes.ha_mux.select(Reg.UPC.value)
    with pytest.raises(AssertionError):
        muxes.ha_mux.select(Reg.NONE.value)
    with pytest.raises(AssertionError):
        muxes.hb_mux.select(Reg.UPC.value)
    with pytest.raises(AssertionError):
        muxes.hb_mux.select(Reg.NONE.value)

