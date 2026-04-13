from zx50_mem_control import ZX50MemControl

if __name__ == "__main__":
    from amaranth.back import verilog

    top = ZX50MemControl()

    # Gather all the signals from our dataclasses to expose them as Verilog ports
    ports = [
        # --- Backplane Bus ---
        top.bp.mclk, top.bp.reset_n, top.bp.z80_a, top.bp.boot_en_n,
        top.bp.b_z80_mreq_n, top.bp.b_z80_iorq_n, top.bp.b_z80_rd_n, top.bp.b_z80_wr_n, top.bp.b_z80_m1_n,
        top.bp.b_z80_iei, top.bp.b_z80_ieo,
        top.bp.wait_n, top.bp.int_n, top.bp.z80_d_oe_n, top.bp.d_dir,

        # --- Shadow Bus ---
        top.sh.sh_d_oe_n, top.sh.sh_c_dir,
        top.sh.sh_en_n, top.sh.sh_stb_n, top.sh.sh_inc_n, top.sh.sh_rw_n, top.sh.sh_done_n, top.sh.sh_busy_n,

        # --- Memory Bus ---
        # --- Memory Bus ---
        top.loc.l_d, top.loc.atl_d, top.loc.atl_a, top.loc.atl_oe_n, top.loc.atl_ce_n, top.loc.atl_we_n,
        top.loc.l_a, top.loc.oe_n, top.loc.we_n, top.loc.ram_ce0_n, top.loc.ram_ce1_n, top.loc.rom_ce2_n,
        top.loc.led_rx,
        
        # --- Internal Data Paths ---
        top.dma_addr
    ]

    with open("zx50_mem_control_generated.v", "w") as f:
        f.write(verilog.convert(top, ports=ports))
        print("Successfully generated zx50_mem_control_generated.v")
