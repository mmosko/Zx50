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
 * 2. Verification: The Z80 reads Logical Page 8. The test asserts that Card A pulls 
 * its `active` pin High, translates the page using its LUT, and returns data 0x80 
 * from the underlying physical page 8.
 * 3. Handoff: The Z80 issues an I/O `OUT` command targeting Card B (Port 0x31) 
 * to map physical page 0xBB into Logical Page 8.
 * 4. Conflict Check: Card A passively snoops this write, realizes it lost Page 8, 
 * and clears its ownership mask. Card B claims it simultaneously. The Z80 reads 
 * Logical Page 8 again. The test asserts Card B is now `active`, Card A is silent, 
 * and the data returned is 0xBB.
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

    // --- Clock Generation (Digital Twin) ---
    zx50_clock clk_gen (
        .run_in(1'b1),    
        .step_n_in(1'b1), 
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
    // Internal Testbench Wires & Mocks
    // ==========================================
    reg failed;

    wire [3:0] atl_addr_a, atl_addr_b;
    wire [7:0] atl_data_a, atl_data_b;
    wire atl_we_n_a, atl_oe_n_a, atl_ce_n_a;
    wire atl_we_n_b, atl_oe_n_b, atl_ce_n_b;
    
    wire active_a, active_b;
    wire hit_a, hit_b;
    wire is_busy_a, is_busy_b;
    wire cpu_updating_a, cpu_updating_b;

    // --- BRIDGE LOGIC: Centralized Decode Simulation ---
    // Simulating the top-level core's routing optimization for both cards
    wire mmu_snoop_wr    = (!z80_iorq_n && !z80_wr_n && ((z80_addr[7:0] & 8'hF0) == 8'h30));
    wire mmu_direct_wr_a = mmu_snoop_wr && (z80_addr[7:0] == (8'h30 | id_sw_a));
    wire mmu_direct_wr_b = mmu_snoop_wr && (z80_addr[7:0] == (8'h30 | id_sw_b));

    // --- Card A (ID 0, Boot Card) ---
    zx50_mmu_sram card_a (
        .mclk(mclk), .reset_n(reset_n), 
        .boot_en_n(1'b0), 
        
        // --- FITTER OPTIMIZED PORTS ---
        .z80_addr_hi(z80_addr[15:8]),
        .mmu_snoop_wr(mmu_snoop_wr),
        .mmu_direct_wr(mmu_direct_wr_a),
        .z80_mreq_n(z80_mreq_n), 
        // ------------------------------
        
        .atl_addr(atl_addr_a), .atl_we_n(atl_we_n_a), .atl_oe_n(atl_oe_n_a), 
        .active(active_a), .z80_card_hit(hit_a), .is_busy(is_busy_a),
        .cpu_updating(cpu_updating_a), 
        .is_rom_enabled()
    );

    // --- Card B (ID 1, RAM Card) ---
    zx50_mmu_sram card_b (
        .mclk(mclk), .reset_n(reset_n), 
        .boot_en_n(1'b1), 
        
        // --- FITTER OPTIMIZED PORTS ---
        .z80_addr_hi(z80_addr[15:8]),
        .mmu_snoop_wr(mmu_snoop_wr),
        .mmu_direct_wr(mmu_direct_wr_b),
        .z80_mreq_n(z80_mreq_n), 
        // ------------------------------
        
        .atl_addr(atl_addr_b), .atl_we_n(atl_we_n_b), .atl_oe_n(atl_oe_n_b), 
        .active(active_b), .z80_card_hit(hit_b), .is_busy(is_busy_b),
        .cpu_updating(cpu_updating_b), 
        .is_rom_enabled()
    );

    // ==========================================
    // MOCK MEMORY LAYER (LUTs and Fake RAM arrays)
    // ==========================================
    assign atl_ce_n_a = !(hit_a || is_busy_a);
    assign atl_data_a = cpu_updating_a ? z80_data : 8'hzz;
    
    is61c256al lut_a (.addr({11'b0, atl_addr_a}), .data(atl_data_a), .ce_n(atl_ce_n_a), .oe_n(atl_oe_n_a), .we_n(atl_we_n_a));

    assign atl_ce_n_b = !(hit_b || is_busy_b);
    assign atl_data_b = cpu_updating_b ? z80_data : 8'hzz;
    
    is61c256al lut_b (.addr({11'b0, atl_addr_b}), .data(atl_data_b), .ce_n(atl_ce_n_b), .oe_n(atl_oe_n_b), .we_n(atl_we_n_b));

    // Behavioral memory arrays to represent the physical pages
    reg [7:0] mock_ram_a [0:255];
    reg [7:0] mock_ram_b [0:255];

    // Multiplex the active card's data onto the shared Z80 bus
    assign z80_data = (active_a && !z80_rd_n) ? mock_ram_a[atl_data_a] : 8'hzz;
    assign z80_data = (active_b && !z80_rd_n) ? mock_ram_b[atl_data_b] : 8'hzz;

    // ==========================================
    // Test Sequence
    // ==========================================
    reg [7:0] dummy_data;

    initial begin
        $dumpfile("waves/zx50_conflict.vcd");
        $dumpvars(0, zx50_conflict_tb);
        
        failed = 0;

        // Initialize target physical pages in the behavioral mock RAM arrays
        mock_ram_a[8'h08] = 8'h80; // Card A Physical Page 0x08 -> Data 0x80
        mock_ram_b[8'hBB] = 8'hBB; // Card B Physical Page 0xBB -> Data 0xBB

        // 1. Initial State Setup
        reset_n = 1;
        id_sw_a = 4'h0;
        id_sw_b = 4'h1;

        // 2. Synchronized Power-On Reset 
        #100 reset_n = 0;
        #100 reset_n = 1;

        $display("[%0t] --- Booting CPLDs and Initializing Page Tables ---", $time);
        
        // Use the Z80 BFM to initialize the default 1:1 map on Card A.
        // Because Card A is explicitly targeted, it will claim ownership of all 16 pages.
        z80.init_mmu(id_sw_a); 

        // 3. Test: Verification of initial state (Z80 reads Logical Page 8 / 0x8000)
        $display("[%0t] --- Verifying Boot State (Card A should own Page 8) ---", $time);
        
        // Use a fork/join to read memory while actively checking the 'active' flags mid-cycle
        fork
            z80.mem_read(16'h8000, dummy_data);
            begin
                wait(z80_mreq_n == 1'b0); // Wait for the Z80 to start the read
                #15; // Give CPLD time to decode the address bus
                
                if (active_a !== 1'b1 || active_b !== 1'b0) begin
                    $display("FAIL: Initial boot state conflict or missing ownership.");
                    $display("Card A Active: %b, Card B Active: %b", active_a, active_b);
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

        // 4. Test: Handover Conflict Resolution (The Snoop Logic)
        $display("[%0t] --- Moving Page 8 from Card A to Card B ---", $time);
        
        // Use the Z80 BFM to dynamically map Physical Page 0xBB into Logical Page 8 on Card B.
        // Card A MUST snoop this write and drop ownership of Page 8.
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