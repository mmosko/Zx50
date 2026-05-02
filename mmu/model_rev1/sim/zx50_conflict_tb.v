`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_conflict_tb
 * =====================================================================================
 * WHAT IS BEING TESTED:
 * This testbench specifically isolates and verifies the "Snoop Protocol" and mutual 
 * exclusion logic of the distributed MMU system. It ensures that two physical memory 
 * cards correctly hand over ownership of a shared Z80 logical memory page without 
 * causing a physical bus conflict.
 *
 * TEST SEQUENCE:
 * 1. Boot: Card A (Boot Card) and Card B (RAM Card) power up. The Z80 BFM initializes 
 * Card A's full 64K map (Logical 1:1 Physical).
 * 2. Verification: The Z80 writes to and reads from Logical Page 8. The test asserts 
 * that Card A's CPLD asserts `z80_card_hit`, and returns the correct data.
 * 3. Handoff: The Z80 issues an I/O `OUT` command targeting Card B (Port 0x31) 
 * to map a new physical page into Logical Page 8.
 * 4. Conflict Check: Card A passively snoops this write, realizes it lost Page 8, 
 * and clears its ownership mask. Card B claims it simultaneously. The Z80 writes
 * to and reads from Logical Page 8 again. The test asserts Card B's CPLD is now 
 * active, Card A is silent, and the new data is returned successfully.
 ***************************************************************************************/

module zx50_conflict_tb;

    // --- Clock Generation ---
    wire mclk, zclk;
    zx50_clock clk_gen (.run_in(1'b1), .step_n_in(1'b1), .mclk(mclk), .zclk(zclk));

    // --- System Nets ---
    wire [15:0] z80_a;
    wire [7:0]  z80_d;
    wire z80_mreq_n, z80_iorq_n, z80_rd_n, z80_wr_n, z80_m1_n;
    wire wait_n, int_n, reset_n;
    
    // Shadow Bus Nets (Required for arbiter, pulled high by backplane)
    wire [15:0] sh_addr;
    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n;

    // ==========================================
    // Shared Z80 Backplane
    // ==========================================
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

    // ==========================================
    // The Z80 Bus Master (BFM)
    // ==========================================
    z80_cpu_util z80 (
        .clk(zclk), .reset_n(reset_n),
        .addr(z80_a), .data(z80_d),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(wait_n) 
    );

    // ==========================================
    // Card A (ID 0, Boot Card)
    // ==========================================
    zx50_mem_card #(.CARD_ID(4'h0)) card_a (
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_a), .z80_d(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .wait_n(wait_n), .int_n(int_n),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // ==========================================
    // Card B (ID 1, RAM Card)
    // ==========================================
    zx50_mem_card #(.CARD_ID(4'h1)) card_b (
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_a), .z80_d(z80_d),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n),
        .wait_n(wait_n), .int_n(int_n),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // ==========================================
    // Test Sequence
    // ==========================================
    reg failed;
    reg [7:0] dummy_data;

    initial begin
        $dumpfile("waves/zx50_conflict.vcd");
        $dumpvars(0, zx50_conflict_tb);
        
        failed = 0;

        $display("[%0t] --- Booting System ---", $time);
        z80.boot_sequence(); 

        $display("[%0t] --- Initializing MMU (Card A claims 64K) ---", $time);
        z80.init_mmu(4'h0); // Instruct Card A to claim all 16 Logical Pages
        
        $display("[%0t] --- Writing Test Data 0x80 to Card A (Page 8) ---", $time);
        z80.mem_write(16'h8000, 8'h80);

        // 1. Verification of initial state
        $display("[%0t] --- Verifying Boot State (Card A should own Page 8) ---", $time);
        
        // Use a fork/join to read memory while actively checking the CPLD Hit flags mid-cycle
        fork
            z80.mem_read(16'h8000, dummy_data);
            begin
                wait(z80_mreq_n == 1'b0); // Wait for the Z80 to assert MREQ
                #15;                      // Give CPLD time to decode the address bus
                
                if (card_a.cpld.z80_card_hit !== 1'b1 || card_b.cpld.z80_card_hit !== 1'b0) begin
                    $display("FAIL: Initial boot state conflict or missing ownership.");
                    $display("Card A Hit: %b, Card B Hit: %b", card_a.cpld.z80_card_hit, card_b.cpld.z80_card_hit);
                    failed = 1;
                end
            end
        join
        
        if (dummy_data !== 8'h80) begin
            $display("FAIL: Data payload read from Card A mismatched! Expected 0x80, Got %h", dummy_data);
            failed = 1;
        end else begin
            $display("  > Success: Read 0x80 from Card A, Phys Page 0x08");
        end
        
        z80.wait_cycles(5);

        // 2. Handover Conflict Resolution (The Snoop Logic)
        $display("\n[%0t] --- Moving Page 8 from Card A to Card B ---", $time);
        // Map Physical Page 0xBB into Logical Page 8 on Card B (ID 1).
        // Card A MUST snoop this write and drop ownership of Page 8.
        z80.mmu_map_page(4'h1, 4'h8, 8'hBB);
        z80.wait_cycles(5);
        
        $display("[%0t] --- Writing Test Data 0xBB to Card B (Page 8) ---", $time);
        z80.mem_write(16'h8000, 8'hBB);

        // 3. Verification: Card A must have "Stepped Down" and Card B must claim it
        $display("[%0t] --- Verifying Handover (Card B should now own Page 8) ---", $time);
        
        fork
            z80.mem_read(16'h8000, dummy_data);
            begin
                wait(z80_mreq_n == 1'b0);
                #15;
                
                if (card_a.cpld.z80_card_hit === 1'b1) begin
                    $display("FAIL: BUS CONFLICT! Card A failed to release Page 8.");
                    failed = 1;
                end
                
                if (card_b.cpld.z80_card_hit !== 1'b1) begin
                    $display("FAIL: Card B failed to claim Page 8.");
                    failed = 1;
                end
            end
        join

        if (dummy_data !== 8'hBB) begin
            $display("FAIL: Data payload read from Card B mismatched! Expected 0xBB, Got %h", dummy_data);
            failed = 1;
        end else begin
            $display("  > Success: Read 0xBB from Card B, Phys Page 0xBB");
        end

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
        #100000;
        $display("FATAL [%0t]: Watchdog Timer Expired! State machine deadlock detected.", $time);
        $fatal(1);
    end
endmodule