`timescale 1ns/1ps

module mmu_tb;

    // --- Clock Generation ---
    wire mclk, zclk;
    zx50_clock clk_gen (.run_in(1'b1), .step_n_in(1'b1), .mclk(mclk), .zclk(zclk));

    // --- System Nets ---
    wire [15:0] z80_a;
    wire [7:0]  z80_d;
    wire z80_mreq_n, z80_iorq_n, z80_rd_n, z80_wr_n, z80_m1_n;
    wire wait_n, int_n, reset_n;

    // -- Backplane --
    zx50_backplane backplane (
        .z80_reset_n(reset_n),
        .z80_addr(z80_a), .z80_data(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .z80_wait_n(wait_n), .z80_int_n(int_n)
    );

    // --- The Z80 CPU (BFM) ---
    z80_cpu_util z80 (
        .clk(zclk), .reset_n(reset_n),
        .addr(z80_a), .data(z80_d),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n),
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(wait_n)
    );

    // --- The Devices Under Test ---
    zx50_mem_card #(.CARD_ID(4'h0), .BOOT_EN(1'b0)) card0 (
        .mclk(mclk), .zclk(zclk),
        .reset_n(reset_n),
        .z80_a(z80_a), .z80_d(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .wait_n(wait_n), .int_n(int_n)
    );

    zx50_mem_card #(.CARD_ID(4'h1), .BOOT_EN(1'b1)) card1 (
        .mclk(mclk), .zclk(zclk), 
        .reset_n(reset_n),
        .z80_a(z80_a), .z80_d(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .wait_n(wait_n), .int_n(int_n)
    );

    // --- Test Sequence ---
    integer i;
    initial begin
        $dumpfile("waves/mmu.vcd");
        $dumpvars(0, mmu_tb);

        $display("--- Starting ZX50 MMU & ATL Test ---");

        z80.boot_sequence();

        // 1. Map Logical Pages 0-7 to Card 0, Physical Pages 0x10-0x17
        $display("\n[%0t] Mapping Pages 0-7 to Card 0...", $time);
        for (i = 0; i < 8; i = i + 1) begin
            z80.mmu_map_page(4'h0, i[3:0], i[7:0] + 8'h10);
        end

        // 2. Map Logical Pages 8-15 to Card 1, Physical Pages 0x28-0x2F
        $display("[%0t] Mapping Pages 8-15 to Card 1...", $time);
        for (i = 8; i < 16; i = i + 1) begin
            z80.mmu_map_page(4'h1, i[3:0], i[7:0] + 8'h20);
        end

        clk_gen.wait_zclk(5);

        // 3. Verify Ownership Masks
        $display("\n--- Verifying CPLD Ownership Masks ---");
        if (card0.cpld.page_ownership === 16'h00FF) $display("SUCCESS: Card 0 claims 0x00FF");
        else begin 
            $display("FAIL: Card 0 claims %h", card0.cpld.page_ownership); 
            $finish(1); 
        end

        if (card1.cpld.page_ownership === 16'hFF00) $display("SUCCESS: Card 1 claims 0xFF00");
        else begin 
            $display("FAIL: Card 1 claims %h", card1.cpld.page_ownership); 
            $finish(1); 
        end

        // 4. Verify Physical ATL SRAM arrays
        $display("\n--- Verifying Physical ATL SRAM Contents ---");
        if (card0.atl_sram.memory_array[0] === 8'h10) $display("SUCCESS: Card 0 ATL[0] = 0x10");
        else begin 
            $display("FAIL: Card 0 ATL[0] = %h", card0.atl_sram.memory_array[0]); 
            $finish(1); 
        end

        if (card1.atl_sram.memory_array[15] === 8'h2F) $display("SUCCESS: Card 1 ATL[15] = 0x2F");
        else begin 
            $display("FAIL: Card 1 ATL[15] = %h", card1.atl_sram.memory_array[15]); 
            $finish(1); 
        end

        // 5. Remap a page from card1 to card0
        z80.mmu_map_page(4'h0, 4'hA, 8'hCD);
        clk_gen.wait_zclk(1);

         $display("\n--- Verifying Ownership Masks After Move ---");
        if (card0.cpld.page_ownership === 16'h04FF) $display("SUCCESS: Card 0 claims 0x04FF");
        else begin 
            $display("FAIL: Card 0 claims %h", card0.cpld.page_ownership); 
            $finish(1); 
        end

        if (card1.cpld.page_ownership === 16'hFB00) $display("SUCCESS: Card 1 claims 0xFB00");
        else begin 
            $display("FAIL: Card 1 claims %h", card1.cpld.page_ownership); 
            $finish(1); 
        end

        $display("\n--- Verifying Physical ATL SRAM Contents After Move ---");
        if (card0.atl_sram.memory_array[10] === 8'hCD) $display("SUCCESS: Card 0 ATL[10] = 0xCD");
        else begin 
            $display("FAIL: Card 0 ATL[10] = %h", card0.atl_sram.memory_array[10]); 
            $finish(1); 
        end

        // Card 1 does not change the ATL, the value does not really matter if it does not own page

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