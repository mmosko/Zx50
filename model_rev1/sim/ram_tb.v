`timescale 1ns/1ps

module ram_tb;

    // --- Clock Generation ---
    wire mclk, zclk;
    zx50_clock clk_gen (.run_in(1'b1), .step_n_in(1'b1), .mclk(mclk), .zclk(zclk));

    // --- System Nets ---
    wire [15:0] z80_a;
    wire [7:0]  z80_d;
    wire z80_mreq_n, z80_iorq_n, z80_rd_n, z80_wr_n, z80_m1_n;
    wire wait_n, int_n, reset_n;

    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_busy_n, sh_data_oe_n;

    // -- Backplane --
    zx50_backplane backplane (
        .z80_reset_n(reset_n),
        .z80_addr(z80_a), .z80_data(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .z80_wait_n(wait_n), .z80_int_n(int_n),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n),
        .sh_busy_n(sh_busy_n)
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
    zx50_mem_card #(.CARD_ID(4'h0)) card0 (
        .mclk(mclk), .zclk(zclk),
        .reset_n(reset_n),
        .z80_a(z80_a), .z80_d(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .wait_n(wait_n), .int_n(int_n),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // --- Test Sequence ---
    reg [7:0] read_val;
    
    initial begin
        $dumpfile("waves/ram.vcd");
        $dumpvars(0, ram_tb);

        $display("--- Starting ZX50 RAM Read/Write Test ---");

        z80.boot_sequence();

        // 1. Map Logical Page 8 (0x8000-0x8FFF) to Physical Page 0x12
        $display("\n[%0t] Mapping Logical Page 8 to Physical Page 0x12...", $time);
        z80.mmu_map_page(4'h0, 4'h8, 8'h12);
        clk_gen.wait_zclk(5);

        // 2. Write to RAM0
        // Address 0x8123: Page 8, A11=0 -> Should physically hit RAM0 at 0x12123
        $display("\n[%0t] Writing 0xAA to 0x8123 (Expecting RAM0 hit)...", $time);
        z80.mem_write(16'h8123, 8'hAA);
        
        // 3. Write to RAM1
        // Address 0x8A45: Page 8, A11=1 -> Should physically hit RAM1 at 0x12A45
        $display("[%0t] Writing 0xBB to 0x8A45 (Expecting RAM1 hit)...", $time);
        z80.mem_write(16'h8A45, 8'hBB);
        
        clk_gen.wait_zclk(5);

        // 4. Read back and verify RAM0
        $display("\n[%0t] Reading back from 0x8123...", $time);
        z80.mem_read(16'h8123, read_val);
        if (read_val === 8'hAA) $display("SUCCESS: RAM0 Read 0xAA");
        else begin $display("FAIL: RAM0 Expected 0xAA, got %h", read_val); $finish(1); end

        // 5. Read back and verify RAM1
        $display("[%0t] Reading back from 0x8A45...", $time);
        z80.mem_read(16'h8A45, read_val);
        if (read_val === 8'hBB) $display("SUCCESS: RAM1 Read 0xBB");
        else begin $display("FAIL: RAM1 Expected 0xBB, got %h", read_val); $finish(1); end

        $display("\n--- Test Complete ---");
        $finish;
    end

    // --- System Watchdog Timer ---
    initial begin
        #500000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
endmodule