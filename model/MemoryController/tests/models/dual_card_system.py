from amaranth import Elaboratable, Module

from tests.models.zx50_mem_card import Zx50MemCard


class DualCardSystem(Elaboratable):
    def __init__(self):
        # Card 0: ID 0x0, Has ROM (boot_en = 0)
        self.card0 = Zx50MemCard(card_id=0x0, boot_en=0)
        # Card 1: ID 0x1, No ROM (boot_en = 1)
        self.card1 = Zx50MemCard(card_id=0x1, boot_en=1)

    def elaborate(self, platform):
        m = Module()
        m.submodules.card0 = self.card0
        m.submodules.card1 = self.card1
        return m
