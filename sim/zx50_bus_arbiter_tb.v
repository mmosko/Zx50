`timescale 1ns/1ps

module arbiter_exhaustive_tb;

    reg mclk;
    reg reset_n;

    reg [3:0] test_vector;
    reg [2:0] settle_counter;

    wire shadow_en_n  = test_vector[0];
    wire z80_card_hit = test_vector[1];
    wire z80_rd_n     = test_vector[2];
    wire shd_rw_n     = test_vector[3];

    wire z80_wait_n, shd_busy_n;
    wire z80_data_oe_n, shd_data_oe_n, d_dir;

    // --- 1. Updated DUT Instantiation ---
    zx50_bus_arbiter dut (
        .mclk(mclk),
        .reset_n(reset_n),
        .shadow_en_n(shadow_en_n),
        .z80_card_hit(z80_card_hit),
        .z80_wait_n(z80_wait_n),
        .shd_busy_n(shd_busy_n),
        .z80_rd_n(z80_rd_n),
        .shd_rw_n(shd_rw_n),
        
        .z80_data_oe_n(z80_data_oe_n),
        .shd_data_oe_n(shd_data_oe_n),
        .d_dir(d_dir) // Shared direction pin
    );

    initial mclk = 0;
    always #13.88 mclk = ~mclk; // 36 MHz test clock

    initial begin
        $dumpfile("waves/arbiter_exhaustive.vcd");
        $dumpvars(0, arbiter_exhaustive_tb);
        
        reset_n = 0;
        test_vector = 4'b0000;
        settle_counter = 3'b000;
        
        #100 reset_n = 1;
    end

    always @(posedge mclk) begin
        if (reset_n) begin
            settle_counter <= settle_counter + 1'b1;
            
            if (settle_counter == 3'b111) begin 
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

    // --- 2. Updated INVARIANT ASSERTIONS ---
    always @(posedge mclk) begin
        if (reset_n) begin
            
            // INVARIANT 1: Mutual Exclusion on the Shared Data Bus
            if (z80_data_oe_n == 0 && shd_data_oe_n == 0) begin
                $display("FATAL [%0t]: Shared Data Bus Short Circuit Detected!", $time);
                $fatal(1); 
            end

            // INVARIANT 2: Z80 Protection (Wait state must cover the transceiver delay)
            if (z80_card_hit && (z80_data_oe_n != 0) && (z80_wait_n != 0)) begin
                $display("FATAL [%0t]: Z80 hit the card but transceivers are closed without a WAIT state!", $time);
                $fatal(1);
            end

            // INVARIANT 3: Shadow Bus Protection
            if (!shadow_en_n && (shd_data_oe_n != 0) && (shd_busy_n != 0)) begin
                $display("FATAL [%0t]: Shadow bus hit the card but transceivers are closed without S_BUSY!", $time);
                $fatal(1);
            end
            
            // Note: Invariant 4 was removed because z80_addr_oe_n is hardwired on the PCB.
        end
    end

    initial begin
        #10000; 
        $display("FATAL [%0t]: Watchdog Timer Expired! State machine deadlock detected.", $time);
        $fatal(1);
    end

endmodule