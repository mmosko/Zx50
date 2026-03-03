`timescale 1ns/1ps

module zx50_bus_arbiter_tb;

    reg mclk;
    reg reset_n;

    reg [3:0] test_vector;
    reg [2:0] settle_counter;

    wire shadow_en_n  = test_vector[0];
    wire z80_card_hit = test_vector[1];
    wire z80_rd_n     = test_vector[2];
    wire shd_rw_n     = test_vector[3];

    wire z80_wait_n, shd_busy_n;
    wire z80_addr_oe_n, z80_data_oe_n, z80_data_dir;
    wire shd_addr_oe_n, shd_data_oe_n, shd_data_dir;

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

    initial mclk = 0;
    always #13.88 mclk = ~mclk; 

    initial begin
        $dumpfile("waves/arbiter_exhaustive.vcd");
        $dumpvars(0, zx50_bus_arbiter_tb); // Fixed to match module name
        
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

    always @(posedge mclk) begin
        if (reset_n) begin
            if (z80_addr_oe_n == 0 && shd_addr_oe_n == 0) begin
                $display("FATAL [%0t]: Transceiver Short Circuit Detected!", $time);
                $fatal(1); 
            end
            if (z80_card_hit && (z80_addr_oe_n != 0) && (z80_wait_n != 0)) begin
                $display("FATAL [%0t]: Z80 accessed unbuffered memory without a WAIT state!", $time);
                $fatal(1);
            end
            if (!shadow_en_n && (shd_addr_oe_n != 0) && (shd_busy_n != 0)) begin
                $display("FATAL [%0t]: Shadow bus accessed unbuffered memory without S_BUSY!", $time);
                $fatal(1);
            end
            if (z80_addr_oe_n != z80_data_oe_n) begin
                $display("FATAL [%0t]: Z80 Address and Data transceivers fell out of sync!", $time);
                $fatal(1);
            end
        end
    end

    // --- System Watchdog Timer ---
    // If the simulation runs for more than 10,000ns, assume a state machine 
    // deadlock and violently kill the simulation with a non-zero exit code.
    initial begin
        #10000; 
        $display("FATAL [%0t]: Watchdog Timer Expired! State machine deadlock detected.", $time);
        $fatal(1);
    end
endmodule