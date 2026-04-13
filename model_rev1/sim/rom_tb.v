`timescale 1ns/1ps

// The ROM is initialized with a predictable non-repeating pattern.
// we should be able to read it linearly, even with A11 bug.
module rom_tb;

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
    reg [7:0] read_val;
    reg [7:0] expected;

    initial begin
        $dumpfile("waves/rom.vcd");
        $dumpvars(0, rom_tb);

        $display("--- Validating ROM ---");

        z80.boot_sequence();

        for (i = 0; i < 32768; i = i + 1) begin
            z80.mem_read(i, read_val);

            expected = (i ^ (i >> 8) ^ (i >> 16)) & 8'hFF;

            if (read_val != expected) begin
                $display("FAIL: Bad ROM value at %h, read %h expected %h", i, read_val, expected); 
                $finish(1); 
            end
        end

        $display("\n--- Test Complete ---");
        $finish;
    end

    // --- System Watchdog Timer ---
    initial begin
        #20000000000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end

endmodule