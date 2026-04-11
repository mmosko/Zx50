from amaranth.sim import Simulator
from zx50.zx50_mem_control import ZX50MemControl
from tests.cpu_mock import Z80BackplaneMock


def test_card_initialization():
    # 1. Instantiate the Device Under Test (DUT)
    dut = ZX50MemControl()

    # 2. Define the test process
    async def test_process(ctx):
        # Setup the virtual backplane
        backplane = Z80BackplaneMock(ctx)

        # =====================================================================
        # SCENARIO 1: Card WITH Boot ROM (boot_en = 0)
        # =====================================================================
        test_id_1 = 0xA
        test_boot_en_1 = 0

        # Plug in the card and reset the backplane
        backplane.plug_in_card(dut, card_id=test_id_1, boot_en=test_boot_en_1)
        await backplane.reset()

        # VERIFY: Read the internal registers using ctx.get()
        latched_id = ctx.get(dut.card_addr)
        latched_rom = ctx.get(dut.has_boot_rom)
        rom_enabled = ctx.get(dut.rom_enabled)
        page_ownership = ctx.get(dut.page_ownership)

        print(f"[TEST] Verifying Latched State (Scenario 1: With ROM)...")
        assert latched_id == test_id_1, f"FAIL: Expected ID {hex(test_id_1)}, got {hex(latched_id)}"
        assert latched_rom == 1, f"FAIL: Expected Boot ROM 1, got {latched_rom}"

        # Verify MMU Boot Initialization
        assert rom_enabled == 1, f"FAIL: Expected ROM Enabled 1, got {rom_enabled}"
        assert page_ownership == 0x00FF, f"FAIL: Expected Page Ownership 0x00FF, got {hex(page_ownership)}"
        print("[TEST] Scenario 1 Passed.")

        # =====================================================================
        # SCENARIO 2: Card WITHOUT Boot ROM (boot_en = 1)
        # =====================================================================
        test_id_2 = 0x5
        test_boot_en_2 = 1

        # "Unplug" the old configuration and re-plug with new hardware straps
        backplane.cards.clear()
        backplane.plug_in_card(dut, card_id=test_id_2, boot_en=test_boot_en_2)

        # Run our CPU mock sequence again
        await backplane.reset()

        # VERIFY: Read the internal registers
        latched_id = ctx.get(dut.card_addr)
        latched_rom = ctx.get(dut.has_boot_rom)
        rom_enabled = ctx.get(dut.rom_enabled)
        page_ownership = ctx.get(dut.page_ownership)

        print(f"\n[TEST] Verifying Latched State (Scenario 2: No ROM)...")
        assert latched_id == test_id_2, f"FAIL: Expected ID {hex(test_id_2)}, got {hex(latched_id)}"
        assert latched_rom == 0, f"FAIL: Expected Boot ROM 0, got {latched_rom}"

        # Verify MMU Boot Initialization
        assert rom_enabled == 0, f"FAIL: Expected ROM Enabled 0, got {rom_enabled}"
        assert page_ownership == 0x0000, f"FAIL: Expected Page Ownership 0x0000, got {hex(page_ownership)}"
        print("[TEST] Scenario 2 Passed.")

        print("\n[TEST] SUCCESS! Card initialized and latched perfectly in both configurations.")

    # 4. Configure and run the Simulator
    sim = Simulator(dut)
    sim.add_clock(20e-9)
    sim.add_testbench(test_process)

    # Generate the waveform file
    with sim.write_vcd("waves/reset_test.vcd"):
        sim.run()


if __name__ == "__main__":
    test_card_initialization()
