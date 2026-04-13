from amaranth.sim import Simulator

from tests.models.cpu_mock import Z80BackplaneMock
from tests.models.dual_card_system import DualCardSystem


def test_distributed_mmu():
    dut = DualCardSystem()

    async def test_process(ctx):
        backplane = Z80BackplaneMock(ctx)
        backplane.plug_in_card(dut.card0)
        backplane.plug_in_card(dut.card1)

        await backplane.reset()

        # NOTE: We access the internal registers through `.controller.` now
        c0_mask = ctx.get(dut.card0.controller.page_ownership)
        c1_mask = ctx.get(dut.card1.controller.page_ownership)
        print(f"Boot State -> Card 0 Mask: {hex(c0_mask)} | Card 1 Mask: {hex(c1_mask)}")
        assert c0_mask == 0x00FF, "Card 0 failed to claim boot pages"
        assert c1_mask == 0x0000, "Card 1 falsely claimed boot pages"

        # Initialize Page 8 on Card 0
        await backplane.mmu_out(port=0x30, logical_page=8, data=0x12)
        c0_mask = ctx.get(dut.card0.controller.page_ownership)
        c1_mask = ctx.get(dut.card1.controller.page_ownership)
        assert c0_mask == 0x01FF, f"Card 0 failed to add page 8. Got {hex(c0_mask)}"
        assert c1_mask == 0x0000, "Card 1 altered unexpectedly."

        # Initialize Page 9 on Card 1
        await backplane.mmu_out(port=0x31, logical_page=9, data=0x12)
        c0_mask = ctx.get(dut.card0.controller.page_ownership)
        c1_mask = ctx.get(dut.card1.controller.page_ownership)
        assert c0_mask == 0x01FF, "Card 0 altered unexpectedly."
        assert c1_mask == 0x0200, f"Card 1 failed to add page 9. Got {hex(c1_mask)}"

        # REMAP Page 9 from Card 1 to Card 0
        print("\n[TEST] Remapping Page 9 from Card 1 to Card 0...")
        await backplane.mmu_out(port=0x30, logical_page=9, data=0x12)
        c0_mask = ctx.get(dut.card0.controller.page_ownership)
        c1_mask = ctx.get(dut.card1.controller.page_ownership)
        assert c0_mask == 0x03FF, f"Card 0 failed to steal page 9. Got {hex(c0_mask)}"
        assert c1_mask == 0x0000, f"Card 1 FAILED to yield page 9! Collision imminent! Got {hex(c1_mask)}"
        print("\n[TEST] SUCCESS! Distributed MMU Snooping Works Perfectly.")

    sim = Simulator(dut)
    sim.add_clock(20e-9)
    sim.add_testbench(test_process)
    with sim.write_vcd("waves/mmu_snoop_test.vcd"):
        sim.run()

if __name__ == "__main__":
    test_distributed_mmu()
