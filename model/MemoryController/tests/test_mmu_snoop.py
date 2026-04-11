from amaranth import *
from amaranth.sim import Simulator
from zx50.zx50_mem_control import ZX50MemControl
from tests.cpu_mock import Z80BackplaneMock


class DualCardSystem(Elaboratable):
    def __init__(self):
        self.card0 = ZX50MemControl()
        self.card1 = ZX50MemControl()

    def elaborate(self, platform):
        m = Module()
        # Instantiate both cards in the same module so the simulator can run them together
        m.submodules.card0 = self.card0
        m.submodules.card1 = self.card1
        return m


def test_distributed_mmu():
    dut = DualCardSystem()

    async def test_process(ctx):
        # Setup the virtual backplane
        backplane = Z80BackplaneMock(ctx)

        # Card 0: ID 0x0, Has ROM (Boot = 0)
        backplane.plug_in_card(dut.card0, card_id=0x0, boot_en=0)
        # Card 1: ID 0x1, No ROM (Boot = 1)
        backplane.plug_in_card(dut.card1, card_id=0x1, boot_en=1)

        # ---------------------------------------------------------------------
        # Boot Phase
        # ---------------------------------------------------------------------
        await backplane.reset()

        c0_mask = ctx.get(dut.card0.page_ownership)
        c1_mask = ctx.get(dut.card1.page_ownership)
        print(f"Boot State -> Card 0 Mask: {hex(c0_mask)} | Card 1 Mask: {hex(c1_mask)}")
        assert c0_mask == 0x00FF, "Card 0 failed to claim boot pages"
        assert c1_mask == 0x0000, "Card 1 falsely claimed boot pages"

        # ---------------------------------------------------------------------
        # Step 1: Initialize Page 8 on Card 0
        # ---------------------------------------------------------------------
        await backplane.mmu_out(port=0x30, logical_page=8)

        c0_mask = ctx.get(dut.card0.page_ownership)
        c1_mask = ctx.get(dut.card1.page_ownership)
        print(f"After Step 1 -> Card 0 Mask: {hex(c0_mask)} | Card 1 Mask: {hex(c1_mask)}")
        assert c0_mask == 0x01FF, f"Card 0 failed to add page 8. Got {hex(c0_mask)}"
        assert c1_mask == 0x0000, "Card 1 altered unexpectedly."

        # ---------------------------------------------------------------------
        # Step 2: Initialize Page 9 on Card 1
        # ---------------------------------------------------------------------
        await backplane.mmu_out(port=0x31, logical_page=9)

        c0_mask = ctx.get(dut.card0.page_ownership)
        c1_mask = ctx.get(dut.card1.page_ownership)
        print(f"After Step 2 -> Card 0 Mask: {hex(c0_mask)} | Card 1 Mask: {hex(c1_mask)}")
        assert c0_mask == 0x01FF, "Card 0 altered unexpectedly."
        assert c1_mask == 0x0200, f"Card 1 failed to add page 9. Got {hex(c1_mask)}"

        # ---------------------------------------------------------------------
        # Step 3: REMAP Page 9 from Card 1 to Card 0 (The Snoop Test!)
        # ---------------------------------------------------------------------
        print("\n[TEST] Remapping Page 9 from Card 1 to Card 0...")
        await backplane.mmu_out(port=0x30, logical_page=9)

        c0_mask = ctx.get(dut.card0.page_ownership)
        c1_mask = ctx.get(dut.card1.page_ownership)
        print(f"After Step 3 -> Card 0 Mask: {hex(c0_mask)} | Card 1 Mask: {hex(c1_mask)}")

        # VERIFY: Card 0 should have added bit 9 (0x01FF + 0x0200 = 0x03FF)
        assert c0_mask == 0x03FF, f"Card 0 failed to steal page 9. Got {hex(c0_mask)}"

        # VERIFY: Card 1 should have snooped port 0x30 and DROPPED bit 9
        assert c1_mask == 0x0000, f"Card 1 FAILED to yield page 9! Collision imminent! Got {hex(c1_mask)}"

        print("\n[TEST] SUCCESS! Distributed MMU Snooping Works Perfectly.")

    # Configure and Run the Simulator
    sim = Simulator(dut)
    sim.add_clock(20e-9)
    sim.add_testbench(test_process)

    with sim.write_vcd("waves/mmu_snoop_test.vcd"):
        sim.run()


if __name__ == "__main__":
    test_distributed_mmu()