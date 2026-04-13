from amaranth.sim import Simulator
from tests.models.zx50_mem_card import Zx50MemCard
from tests.models.cpu_mock import Z80BackplaneMock


def test_card_initialization():
    dut = Zx50MemCard(card_id=0xA, boot_en=0)

    async def test_process(ctx):
        backplane = Z80BackplaneMock(ctx)
        backplane.plug_in_card(dut)
        await backplane.reset()

        latched_id = ctx.get(dut.controller.card_addr)
        latched_rom = ctx.get(dut.controller.has_boot_rom)
        rom_enabled = ctx.get(dut.controller.rom_enabled)
        page_ownership = ctx.get(dut.controller.page_ownership)

        print(f"[TEST] Verifying Latched State (Scenario 1: With ROM)...")
        assert latched_id == 0xA, f"FAIL: Expected ID 0xA, got {hex(latched_id)}"
        assert latched_rom == 1, f"FAIL: Expected Boot ROM 1, got {latched_rom}"
        assert rom_enabled == 1, f"FAIL: Expected ROM Enabled 1, got {rom_enabled}"
        assert page_ownership == 0x00FF, f"FAIL: Expected Page Ownership 0x00FF, got {hex(page_ownership)}"
        print("[TEST] Scenario 1 Passed.")

        # --- Scenario 2 ---
        # Physically "flick" the DIP switches and Jumper on the card
        dut.card_id = 0x5
        dut.boot_en = 1

        await backplane.reset()

        latched_id = ctx.get(dut.controller.card_addr)
        latched_rom = ctx.get(dut.controller.has_boot_rom)
        rom_enabled = ctx.get(dut.controller.rom_enabled)
        page_ownership = ctx.get(dut.controller.page_ownership)

        print(f"\n[TEST] Verifying Latched State (Scenario 2: No ROM)...")
        assert latched_id == 0x5, f"FAIL: Expected ID 0x5, got {hex(latched_id)}"
        assert latched_rom == 0, f"FAIL: Expected Boot ROM 0, got {latched_rom}"
        assert rom_enabled == 0, f"FAIL: Expected ROM Enabled 0, got {rom_enabled}"
        assert page_ownership == 0x0000, f"FAIL: Expected Page Ownership 0x0000, got {hex(page_ownership)}"
        print("[TEST] Scenario 2 Passed.")

    sim = Simulator(dut)
    sim.add_clock(20e-9)
    sim.add_testbench(test_process)
    with sim.write_vcd("waves/reset_test.vcd"):
        sim.run()


if __name__ == "__main__":
    test_card_initialization()