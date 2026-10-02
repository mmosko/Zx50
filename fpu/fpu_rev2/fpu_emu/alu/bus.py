"""Hardware bus interface helpers for ALU operations.

Per SystemDesign.md Section 3.3 (Shared Datapath Buses & Multiplexers):
- HA_BUS[31:0]: 2:1 PFU multiplexer selecting AL (HalfSelect.LO) or AH (HalfSelect.HI).
- HB_BUS[31:0]: 8:1 (or 2-stage) multiplexer selecting BL, BH, DL, DH, FL, FH, AL, AH, EA, EB, C.
- RES_BUS[31:0]: 6:1 result bus selecting active execution source.
- Latching into registers is controlled by dedicated clock enable pins (WE_AL .. WE_FH, WE_EA, WE_EB, WE_C).

All ALU units MUST read inputs strictly from HA_BUS and/or HB_BUS, and write outputs
strictly via RES_BUS. Direct access to register file internal state is forbidden.
"""

from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import HalfSelect, Reg, Registers


def read_bus32(hw: Hardware, reg: Reg) -> int:
    """Reads a 32-bit register strictly through the HA_BUS or HB_BUS multiplexers."""
    if not reg.is_32() and reg not in (Reg.C, Reg.EA, Reg.EB):
        raise ValueError(f"Expected 32-bit register or control register, got {reg}")

    if reg in (Reg.AL, Reg.AH):
        half = HalfSelect.LO if reg == Reg.AL else HalfSelect.HI
        if hw.reg.ha_bus_half != half or hw.reg.last_ha_tick is None:
            if hw.reg.last_ha_tick == hw.clock.cycles:
                hw.clock.tick(1)
            hw.reg.set_ha_bus_mux(half)
        return Registers.to_int(hw.reg.read_ha_bus())
    else:
        half = HalfSelect.HI if reg in (Reg.BH, Reg.DH, Reg.FH) else HalfSelect.LO
        if (
            hw.reg.hb_bus_half != half
            or hw.reg.hb_bus_reg != reg
            or hw.reg.last_hb_tick is None
        ):
            if hw.reg.last_hb_tick == hw.clock.cycles:
                hw.clock.tick(1)
            hw.reg.set_hb_bus_mux(half, reg)
        return Registers.to_int(hw.reg.read_hb_bus())


def write_bus32(hw: Hardware, reg: Reg, val: int) -> None:
    """Drives result strictly via RES_BUS to destination register."""
    if not reg.is_32() and reg not in (Reg.C, Reg.EA, Reg.EB):
        raise ValueError(f"Expected 32-bit register or control register, got {reg}")
    if hw.reg.last_res_tick == hw.clock.cycles:
        hw.clock.tick(1)
    hw.reg.set_res_bus(reg, Registers.from_int(val & 0xFFFFFFFF, 4))


def read_bus64(hw: Hardware, reg: Reg) -> int:
    """Reads 64-bit register pair strictly via HA_BUS/HB_BUS multiplexers."""
    if not reg.is_64():
        raise ValueError(f"Expected 64-bit register, got {reg}")

    if reg == Reg.AX:
        need_ha = hw.reg.ha_bus_half != HalfSelect.LO or hw.reg.last_ha_tick is None
        need_hb = (
            hw.reg.hb_bus_half != HalfSelect.HI
            or hw.reg.hb_bus_reg != Reg.AX
            or hw.reg.last_hb_tick is None
        )
        if (need_ha and hw.reg.last_ha_tick == hw.clock.cycles) or (
            need_hb and hw.reg.last_hb_tick == hw.clock.cycles
        ):
            hw.clock.tick(1)

        if need_ha:
            hw.reg.set_ha_bus_mux(HalfSelect.LO)
        lo_bytes = hw.reg.read_ha_bus()

        if need_hb:
            hw.reg.set_hb_bus_mux(HalfSelect.HI, Reg.AX)
        hi_bytes = hw.reg.read_hb_bus()

        return Registers.to_int(lo_bytes + hi_bytes)
    else:
        lo = read_bus32(hw, reg.lo_half())
        hi = read_bus32(hw, reg.hi_half())
        return (hi << 32) | lo


def write_bus64(hw: Hardware, reg: Reg, val: int) -> None:
    """Writes 64-bit result strictly via RES_BUS across 2 clock cycles."""
    if not reg.is_64():
        raise ValueError(f"Expected 64-bit register, got {reg}")
    write_bus32(hw, reg.lo_half(), val & 0xFFFFFFFF)
    hw.clock.tick(1)
    write_bus32(hw, reg.hi_half(), (val >> 32) & 0xFFFFFFFF)
