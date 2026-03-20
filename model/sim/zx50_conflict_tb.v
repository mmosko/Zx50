`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_conflict_tb
 * =====================================================================================
 * Description:
 * This testbench specifically verifies the "Snoop Logic" and mutual exclusion of the 
 * distributed MMU system. It ensures that two physical memory cards correctly hand 
 * over ownership of a shared Z80 logical memory page without causing a bus conflict[cite: 599, 600].
 *
 * Test Sequence:
 * 1. Boot: Both Card A and Card B boot. The Z80 BFM initializes their default 1:1 maps.
 * 2. Verification: The Z80 reads Logical Page 8. Card A asserts 'active' (by default, Card A owns everything).
 * 3. Handoff: The Z80 issues an I/O write specifically targeting Card B (Port 0x31) 
 * to map a physical page into Logical Page 8.
 * 4. Conflict Check: Card A must snoop this write, realize it is no longer the owner 
 * of Logical Page 8, and drop its ownership bit[cite: 603, 604]. Card B must claim it simultaneously.
 ***************************************************************************************/

module zx50_conflict_tb;
    wire mclk;
    wire zclk;
    reg reset_n;
    reg [3:0] id_sw_a, id_sw_b;

    // --- Z80 Backplane Buses (Driven by BFM) ---
    wire [15:0] z80_addr;
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n;

    wire active_a, active_b;
    reg failed;

    // --- Clock Generation (Digital Twin) ---
    zx50_clock clk_gen (
        .run_in(1'b1),    // Free run enabled
        .step_n_in(1'b1), // Not stepping
        .mclk(mclk),
        .zclk(zclk)
    );

    // ==========================================
    // The Z80 Bus Master (BFM)
    // ==========================================
    z80_cpu_util z80 (
        .clk(zclk), 
        .addr(z80_addr), 
        .data(z80_data),
        .mreq_n(z80_mreq_n), 
        .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), 
        .wr_n(z80_wr_n), 
        .m1_n(z80_m1_n),
        .wait_n(1'b1) // No wait states needed for isolated MMU testing
    );

    // ==========================================
    // Card A (ID 0, Boot Card)
    // ==========================================
    zx50_mmu_sram card_a (
        .mclk(mclk), 
        .reset_n(reset_n), 
        .card_id_sw(id_sw_a), 
        .z80_addr(z80_addr), 
        .l_addr_hi(z80_addr[15:12]), 
        .l_data(z80_data),        
        .z80_iorq_n(z80_iorq_n), 
        .z80_wr_n(z80_wr_n), 
        .z80_mreq_n(z80_mreq_n), 
        
        // Explicitly float unused outputs
        .atl_addr(), 
        .atl_we_n(), 
        .atl_oe_n(), 
        
        .active(active_a),
        .z80_card_hit(),
        .is_busy(),
        .cpu_updating(),
        .is_initializing(),
        .init_ptr()
    );

    // ==========================================
    // Card B (ID 1, Secondary Card)
    // ==========================================
    zx50_mmu_sram card_b (
        .mclk(mclk), 
        .reset_n(reset_n), 
        .card_id_sw(id_sw_b), 
        .z80_addr(z80_addr), 
        .l_addr_hi(z80_addr[15:12]), 
        .l_data(z80_data),        
        .z80_iorq_n(z80_iorq_n), 
        .z80_wr_n(z80_wr_n), 
        .z80_mreq_n(z80_mreq_n), 
        
        // Explicitly float unused outputs
        .atl_addr(), 
        .atl_we_n(), 
        .atl_oe_n(), 
        
        .active(active_b),
        .z80_card_hit(),
        .is_busy(),
        .cpu_updating(),
        .is_initializing(),
        .init_ptr()
    );

    reg [7:0] dummy_data;

    initial begin
        $dumpfile("waves/zx50_conflict.vcd");
        $dumpvars(0, zx50_conflict_tb);
        
        failed = 0;
        
        // 1. Initial State Setup
        reset_n = 1; 
        id_sw_a = 4'h0; 
        id_sw_b = 4'h1;

        // 2. Synchronized Power-On Reset 
        #100 reset_n = 0;
        #100 reset_n = 1;

        $display("[%0t] --- Booting CPLDs and Initializing Page Tables ---", $time);

        // Use the Z80 BFM to initialize the default 1:1 map on Card A
        // Because Card A is initialized, it will claim ownership of all pages.
        z80.init_mmu(id_sw_a); 

        // 3. Test: Verification of initial state (Z80 reads Page 8 / 0x8000)
        $display("[%0t] --- Verifying Boot State (Card A should own Page 8) ---", $time);
        
        // Use a fork/join to read memory while actively checking the 'active' flags mid-cycle
        fork
            z80.mem_read(16'h8000, dummy_data);
            begin
                wait(z80_mreq_n == 1'b0); // Wait for the Z80 to start the read
                #15; // Give CPLD time to decode
                if (active_a !== 1'b1 || active_b !== 1'b0) begin
                    $display("FAIL: Initial boot state conflict or missing ownership.");
                    $display("Card A Active: %b, Card B Active: %b", active_a, active_b);
                    failed = 1;
                end
            end
        join
        
        z80.wait_cycles(5);

        // 4. Test: Handover Conflict Resolution (The Snoop Logic)
        $display("[%0t] --- Moving Page 8 from Card A to Card B ---", $time);
        
        // Use the Z80 BFM to dynamically map Physical Page 0xBB into Logical Page 8 on Card B
        z80.mmu_map_page(id_sw_b, 4'h8, 8'hBB);
        
        z80.wait_cycles(5);
        
        // 5. Verification: Card A must have "Stepped Down" and Card B must claim it
        $display("[%0t] --- Verifying Handover (Card B should now own Page 8) ---", $time);
        
        fork
            z80.mem_read(16'h8000, dummy_data);
            begin
                wait(z80_mreq_n == 1'b0);
                #15;
                if (active_a === 1'b1) begin
                    $display("FAIL: BUS CONFLICT! Card A failed to release Page 8.");
                    failed = 1;
                end
                if (active_b !== 1'b1) begin
                    $display("FAIL: Card B failed to claim Page 8.");
                    failed = 1;
                end
            end
        join

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