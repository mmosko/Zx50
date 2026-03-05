`timescale 1ns/1ps

module zx50_mem_card_tb;
    // --- 1. System Signals ---
    reg mclk, reset_n, boot_en_n;
    reg [3:0] card_id;
    
    // --- 2. Z80 Backplane (Mock) ---
    reg [15:0] z80_addr;
    wire [7:0] z80_data;
    reg [7:0]  z80_data_out;
    reg z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n;
    reg z80_m1_n, z80_iei;
    
    // Drive the bidirectional Z80 data bus
    assign z80_data = (!z80_wr_n) ? z80_data_out : 8'hzz;

    // --- 3. Shadow Bus (Mock - Inactive) ---
    wire [15:0] shd_addr;
    wire [7:0]  shd_data;
    wire shd_en_n, shd_rw_n, shd_inc_n, shd_stb_n, shd_done_n, shd_busy_n;

    // --- 4. Instantiate the Whole Card ---
    zx50_mem_card dut (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(card_id),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(z80_iei),
        .z80_wait_n(), .z80_ieo(), .z80_int_n(),
        .shd_addr(shd_addr), .shd_data(shd_data),
        .shd_en_n(shd_en_n), .shd_rw_n(shd_rw_n), .shd_inc_n(shd_inc_n), 
        .shd_stb_n(shd_stb_n), .shd_done_n(shd_done_n), .shd_busy_n(shd_busy_n)
    );

    // Clock Gen
    initial mclk = 0;
    always #13.88 mclk = ~mclk; // 36MHz

    initial begin
        $dumpfile("waves/zx50_mem_card_tbvcd");
        $dumpvars(0, zx50_mem_card_tb);
        
        // Initial setup
        reset_n = 1; boot_en_n = 1; card_id = 4'h0;
        z80_mreq_n = 1; z80_iorq_n = 1; z80_wr_n = 1; z80_rd_n = 1;
        z80_addr = 0; z80_data_out = 0;

        // Reset Sequence
        #100 reset_n = 0;
        #200 reset_n = 1;
        #500; // Wait for MMU Hardware Wipe

        // STEP 1: Program MMU (Map Z80 Bank 0x0 to Physical Page 0x85)
        // I/O Port 0x30 = Bank 0x0
        $display("[%0t] Step 1: Programming MMU Page 0...", $time);
        z80_addr = 16'h0030; z80_data_out = 8'h85; 
        z80_iorq_n = 0; z80_wr_n = 0;
        #100 z80_wr_n = 1; z80_iorq_n = 1;
        
        #100;

        // STEP 2: Write to the new page (Bank 0x0, Addr 0x0123)
        // This targets physical address 0x85 (Page) + 0x123 (Offset)
        $display("[%0t] Step 2: Writing to SRAM...", $time);
        z80_addr = 16'h0123; z80_data_out = 8'hA5;
        z80_mreq_n = 0; z80_wr_n = 0;
        #100 z80_wr_n = 1; z80_mreq_n = 1;

        #100;

        // STEP 3: Read back from the same address
        $display("[%0t] Step 3: Reading back from SRAM...", $time);
        z80_addr = 16'h0123;
        z80_mreq_n = 0; z80_rd_n = 0;
        #100;
        
        if (z80_data === 8'hA5) 
            $display("SUCCESS: Data Match! MMU and SRAM working perfectly.");
        else 
            $display("FAILURE: Expected A5, got %h", z80_data);

        #100 $finish;
    end
endmodule