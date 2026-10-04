"""Unified physical hardware state container for Zx50 FPU."""

from dataclasses import dataclass, field
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.registers import Registers
from fpu_emu.hardware.memory import Ram
from fpu_emu.hardware.rom import Rom


@dataclass
class Hardware:
    """Encapsulates the core physical hardware state: Clock, Registers, SysMEM RAM, and Flash ROM.

    All components are guaranteed to exist and are never None.
    """

    clock: Clock = field(default_factory=Clock)
    reg: Registers = field(default_factory=Registers)
    mem: Ram = field(default_factory=Ram)
    rom: Rom = field(default_factory=Rom)

    def __post_init__(self):
        self.reg.bind_clock(self.clock)

    def reset(self, clear_mem: bool = False):
        """Performs a master hardware reset on clock, registers, and optionally RAM."""
        self.clock.reset()
        self.reg.reset()
        self.reg.bind_clock(self.clock)
        if clear_mem:
            self.mem.clear()
