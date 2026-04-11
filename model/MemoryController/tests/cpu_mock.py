from dataclasses import dataclass
from zx50.zx50_mem_control import ZX50MemControl


@dataclass
class CardConfig:
    dut: ZX50MemControl
    card_id: int
    boot_en: int


class Z80BackplaneMock:
    """
    Simulates the shared physical backplane. Any cards "plugged in"
    will automatically receive all bus broadcasts simultaneously.
    """
    def __init__(self, ctx):
        self.ctx = ctx
        self.cards: list[CardConfig] = []

    def plug_in_card(self, dut: ZX50MemControl, card_id: int, boot_en: int):
        """Registers a card to receive backplane broadcasts."""
        self.cards.append(CardConfig(dut, card_id, boot_en))

    async def reset(self):
        """
        Simulates the backplane holding RESET low while the DIP switches
        drive the buffered Z80 control lines to set the Card ID.
        """
        print(f"[CPU MOCK] Asserting Reset for {len(self.cards)} card(s)...")

        # 1. Setup pins for all cards simultaneously
        for config in self.cards:
            self.ctx.set(config.dut.bp.reset_n, 0)
            self.ctx.set(config.dut.bp.b_z80_mreq_n, (config.card_id >> 3) & 1)
            self.ctx.set(config.dut.bp.b_z80_iorq_n, (config.card_id >> 2) & 1)
            self.ctx.set(config.dut.bp.b_z80_rd_n, (config.card_id >> 1) & 1)
            self.ctx.set(config.dut.bp.b_z80_wr_n, config.card_id & 1)
            self.ctx.set(config.dut.bp.boot_en_n, config.boot_en)

        # 2. Hold reset to let the sync blocks latch
        for _ in range(5):
            await self.ctx.tick()

        # 3. Release Reset for all cards
        print("[CPU MOCK] Releasing Reset.")
        for config in self.cards:
            self.ctx.set(config.dut.bp.reset_n, 1)

        # 4. Wait one more clock cycle for FSMs to settle
        await self.ctx.tick()

    async def mmu_out(self, port: int, logical_page: int):
        """
        Simulates Z80 `OUT (C), r` across all plugged-in cards.
        A0-A7 holds the Port. A8-A15 holds the data (logical page).
        """
        addr = (logical_page << 8) | port
        print(f"[CPU MOCK] OUT (0x{port:02X}), Page {logical_page}")

        # 1. Drive the bus for all cards
        for config in self.cards:
            self.ctx.set(config.dut.bp.z80_a, addr)
            self.ctx.set(config.dut.bp.b_z80_iorq_n, 0)
            self.ctx.set(config.dut.bp.b_z80_wr_n, 0)

        # 2. Wait for FSMs to react (IDLE -> Z80_IORQ_MMU_SET)
        await self.ctx.tick()
        await self.ctx.tick()

        # 3. End cycle for all cards
        for config in self.cards:
            self.ctx.set(config.dut.bp.b_z80_iorq_n, 1)
            self.ctx.set(config.dut.bp.b_z80_wr_n, 1)

        # 4. Wait for FSMs to return to IDLE
        await self.ctx.tick()
        await self.ctx.tick()

    async def mem_write(self, addr: int, data: int):
        """Simulates the Z80 writing a byte to memory."""
        print(f"[CPU MOCK] Mem Write -> Addr: 0x{addr:04X}, Data: 0x{data:02X}")

        for config in self.cards:
            self.ctx.set(config.dut.bp.z80_a, addr)
            self.ctx.set(config.dut.loc.l_d, data)  # Drive the local data bus directly for the mock
            self.ctx.set(config.dut.bp.b_z80_mreq_n, 0)
            self.ctx.set(config.dut.bp.b_z80_wr_n, 0)

        await self.ctx.tick()
        await self.ctx.tick()

        for config in self.cards:
            self.ctx.set(config.dut.bp.b_z80_mreq_n, 1)
            self.ctx.set(config.dut.bp.b_z80_wr_n, 1)

        await self.ctx.tick()
        await self.ctx.tick()

    async def mem_read(self, addr: int):
        """Simulates the Z80 reading a byte from memory."""
        print(f"[CPU MOCK] Mem Read  <- Addr: 0x{addr:04X}")

        for config in self.cards:
            self.ctx.set(config.dut.bp.z80_a, addr)
            self.ctx.set(config.dut.bp.b_z80_mreq_n, 0)
            self.ctx.set(config.dut.bp.b_z80_rd_n, 0)

        await self.ctx.tick()
        await self.ctx.tick()

        for config in self.cards:
            self.ctx.set(config.dut.bp.b_z80_mreq_n, 1)
            self.ctx.set(config.dut.bp.b_z80_rd_n, 1)

        await self.ctx.tick()
        await self.ctx.tick()
