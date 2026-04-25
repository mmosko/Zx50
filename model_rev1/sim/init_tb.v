`timescale 1ns/1ps

module init_tb;

    // --- Clock Generation ---
    wire mclk, zclk;
    zx50_clock clk_gen (
        .run_in(1'b1),      // Free run
        .step_n_in(1'b1), 
        .mclk(mclk), 
        .zclk(zclk)
    );

    // --- System Nets ---
    wire [15:0] z80_a;
    wire [7:0]  z80_d;
    wire z80_mreq_n, z80_iorq_n, z80_rd_n, z80_wr_n, z80_m1_n;
    wire wait_n, int_n, reset_n;

    // -- Backplane --
    zx50_backplane backplane (
        .z80_reset_n(reset_n),
        .z80_addr(z80_a),
        .z80_data(z80_d),
        .z80_mreq_n(z80_mreq_n),
        .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n),
        .z80_wr_n(z80_wr_n),
        .z80_m1_n(z80_m1_n),
        .z80_wait_n(wait_n),
        .z80_int_n(int_n)
    );

    // --- The Z80 CPU (BFM) ---
    z80_cpu_util z80 (
        .clk(zclk),
        .reset_n(reset_n),
        .addr(z80_a),
        .data(z80_d),
        .mreq_n(z80_mreq_n),
        .iorq_n(z80_iorq_n),
        .rd_n(z80_rd_n),
        .wr_n(z80_wr_n),
        .m1_n(z80_m1_n),
        .wait_n(wait_n)
    );


    // --- The Device Under Test ---
    zx50_mem_card #(
        .CARD_ID(4'hA)
    ) card0 (
        .mclk(mclk),
        .zclk(zclk),
        .reset_n(reset_n),
        .z80_a(z80_a),
        .z80_d(z80_d),
        .z80_mreq_n(mreq_n),
        .z80_iorq_n(iorq_n),
        .z80_rd_n(rd_n),
        .z80_wr_n(wr_n),
        .z80_m1_n(z80_m1_n),
        .wait_n(wait_n),
        .int_n(int_n)
    );

    zx50_mem_card #(
        .CARD_ID(4'h6)
    ) card1 (
        .mclk(mclk),
        .zclk(zclk),
        .reset_n(reset_n),
        .z80_a(z80_a),
        .z80_d(z80_d),
        .z80_mreq_n(mreq_n),
        .z80_iorq_n(iorq_n),
        .z80_rd_n(rd_n),
        .z80_wr_n(wr_n),
        .z80_m1_n(z80_m1_n),
        .wait_n(wait_n),
        .int_n(int_n)
    );

    // --- Test Sequence ---
    initial begin
        $dumpfile("waves/init.vcd");
        $dumpvars(0, init_tb);

        $display("--- Starting ZX50 Reset & Init Test ---");

        // 1. Power On & Reset
        z80.boot_sequence();

        // Verify CPLD latched state
        if (card0.cpld.card_addr === 4'hA) begin
            $display("SUCCESS: Card0 Card ID latched correctly.");
        end
        else begin
            $display("FAIL: Card0 Expected Card ID A, got %h", card0.cpld.card_addr);
            $finish(1);
        end
        
        
        if (card0.cpld.page_ownership === 16'h00FF) begin
            $display("SUCCESS: Card0 ROM Pages latched correctly.");
        end
        else begin
            $display("FAIL: Card0 Expected Pages 00FF, got %h", card0.cpld.page_ownership);
            $finish(1);
        end

        // ==== Verify Card 1
        if (card1.cpld.card_addr === 4'h6) begin
            $display("SUCCESS: Card1 ID latched correctly.");
        end
        else begin
            $display("FAIL: Card1 Expected Card ID 6, got %h", card1.cpld.card_addr);
            $finish(1);
        end

        if (card1.cpld.page_ownership === 16'h0000) begin
            $display("SUCCESS: Card1 ROM Pages latched correctly.");
        end
        else begin
            $display("FAIL: Card1 Expected Pages 0000, got %h", card1.cpld.page_ownership);
            $finish(1);
        end

        $finish;
    end

        // --- System Watchdog Timer ---
    initial begin
        #500000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
endmodule