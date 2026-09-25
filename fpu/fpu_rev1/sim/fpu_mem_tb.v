`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: fpu_mem_tb
 * FILE: sim/fpu_mem_tb.v
 * DESCRIPTION:
 * Unit test for zx50_fpu_mem private memory controller & arbiter (CPLD Rev C2).
 * Verifies dynamic wait state scaling via clk_spd (20 MHz vs 40 MHz MCLK).
 ***************************************************************************************/

module fpu_mem_tb;

    // --- Clock & System Signals ---
    reg mclk;
    reg reset_n;
    reg clk_spd;

    // Dynamic Clock Generator (Default 40 MHz / 25ns period)
    real clk_half_period = 12.5;
    always #(clk_half_period) mclk = ~mclk;

    // --- Client 0: Host Port Interface Signals ---
    reg        host_we_req;
    reg        host_oe_req;
    reg  [7:0] host_addr;
    reg  [7:0] host_wdata;

    // --- Client 1: Coprocessor Engine Interface Signals ---
    reg        eng_we_req;
    reg        eng_oe_req;
    reg        eng_sel_flash;
    reg [14:0] eng_addr;
    reg  [7:0] eng_wdata;

    // --- Controller Outputs & Physical Bus Nets ---
    wire [7:0]  mem_rdata;
    wire        mem_ready;
    wire [14:0] ca;
    wire [7:0]  cd;
    wire        m_ce_n;
    wire        f_ce_n;
    wire        c_oe_n;
    wire        c_we_n;

    // --- Device Under Test ---
    zx50_fpu_mem dut (
        .mclk(mclk),
        .reset_n(reset_n),
        .clk_spd(clk_spd),
        .host_we_req(host_we_req),
        .host_oe_req(host_oe_req),
        .host_addr(host_addr),
        .host_wdata(host_wdata),
        .eng_we_req(eng_we_req),
        .eng_oe_req(eng_oe_req),
        .eng_sel_flash(eng_sel_flash),
        .eng_addr(eng_addr),
        .eng_wdata(eng_wdata),
        .mem_rdata(mem_rdata),
        .mem_ready(mem_ready),
        .ca(ca),
        .cd(cd),
        .m_ce_n(m_ce_n),
        .c_oe_n(c_oe_n),
        .c_we_n(c_we_n),
        .f_ce_n(f_ce_n)
    );

    // --- IS61C256AL Private 12ns SRAM Model (U12) ---
    is61c256al_12 sram_u12 (
        .addr(ca),
        .data(cd),
        .ce_n(m_ce_n),
        .oe_n(c_oe_n),
        .we_n(c_we_n)
    );

    // --- SST39SF040 Private Flash ROM Model (U13) ---
    sst39sf040 flash_u13 (
        .addr({4'b0000, ca}),
        .data(cd),
        .ce_n(f_ce_n),
        .oe_n(c_oe_n),
        .we_n(c_we_n)
    );

    // --- Test Sequence ---
    initial begin
        $dumpfile("waves/fpu_mem.vcd");
        $dumpvars(0, fpu_mem_tb);

        $display("=================================================");
        $display("=== Starting ZX50 Private Memory Controller Test ==");
        $display("=================================================");

        // Initial State
        mclk             = 1'b0;
        reset_n          = 1'b0;
        clk_spd          = 1'b1; // Start in 40 MHz Fast Mode
        clk_half_period  = 12.5; // 25ns period
        host_we_req      = 1'b0;
        host_oe_req      = 1'b0;
        host_addr        = 8'h00;
        host_wdata       = 8'h00;
        eng_we_req       = 1'b0;
        eng_oe_req       = 1'b0;
        eng_sel_flash    = 1'b0;
        eng_addr         = 15'h0000;
        eng_wdata        = 8'h00;

        #50;
        reset_n = 1'b1;
        @(posedge mclk);

        // Pre-load test byte into Flash ROM
        flash_u13.memory_array[19'h00123] = 8'h7E;

        // -----------------------------------------------------------------
        // TEST 1: 40 MHz Fast Mode (clk_spd = 1) -> Flash 3 Cycles
        // -----------------------------------------------------------------
        $display("\n--- Test 1: 40 MHz Mode Flash Read (clk_spd = 1) ---");
        clk_spd          = 1'b1;
        clk_half_period  = 12.5; // 40 MHz (25ns period)
        eng_sel_flash    = 1'b1;
        eng_oe_req       = 1'b1;
        eng_addr         = 15'h0123;

        // Cycle 1: Not Ready
        @(posedge mclk); #1;
        if (mem_ready !== 1'b0) $fatal(1, "FAIL: Cycle 1 should be Not Ready");

        // Cycle 2: Not Ready
        @(posedge mclk); #1;
        if (mem_ready !== 1'b0) $fatal(1, "FAIL: Cycle 2 should be Not Ready");

        // Cycle 3: Ready!
        @(posedge mclk); #1;
        if (mem_ready !== 1'b1 || mem_rdata !== 8'h7E) $fatal(1, "FAIL: Expected 0x7E on Cycle 3!");
        $display("PASS [40MHz]: Flash read ready on cycle 3 (75ns).");

        eng_oe_req    = 1'b0;
        eng_sel_flash = 1'b0;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 2: 20 MHz Mode (clk_spd = 0) -> Flash 2 Cycles
        // -----------------------------------------------------------------
        $display("\n--- Test 2: 20 MHz Mode Flash Read (clk_spd = 0) ---");
        clk_spd          = 1'b0; // Set 20 MHz CPLD mode
        clk_half_period  = 25.0; // Scale testbench clock to 20 MHz (50ns period)
        eng_sel_flash    = 1'b1;
        eng_oe_req       = 1'b1;
        eng_addr         = 15'h0123;

        // Cycle 1 (50ns): Not Ready
        @(posedge mclk); #1;
        if (mem_ready !== 1'b0) $fatal(1, "FAIL: Cycle 1 should be Not Ready");

        // Cycle 2 (100ns > 55ns t_ACC): Ready!
        @(posedge mclk); #1;
        if (mem_ready !== 1'b1 || mem_rdata !== 8'h7E) $fatal(1, "FAIL: Expected 0x7E on Cycle 2!");
        $display("PASS [20MHz]: Flash read ready on cycle 2 (100ns > 55ns t_ACC).");

        eng_oe_req    = 1'b0;
        eng_sel_flash = 1'b0;
        @(posedge mclk);

        $display("\n=================================================");
        $display("=== SUCCESS: Dynamic Memory Timing Tests Passed! ");
        $display("=================================================");

        $finish;
    end

endmodule