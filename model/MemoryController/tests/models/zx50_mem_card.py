from amaranth import Module, Elaboratable, Signal

from tests.models.mock_atl_sram import MockATLSRAM
from tests.models.mock_memory_chip import MockMemoryChip
from zx50.zx50_mem_control import ZX50MemControl


class Zx50MemCard(Elaboratable):
    """Simulates the physical ZX50_Mem_Card PCB (CPLD + SRAM + RAM + ROM)"""

    def __init__(self, card_id: int = 0x0, boot_en: int = 1):
        # Physical DIP switch / Jumper straps on the board
        self.card_id = card_id
        self.boot_en = boot_en

        # The CPLD Core
        self.controller = ZX50MemControl()

        # Expose the edge connectors for the testbench
        self.bp = self.controller.bp
        self.loc = self.controller.loc

        # On-Board Chips
        self.sram = MockATLSRAM(self.loc, name=f'Card{self.card_id}ATL')
        self.ram0 = MockMemoryChip(self.loc, self.loc.ram_ce0_n, name=f'Card{self.card_id}RAM0', ro=False)
        self.ram1 = MockMemoryChip(self.loc, self.loc.ram_ce1_n, name=f'Card{self.card_id}RAM1', ro=False)
        self.rom = MockMemoryChip(self.loc, self.loc.rom_ce2_n, name=f'Card{self.card_id}ROM', ro=True)

        # --- Testbench Injection Pins ---
        # Simulates the Z80 Backplane Data bus physically plugging into the card
        self.tb_z80_d_in = Signal(8)
        self.tb_z80_d_out = Signal(8)

    def register_sim(self, sim):
        """Registers the background simulation processes for the memory chips."""
        sim.add_testbench(self.sram.sim_process)
        sim.add_testbench(self.ram0.sim_process)
        sim.add_testbench(self.ram1.sim_process)
        sim.add_testbench(self.rom.sim_process)

    def elaborate(self, platform):
        m = Module()

        m.submodules.controller = self.controller
        m.submodules.sram = self.sram
        m.submodules.ram0 = self.ram0
        m.submodules.ram1 = self.ram1
        m.submodules.rom = self.rom

        # =====================================================================
        # MOCK TRANSCEIVER (74LVC245)
        # Bridges the Backplane Data Bus to the Local Data Bus based on CPLD pins
        # =====================================================================

        # Write: Z80 -> Card (CPLD drops OE and sets DIR to 1)
        with m.If((self.bp.z80_d_oe_n == 0) & (self.bp.d_dir == 1)):
            m.d.comb += self.loc.l_d.eq(self.tb_z80_d_in)

        # Read: Card -> Z80 (CPLD drops OE and sets DIR to 0)
        with m.If((self.bp.z80_d_oe_n == 0) & (self.bp.d_dir == 0)):
            m.d.comb += self.tb_z80_d_out.eq(self.loc.l_d)

        return m