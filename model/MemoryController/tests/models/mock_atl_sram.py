from amaranth import *


class MockATLSRAM(Elaboratable):
    def __init__(self, bus, name):
        self.name = name
        self.bus = bus
        # We use a Signal for each slot to ensure instant combinatorial visibility
        self.slots = [Signal(8, reset=0x00, name=f"{name}_s{i}") for i in range(16)]

    def elaborate(self, platform):
        m = Module()

        # --- Instant Combinatorial Read ---
        # This ensures that as soon as atl_a changes, atl_d changes in 0ns
        with m.If((self.bus.atl_ce_n == 0) & (self.bus.atl_oe_n == 0) & (self.bus.atl_we_n == 1)):
            for i in range(16):
                with m.If(self.bus.atl_a == i):
                    m.d.comb += self.bus.atl_d.eq(self.slots[i])

        # --- Instant Sync Write ---
        # We use sync here to latch the data, but the 'slots' Signals
        # will propagate to the 'comb' read above immediately on the next delta
        with m.If((self.bus.atl_ce_n == 0) & (self.bus.atl_we_n == 0)):
            for i in range(16):
                with m.If(self.bus.atl_a == i):
                    m.d.sync += self.slots[i].eq(self.bus.l_d)

        return m

    async def sim_process(self, ctx):
        """Monitor for logging"""
        prev_we = 1
        while True:
            ce_n = ctx.get(self.bus.atl_ce_n)
            we_n = ctx.get(self.bus.atl_we_n)
            addr = ctx.get(self.bus.atl_a)

            if ce_n == 0 and we_n == 0 and prev_we == 1:
                val = ctx.get(self.bus.l_d)
                print(f"[MOCK ATL] {self.name} Write 0x{addr:02X} = 0x{val:02X}")

            prev_we = we_n
            await ctx.tick()