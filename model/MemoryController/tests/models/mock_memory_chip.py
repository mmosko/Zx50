from amaranth import *

MEM_512KB = 524288


class MockMemoryChip(Elaboratable):
    """Simulates a 512KB physical memory chip using a fast, sparse Python dictionary."""
    ground_truth = {}

    @classmethod
    def _generate_rom(cls):
        """Initialize a 32KB memory with a predictable program."""
        if not cls.ground_truth:
            x = 42
            for i in range(MEM_512KB):
                x = (5 * x + 1) % 256
                cls.ground_truth[i] = x

    def __init__(self, bus, ce_n, name, ro=False):
        self.bus = bus
        self.ce_n = ce_n
        self.ro = ro
        self.name = name

        self.ram = {}
        if self.ro:
            MockMemoryChip._generate_rom()
            self.ram = MockMemoryChip.ground_truth.copy()

        self.tb_data_out = Signal(8)
        self.tb_drive = Signal()

    def elaborate(self, platform):
        m = Module()
        with m.If(self.tb_drive):
            m.d.comb += self.bus.l_d.eq(self.tb_data_out)
        return m

    async def sim_process(self, ctx):
        """Background simulator process acting as the physical memory."""
        prev_we = 1
        prev_oe = 1

        while True:
            ce_n = ctx.get(self.ce_n)
            oe_n = ctx.get(self.bus.oe_n)
            we_n = ctx.get(self.bus.we_n)

            l_a = ctx.get(self.bus.l_a)
            atl_d = ctx.get(self.bus.atl_d)
            phys_addr = (atl_d << 11) | l_a

            # --- Async Read ---
            if ce_n == 0 and oe_n == 0 and we_n == 1:
                val = self.ram.get(phys_addr, None)

                # Only log on the falling edge of OE
                if prev_oe == 1:
                    if val is None:
                        print(f"[MOCK RAM WARNING] {self.name} Read from uninit phys addr: 0x{phys_addr:05X}")
                        val = 0xFF
                    else:
                        print(f"[MOCK RAM] {self.name} Read  0x{phys_addr:05X} = 0x{val:02X}")

                ctx.set(self.tb_data_out, val if val is not None else 0xFF)
                ctx.set(self.tb_drive, 1)
            else:
                ctx.set(self.tb_drive, 0)

            # --- Sync Write ---
            if not self.ro and ce_n == 0 and we_n == 0:
                # Only write and log on the falling edge of WE
                if prev_we == 1:
                    val = ctx.get(self.bus.l_d)
                    print(f"[MOCK RAM] {self.name} Write 0x{phys_addr:05X} = 0x{val:02X}")
                    self.ram[phys_addr] = val

            prev_we = we_n
            prev_oe = oe_n
            await ctx.tick()