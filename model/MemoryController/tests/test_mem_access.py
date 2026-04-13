from amaranth.sim import Simulator

from tests.models.cpu_mock import Z80BackplaneMock
from tests.models.dual_card_system import DualCardSystem


def test_memory_read_write():
    dut = DualCardSystem()

    async def test_process(ctx):
        backplane = Z80BackplaneMock(ctx)
        backplane.plug_in_card(dut.card0)
        backplane.plug_in_card(dut.card1)

        await backplane.reset()

        # 1. Configure the MMU
        await backplane.mmu_out(port=0x30, logical_page=8, data=0x02)
        await backplane.mmu_out(port=0x31, logical_page=9, data=0x05)

        # 2. Write Data to RAM
        await backplane.mem_write(addr=0x8123, data=0xAA)
        await backplane.mem_write(addr=0x9A45, data=0xBB)

        # ---------------------------------------------------------------------
        # 3. Read Data Back (Verify the Z80 Read Path works)
        # ---------------------------------------------------------------------
        print("\n[TEST] Verifying RAM Contents via Z80 Read cycles...")

        # Read from Card 0 using the returned value!
        card0_read_val = await backplane.mem_read(addr=0x8123)

        # Read from Card 1 using the returned value!
        card1_read_val = await backplane.mem_read(addr=0x9A45)

        assert card0_read_val == 0xAA, f"Card 0 failed. Expected 0xAA, got {hex(card0_read_val)}"
        assert card1_read_val == 0xBB, f"Card 1 failed. Expected 0xBB, got {hex(card1_read_val)}"

        print("[TEST] SUCCESS! The Z80 can write to and read from the physical 512KB chips.")

    sim = Simulator(dut)
    sim.add_clock(20e-9)

    # Start the fast sparse-memory processes in the background!
    dut.card0.register_sim(sim)
    dut.card1.register_sim(sim)

    sim.add_testbench(test_process)
    with sim.write_vcd("waves/z80_mem_test.vcd"):
        sim.run()


if __name__ == "__main__":
    test_memory_read_write()