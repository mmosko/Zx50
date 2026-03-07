`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_conflict_tb
 * =====================================================================================
 * Description:
 * This testbench specifically verifies the "Snoop Logic" and mutual exclusion of the 
 * distributed MMU system. It ensures that two physical memory cards correctly hand 
 * over ownership of a shared Z80 logical memory page without causing a bus conflict.
 *
 * Test Sequence:
 * 1. Boot: Card A boots with the Boot ROM override enabled, claiming the top 32KB 
 * (Pages 8-15). Card B boots empty.
 * 2. Verification: The Z80 reads Page 8 (0x8000). Card A asserts 'active'.
 * 3. Handoff: The Z80 issues an I/O write specifically targeting Card B (Port 0x31) 
 * to map Physical Page 0xBB into Logical Page 8.
 * 4. Conflict Check: Card A must snoop this write, realize it is no longer the owner 
 * of Logical Page 8, and drop its ownership bit. Card B must claim it simultaneously.
 ***************************************************************************************/

module zx50_conflict_tb;
    reg mclk;
    reg [15:0] z80_addr;
    reg [7:0] l_data;          // Unified local data bus
    reg z80_iorq_n, z80_wr_n, z80_mreq_n, reset_n;
    reg boot_a_n, boot_b_n;
    reg [3:0] id_sw_a, id_sw_b;

    wire active_a, active_b;

    // --- Clock Generation (36MHz) ---
    initial mclk = 0;
    always #13.88 mclk = ~mclk; // ~36MHz Target Clock

    // ==========================================
    // Card A (ID 0, Boot Card)
    // ==========================================
    zx50_mmu_sram card_a (
        .mclk(mclk), 
        .reset_n(reset_n), 
        .boot_en_n(boot_a_n), 
        .card_id_sw(id_sw_a), 
        
        .z80_addr(z80_addr), 
        .l_addr_hi(z80_addr[15:12]), 
        .l_data(l_data),        
        
        .z80_iorq_n(z80_iorq_n), 
        .z80_wr_n(z80_wr_n), 
        .z80_mreq_n(z80_mreq_n), 
        
        // Explicitly float unused outputs to prevent compiler warnings
        .atl_addr(), 
        .atl_data(), 
        .atl_we_n(), 
        .atl_oe_n(), 
        .p_addr_hi(), 
        
        .active(active_a),
        .z80_card_hit(),
        .is_busy()
    );

    // ==========================================
    // Card B (ID 1, Secondary Card)
    // ==========================================
    zx50_mmu_sram card_b (
        .mclk(mclk), 
        .reset_n(reset_n), 
        .boot_en_n(boot_b_n), 
        .card_id_sw(id_sw_b), 
        
        .z80_addr(z80_addr), 
        .l_addr_hi(z80_addr[15:12]), 
        .l_data(l_data),        
        
        .z80_iorq_n(z80_iorq_n), 
        .z80_wr_n(z80_wr_n), 
        .z80_mreq_n(z80_mreq_n), 
        
        // Explicitly float unused outputs
        .atl_addr(), 
        .atl_data(), 
        .atl_we_n(), 
        .atl_oe_n(), 
        .p_addr_hi(), 
        
        .active(active_b),
        .z80_card_hit(),
        .is_busy()
    );

    reg failed;

    initial begin
        $dumpfile("waves/zx50_conflict.vcd");
        $dumpvars(0, zx50_conflict_tb);
        
        failed = 0;
        
        // 1. Initial State Setup
        reset_n = 1; z80_iorq_n = 1; z80_wr_n = 1; z80_mreq_n = 1;
        id_sw_a = 4'h0; id_sw_b = 4'h1;
        boot_a_n = 0; // Card A claims top 32K on boot
        boot_b_n = 1; // Card B claims nothing
        z80_addr = 16'h0000;
        l_data = 8'h00;
        
        // 2. Synchronized Power-On Reset 
        // (Give the 16-clock hardware wipe time to finish mapping the LUT)
        #100 reset_n = 0;
        #100 reset_n = 1;
        repeat(20) @(posedge mclk); 

        // 3. Test: Verification of initial state (Z80 reads Page 8 / 0x8000)
        $display("[%0t] --- Verifying Boot State (Page 8) ---", $time);
        @(posedge mclk);
        z80_addr = 16'h8000; 
        z80_mreq_n = 0; 
        
        repeat(3) @(posedge mclk); // Let active signals settle
        
        if (active_a !== 1'b1 || active_b !== 1'b0) begin
            $display("FAIL: Initial boot state conflict or missing ownership.");
            $display("Card A: %b, Card B: %b", active_a, active_b);
            failed = 1;
        end
        z80_mreq_n = 1; 
        repeat(3) @(posedge mclk);

        // 4. Test: Handover Conflict Resolution (The Snoop Logic)
        $display("[%0t] --- Moving Page 8 from Card A to Card B ---", $time);
        // Z80 OUT instruction: A15-A8 is the Page (0x08), A7-A0 is the Port (0x31 -> Card B)
        @(posedge mclk);
        z80_addr = 16'h0831; 
        l_data = 8'hBB; 
        z80_iorq_n = 0; 
        
        // Simulate safe write pulse timing
        #10 z80_wr_n = 0;
        
        repeat(5) @(posedge mclk); // Hold the I/O write
        
        z80_wr_n = 1;
        #10 z80_iorq_n = 1;
        
        repeat(5) @(posedge mclk);
        
        // 5. Verification: Card A must have "Stepped Down"
        $display("[%0t] --- Verifying Handover (Page 8) ---", $time);
        @(posedge mclk);
        z80_addr = 16'h8000; 
        z80_mreq_n = 0; 
        
        repeat(3) @(posedge mclk); // Let active signals settle
        
        if (active_a === 1'b1) begin
            $display("FAIL: BUS CONFLICT! Card A failed to release Page 8.");
            failed = 1;
        end
        if (active_b !== 1'b1) begin
            $display("FAIL: Card B failed to claim Page 8.");
            failed = 1;
        end

        z80_mreq_n = 1;

        if (!failed) begin
            $display("=====================================================");
            $display(" SUCCESS: Conflict Resolution (Snooping) Passed.");
            $display("=====================================================");
        end else begin
            $display("!!!!!! CONFLICT RESOLUTION FAILED !!!!!!");
            $fatal(1);
        end
        $finish;
    end

    // --- System Watchdog Timer ---
    initial begin
        #10000; 
        $display("FATAL [%0t]: Watchdog Timer Expired! State machine deadlock detected.", $time);
        $fatal(1);
    end
endmodule