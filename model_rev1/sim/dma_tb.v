`timescale 1ns/1ps

module dma_tb;

    // --- Clock Generation ---
    wire mclk, zclk;
    zx50_clock clk_gen (.run_in(1'b1), .step_n_in(1'b1), .mclk(mclk), .zclk(zclk));

    // --- System Nets ---
    wire [15:0] z80_a;
    wire [7:0]  z80_d;
    wire z80_mreq_n, z80_iorq_n, z80_rd_n, z80_wr_n, z80_m1_n;
    wire wait_n, int_n, reset_n;
    
    // Shadow Bus Nets
    wire [15:0] sh_addr;
    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n;
    wire sh_c_dir, sh_data_oe_n;

    // -- Backplane --
    zx50_backplane backplane (
        .z80_reset_n(reset_n),
        .z80_addr(z80_a), .z80_data(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .z80_wait_n(wait_n), .z80_int_n(int_n),
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // --- The Z80 CPU (BFM) ---
    z80_cpu_util z80 (
        .clk(zclk), .reset_n(reset_n),
        .addr(z80_a), .data(z80_d),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n),
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(wait_n)
    );

    // --- The Device Under Test ---
    zx50_mem_card #(.CARD_ID(2'h0)) card0 ( 
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_a), .z80_d(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .wait_n(wait_n), .int_n(int_n),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // --- Test Sequence ---
    initial begin
        $dumpfile("waves/dma.vcd");
        $dumpvars(0, dma_tb);

        $display("--- Starting ZX50 DMA Cycle Stealing Test ---");

        z80.boot_sequence();

        // 1. Map Logical Page 8 to Physical Page 0x10
        $display("\n[%0t] Mapping Logical Page 8 to Physical Page 0x10...", $time);
        z80.mmu_map_page(4'h1, 4'h8, 8'h10);
        clk_gen.wait_zclk(5);

        // 2. Pre-fill some Z80 data at 0x8100
        z80.mem_write(16'h8100, 8'hAA);
        z80.mem_write(16'h8101, 8'hBB);

        // 3. Configure DMA (Read from Card 0 to Shadow Bus)
        $display("\n[%0t] Configuring DMA (Physical Addr: 0x10100)...", $time);
        
        // OPCODE 0 (Setup): A15=0, A14(is_master)=1, A13(dir)=0, A12:8(PA19:15)=00010 -> 0x42
        // Data: D7:5(PA14:12)=000, D4:1(PA11:8)=0001, D0=0 -> 0x02
        z80.io_write(16'h4240, 8'h02); 
        
        // OPCODE 1 (Arm): A15=1, A14:8(byte_count)=2 -> 0x82
        // Data: D7:0(PA7:0) = 0x00
        $display("[%0t] Arming DMA for 2 bytes...", $time);
        z80.io_write(16'h8240, 8'h00);

        // 4. Wait for DMA to complete (Interrupt will drop)
        $display("[%0t] Waiting for DMA interrupt...", $time);
        while (int_n !== 1'b0) begin
            clk_gen.wait_mclk(1);
        end
        $display("[%0t] SUCCESS: DMA Interrupt Fired!", $time);

        $display("\n--- Test Complete ---");
        $finish;
    end
    
    initial begin
        #500000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
endmodule
