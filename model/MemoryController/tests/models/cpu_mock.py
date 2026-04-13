from tests.models.zx50_mem_card import Zx50MemCard


class Z80BackplaneMock:
    """
    Simulates the shared physical backplane. Any cards "plugged in"
    will automatically receive all bus broadcasts simultaneously.
    """

    def __init__(self, ctx):
        self.ctx = ctx
        self.cards: list[Zx50MemCard] = []

    def plug_in_card(self, card: Zx50MemCard):
        self.cards.append(card)

    async def reset(self):
        print(f"[CPU MOCK] Asserting Reset for {len(self.cards)} card(s)...")
        for card in self.cards:
            self.ctx.set(card.bp.reset_n, 0)
            self.ctx.set(card.bp.b_z80_mreq_n, (card.card_id >> 3) & 1)
            self.ctx.set(card.bp.b_z80_iorq_n, (card.card_id >> 2) & 1)
            self.ctx.set(card.bp.b_z80_rd_n, (card.card_id >> 1) & 1)
            self.ctx.set(card.bp.b_z80_wr_n, card.card_id & 1)
            self.ctx.set(card.bp.boot_en_n, card.boot_en)

        for _ in range(5):
            await self.ctx.tick()

        print("[CPU MOCK] Releasing Reset.")
        for card in self.cards:
            self.ctx.set(card.bp.reset_n, 1)
            self.ctx.set(card.bp.b_z80_mreq_n, 1)
            self.ctx.set(card.bp.b_z80_iorq_n, 1)
            self.ctx.set(card.bp.b_z80_rd_n, 1)
            self.ctx.set(card.bp.b_z80_wr_n, 1)
        await self.ctx.tick()

    async def mmu_out(self, port: int, logical_page: int, data: int = 0x00):
        print(f"[CPU MOCK] MMU_OUT (0x{port:02X}), Page {logical_page}, Data (Phys Page): 0x{data:02X}")
        await self.io_write(port, data, logical_page)

    async def io_write(self, port: int, data: int, ah: int):
        """ Z80 I/O Write Cycle Timing """
        addr = (ah & 0xFF) << 8 | (port & 0xFF)
        print(f"[CPU MOCK] IO_WRITE port 0x{port:02X}, Data: 0x{data:02X}, AH: 0x{ah:02X}")

        # T1: Address and Data Valid
        for card in self.cards:
            self.ctx.set(card.bp.z80_a, addr)
            self.ctx.set(card.tb_z80_d_in, data)
        await self.ctx.tick()

        # T2: IORQ and WR go low
        for card in self.cards:
            self.ctx.set(card.bp.b_z80_iorq_n, 0)
            self.ctx.set(card.bp.b_z80_wr_n, 0)
        await self.ctx.tick()

        # Tw: Z80 automatically inserts a Wait state for I/O
        await self.ctx.tick()

        # T3: End of cycle
        for card in self.cards:
            self.ctx.set(card.bp.b_z80_iorq_n, 1)
            self.ctx.set(card.bp.b_z80_wr_n, 1)
        await self.ctx.tick()
        await self.ctx.tick()  # Pipeline flush

    async def mem_write(self, addr: int, data: int):
        """ Z80 Memory Write Cycle Timing """
        print(f"[CPU MOCK] Mem Write -> Addr: 0x{addr:04X}, Data: 0x{data:02X}")
        for card in self.cards:
            self.ctx.set(card.bp.z80_a, addr)
            self.ctx.set(card.tb_z80_d_in, data)
            self.ctx.set(card.bp.b_z80_mreq_n, 0)
        await self.ctx.tick()

        for card in self.cards:
            self.ctx.set(card.bp.b_z80_wr_n, 0)

        # Hold the bus open! Gives the Python Dictionary time to evaluate.
        for _ in range(4):
            await self.ctx.tick()

        for card in self.cards:
            self.ctx.set(card.bp.b_z80_mreq_n, 1)
            self.ctx.set(card.bp.b_z80_wr_n, 1)
        await self.ctx.tick()

    async def mem_read(self, addr: int) -> int:
        """ Z80 Memory Read Cycle Timing """
        print(f"[CPU MOCK] Mem Read  <- Addr: 0x{addr:04X}")
        for card in self.cards:
            self.ctx.set(card.bp.z80_a, addr)
            self.ctx.set(card.bp.b_z80_mreq_n, 0)
        await self.ctx.tick()

        for card in self.cards:
            self.ctx.set(card.bp.b_z80_rd_n, 0)

        # Hold the bus open! Gives the CPLD and Python Dictionary time to evaluate.
        for _ in range(4):
            await self.ctx.tick()

        # DATA CAPTURE: Sample safely before ending the cycle!
        captured_data = 0xFF
        for card in self.cards:
            if self.ctx.get(card.bp.z80_d_oe_n) == 0 and self.ctx.get(card.bp.d_dir) == 0:
                captured_data = self.ctx.get(card.tb_z80_d_out)

        for card in self.cards:
            self.ctx.set(card.bp.b_z80_mreq_n, 1)
            self.ctx.set(card.bp.b_z80_rd_n, 1)

        await self.ctx.tick()
        await self.ctx.tick()

        return captured_data