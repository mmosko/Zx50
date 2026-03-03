`timescale 1ns/1ps

module arbiter_exhaustive_tb;

    // --- 1. System Clocks & Resets ---
    reg mclk;
    reg reset_n;

    // --- 2. Exhaustive Test Vectors ---
    reg [3:0] test_vector;
    reg [2:0] settle_counter;

    // Map the counter bits directly to the Arbiter inputs
    wire shadow_en_n  = test_vector[0];
    wire z80_card_hit = test_vector[1];
    wire z80_rd_n     = test_vector[2];
    wire shd_rw_n     = test_vector[3];

    // --- 3. Arbiter Outputs ---
    wire z80_wait_n, shd_busy_n;
    wire z80_addr_oe_n, z80_data_oe_n, z80_data_dir;
    wire shd_addr_oe_n, shd_data_oe_n, shd_data_dir;

    // --- 4. Instantiate the Device Under Test (DUT) ---
    zx50_bus_arbiter dut (
        .mclk(mclk),
        .reset_n(reset_n),
        .shadow_en_n(shadow_en_n),
        .z80_card_hit(z80_card_hit),
        .z80_wait_n(z80_wait_n),
        .shd_busy_n(shd_busy_n),
        .z80_rd_n(z80_rd_n),
        .shd_rw_n(shd_rw_n),
        
        .z80_addr_oe_n(z80_addr_oe_n),
        .z80_data_oe_n(z80_data_oe_n),
        .z80_data_dir(z80_data_dir),
        
        .shd_addr_oe_n(shd_addr_oe_n),
        .shd_data_oe_n(shd_data_oe_n),
        .shd_data_dir(shd_data_dir)
    );

    // --- 5. Clock Generation (36 MHz) ---
    initial mclk = 0;
    always #13.88 mclk = ~mclk; // 27.7ns period

    // --- 6. The Exhaustive Walker ---
    initial begin
        $dumpfile("waves/arbiter_exhaustive.vcd");
        $dumpvars(0, arbiter_exhaustive_tb);
        
        // Start with system in reset, test vector at 0
        reset_n = 0;
        test_vector = 4'b0000;
        settle_counter = 3'b000;
        
        #100 reset_n = 1;
    end

    // Walk through all 16 states, holding each for 8 clock cycles
    always @(posedge mclk) begin
        if (reset_n) begin
            settle_counter <= settle_counter + 1'b1;
            
            // Wait for the state machine to transition through any dead zones
            if (settle_counter == 3'b111) begin 
                
                // EXIT CONDITION: Have we tested the final combination (1111)?
                if (test_vector == 4'b1111) begin
                    $display("=====================================================");
                    $display(" SUCCESS: All 16 Input States Tested.");
                    $display(" ZERO Bus Contention Violations Found.");
                    $display("=====================================================");
                    $finish;
                end else begin
                    test_vector <= test_vector + 1'b1;
                end
            end
        end
    end

    // --- 7. INVARIANT ASSERTIONS (The "Proptest" Watchdogs) ---
    always @(posedge mclk) begin
        if (reset_n) begin
            // INVARIANT 1: Mutual Exclusion (No Magic Smoke)
            if (z80_addr_oe_n == 0 && shd_addr_oe_n == 0) begin
                $display("FATAL [%0t]: Transceiver Short Circuit Detected!", $time);
                $fatal(1); 
            end

            // INVARIANT 2: Z80 Protection (No Garbage Reads)
            if (z80_card_hit && (z80_addr_oe_n != 0) && (z80_wait_n != 0)) begin
                $display("FATAL [%0t]: Z80 accessed unbuffered memory without a WAIT state!", $time);
                $fatal(1);
            end

            // INVARIANT 3: Shadow Bus Protection (No Dropped Writes)
            if (!shadow_en_n && (shd_addr_oe_n != 0) && (shd_busy_n != 0)) begin
                $display("FATAL [%0t]: Shadow bus accessed unbuffered memory without S_BUSY!", $time);
                $fatal(1);
            end
            
            // INVARIANT 4: Break-Before-Make Output Enable sync
            if (z80_addr_oe_n != z80_data_oe_n) begin
                $display("FATAL [%0t]: Z80 Address and Data transceivers fell out of sync!", $time);
                $fatal(1);
            end
        end
    end

    // --- 8. System Watchdog Timer ---
    initial begin
        #10000; // Adjusted to allow the 16 states * 8 clocks to finish safely
        $display("FATAL [%0t]: Watchdog Timer Expired! State machine deadlock detected.", $time);
        $fatal(1);
    end

endmodule