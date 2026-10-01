"""Unit tests for immediate literal load (ld.py) operations."""

import pytest
from fpu_emu.hardware import Hardware
from fpu_emu.memory import ld
from fpu_emu.memory.registers import Reg, Registers, StatusFlag
from fpu_emu.tests.testharness import RegTestHarness


class TestLd:
    """Test suite for ld32, ld64, ld_c, ld_sp, ld_osp, and ld dispatch."""

    def setup_method(self):
        self.hw = Hardware()
        self.reg = RegTestHarness(self.hw.reg)

    def test_ld32_general_registers(self):
        start_cycles = self.hw.clock.cycles
        ld.ld32(self.hw, Reg.AL, 0x12345678)
        assert self.hw.clock.cycles == start_cycles + 2
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 0x12345678

        # Load negative int / sign extension
        ld.ld32(self.hw, Reg.BL, -1)
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 0xFFFFFFFF

        # Load 0
        ld.ld32(self.hw, Reg.FL, 0)
        assert Registers.to_int(self.reg.peek(Reg.FL)) == 0

        # Load high half register AH
        ld.ld32(self.hw, Reg.AH, 0xAABBCCDD)
        assert Registers.to_int(self.reg.peek(Reg.AH)) == 0xAABBCCDD

    def test_ld32_bytes_and_bytearray(self):
        # Exact 4 bytes
        ld.ld32(self.hw, Reg.DL, b"\x11\x22\x33\x44")
        assert self.reg.peek(Reg.DL) == bytearray(b"\x11\x22\x33\x44")

        # Short bytes (zero-padded)
        ld.ld32(self.hw, Reg.DH, bytearray(b"\xaa\xbb"))
        assert self.reg.peek(Reg.DH) == bytearray(b"\xaa\xbb\x00\x00")

        # Longer bytes (truncated to 4)
        ld.ld32(self.hw, Reg.FH, b"\x01\x02\x03\x04\x05\x06")
        assert self.reg.peek(Reg.FH) == bytearray(b"\x01\x02\x03\x04")

    def test_ld32_exponent_registers(self):
        ld.ld32(self.hw, Reg.EA, 0x0123)
        assert self.hw.reg.ea == 0x0123

        ld.ld32(self.hw, Reg.EB, 0x0FFF)
        assert self.hw.reg.eb == 0x0FFF

    def test_ld64_compound_registers(self):
        val = 0x0123456789ABCDEF
        start_cycles = self.hw.clock.cycles
        ld.ld64(self.hw, Reg.AX, val)
        assert self.hw.clock.cycles == start_cycles + 3
        assert Registers.to_int(self.reg.peek(Reg.AX)) == val

        # 64-bit negative int
        ld.ld64(self.hw, Reg.BX, -1)
        assert Registers.to_int(self.reg.peek(Reg.BX)) == 0xFFFFFFFFFFFFFFFF

        # 64-bit bytes
        data = b"\x10\x20\x30\x40\x50\x60\x70\x80"
        ld.ld64(self.hw, Reg.DX, data)
        assert self.reg.peek(Reg.DX) == bytearray(data)

        # 64-bit short bytes (zero-padded)
        ld.ld64(self.hw, Reg.FX, b"\x01\x02\x03\x04")
        assert self.reg.peek(Reg.FX) == bytearray(b"\x01\x02\x03\x04\x00\x00\x00\x00")

    def test_ld_control_registers(self):
        # LD C
        start_cycles = self.hw.clock.cycles
        ld.ld_c(self.hw, 24)
        assert self.hw.clock.cycles == start_cycles + 1
        assert self.hw.reg.c == 24

        # Masked to 6 bits
        ld.ld_c(self.hw, 0xFF)
        assert self.hw.reg.c == 0x3F

        # LD SP
        start_cycles = self.hw.clock.cycles
        ld.ld_sp(self.hw, 0)
        assert self.hw.clock.cycles == start_cycles + 1
        assert self.hw.reg.sp == 0
        ld.ld_sp(self.hw, 16)
        assert self.hw.reg.sp == 16

        # LD OSP
        start_cycles = self.hw.clock.cycles
        ld.ld_osp(self.hw, 0)
        assert self.hw.clock.cycles == start_cycles + 1
        assert self.hw.reg.osp == 0
        ld.ld_osp(self.hw, 8)
        assert self.hw.reg.osp == 8

    def test_ld_generic_dispatch(self):
        # Dispatch SP, OSP, C
        ld.ld(self.hw, Reg.SP, 0)
        assert self.hw.reg.sp == 0
        ld.ld(self.hw, Reg.OSP, 0)
        assert self.hw.reg.osp == 0
        ld.ld(self.hw, Reg.C, 16)
        assert self.hw.reg.c == 16

        # Dispatch 64-bit
        ld.ld(self.hw, Reg.FX, 0xCAFEBABE11223344)
        assert Registers.to_int(self.reg.peek(Reg.FX)) == 0xCAFEBABE11223344

        # Dispatch 32-bit
        ld.ld(self.hw, Reg.FL, 0x12344321)
        assert Registers.to_int(self.reg.peek(Reg.FL)) == 0x12344321

        # String register names
        ld.ld32(self.hw, "BL", 0x1234)
        assert Registers.to_int(self.reg.peek(Reg.BL)) == 0x1234
        ld.ld64(self.hw, "BX", 0x5678)
        assert Registers.to_int(self.reg.peek(Reg.BX)) == 0x5678

        ld.ld(self.hw, "AL", 0x55)
        assert Registers.to_int(self.reg.peek(Reg.AL)) == 0x55
        ld.ld(self.hw, "AX", 0x99)
        assert Registers.to_int(self.reg.peek(Reg.AX)) == 0x99
        ld.ld(self.hw, "SP", 4)
        assert self.hw.reg.sp == 4
        ld.ld(self.hw, "OSP", 2)
        assert self.hw.reg.osp == 2
        ld.ld(self.hw, "C", 5)
        assert self.hw.reg.c == 5

        # Bytes imm for control regs
        ld.ld(self.hw, "SP", b"\x08")
        assert self.hw.reg.sp == 8
        ld.ld(self.hw, "OSP", b"\x04")
        assert self.hw.reg.osp == 4
        ld.ld(self.hw, "C", b"\x0a")
        assert self.hw.reg.c == 10

    def test_flags_unaffected(self):
        self.hw.reg.set_flag(StatusFlag.ZERO, True)
        self.hw.reg.set_flag(StatusFlag.SIGN, True)
        self.hw.reg.set_flag(StatusFlag.CARRY, True)
        self.hw.reg.set_flag(StatusFlag.OVERFLOW, True)

        ld.ld32(self.hw, Reg.AL, 0)
        ld.ld64(self.hw, Reg.AX, 0)
        ld.ld_c(self.hw, 0)
        ld.ld_sp(self.hw, 0)
        ld.ld_osp(self.hw, 0)

        assert self.hw.reg.get_flag(StatusFlag.ZERO)
        assert self.hw.reg.get_flag(StatusFlag.SIGN)
        assert self.hw.reg.get_flag(StatusFlag.CARRY)
        assert self.hw.reg.get_flag(StatusFlag.OVERFLOW)

    def test_invalid_operands(self):
        with pytest.raises(ValueError, match="ld32 called with incompatible register"):
            ld.ld32(self.hw, Reg.AX, 0)

        with pytest.raises(ValueError, match="ld32 called with incompatible register"):
            ld.ld32(self.hw, Reg.SP, 0)

        with pytest.raises(ValueError, match="ld64 requires 64-bit compound register"):
            ld.ld64(self.hw, Reg.AL, 0)

        with pytest.raises(ValueError, match="Unsupported register for LD"):
            ld.ld(self.hw, Reg.STATUS, 0)

        with pytest.raises(TypeError, match="Invalid type for immediate operand"):
            ld.ld32(self.hw, Reg.AL, "not_a_number")  # type: ignore
