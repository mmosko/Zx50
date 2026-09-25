`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: fpu_mem_tb
 * FILE: sim/fpu_mem_tb.v
 * DESCRIPTION:
 * Unit test pro zx50_fpu_mem (CPLD Rev C2).
 ***************************************************************************************/

module fpu_mem_tb;

    // --- Clock & System Signals ---
    reg mclk;
    reg reset_n;
    reg clk_spd;

    real clk_half_period = 12.5; // 12.5ns = 40MHz, 25.0ns = 20MHz
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
        // TEST 1: Reset & Idle Controls
        // -----------------------------------------------------------------
        $display("\n--- Test 1: Reset & Idle Controls ---");
        if (m_ce_n !== 1'b1 || f_ce_n !== 1'b1 || c_oe_n !== 1'b1 || c_we_n !== 1'b1 || mem_ready !== 1'b0) begin
            $display("FAIL [IDLE]: Strobes should be inactive HIGH and mem_ready LOW!");
            $fatal(1);
        end
        $display("PASS [IDLE]: Control strobes and mem_ready cleanly idle.");

        // -----------------------------------------------------------------
        // TEST 2: Client 0 (Host) Fast 12ns SRAM Write & Read
        // -----------------------------------------------------------------
        $display("\n--- Test 2: Client 0 Fast 12ns SRAM Write & Read ---");
        host_addr   = 8'h05;
        host_wdata  = 8'hBE;
        host_we_req = 1'b1;

        @(posedge mclk); #1;
        @(posedge mclk); #1;
        if (mem_ready !== 1'b1) begin
            $display("FAIL [SRAM WR]: Expected mem_ready = 1 on Phase 2 hold!");
            $fatal(1);
        end
        host_we_req = 1'b0;
        @(posedge mclk); #1;

        // Read back from SRAM address 0x0005
        host_oe_req = 1'b1;
        host_addr   = 8'h05;
        @(posedge mclk); #1; // Exspecta oram ascendentem mclk pro mem_ready
        if (mem_ready !== 1'b1 || mem_rdata !== 8'hBE) begin
            $display("FAIL [SRAM RD]: Expected 0xBE and mem_ready=1, got data=0x%02h, ready=%b", mem_rdata, mem_ready);
            $fatal(1);
        end
        $display("PASS [SRAM RD]: Single-cycle SRAM read back 0xBE with mem_ready = 1.");
        host_oe_req = 1'b0;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 3: 40 MHz Mode Flash Read (clk_spd = 1) -> 3 Cycles
        // -----------------------------------------------------------------
        $display("\n--- Test 3: 40 MHz Mode Flash Read (clk_spd = 1) ---");
        clk_spd          = 1'b1;
        clk_half_period  = 12.5; // 40 MHz (25ns period)
        eng_sel_flash    = 1'b1;
        eng_oe_req       = 1'b1;
        eng_addr         = 15'h0123;

        // Cycle 1 (25ns): Not Ready
        @(posedge mclk); #1;
        if (mem_ready !== 1'b0) $fatal(1, "FAIL: Cycle 1 should be Not Ready");

        // Cycle 2 (50ns): Not Ready
        @(posedge mclk); #1;
        if (mem_ready !== 1'b0) $fatal(1, "FAIL: Cycle 2 should be Not Ready");

        // Cycle 3 (75ns > 55ns t_ACC): Ready!
        @(posedge mclk); #1;
        if (mem_ready !== 1'b1 || mem_rdata !== 8'h7E) begin
            $display("FAIL [FLASH 40MHz]: Expected 0x7E and mem_ready=1 on Cycle 3, got data=0x%02h, ready=%b", mem_rdata, mem_ready);
            $fatal(1);
        end
        $display("PASS [FLASH 40MHz]: Flash read ready on cycle 3 (75ns).");

        eng_oe_req    = 1'b0;
        eng_sel_flash = 1'b0;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 4: 20 MHz Mode Flash Read (clk_spd = 0) -> 2 Cycles
        // -----------------------------------------------------------------
        $display("\n--- Test 4: 20 MHz Mode Flash Read (clk_spd = 0) ---");
        clk_spd          = 1'b0; // Set 20 MHz mode
        clk_half_period  = 25.0; // 20 MHz (50ns period)
        eng_sel_flash    = 1'b1;
        eng_oe_req       = 1'b1;
        eng_addr         = 15'h0123;

        // Cycle 1 (50ns): Not Ready
        @(posedge mclk); #1;
        if (mem_ready !== 1'b0) $fatal(1, "FAIL: Cycle 1 should be Not Ready");

        // Cycle 2 (100ns > 55ns t_ACC): Ready!
        @(posedge mclk); #1;
        if (mem_ready !== 1'b1 || mem_rdata !== 8'h7E) begin
            $display("FAIL [FLASH 20MHz]: Expected 0x7E and mem_ready=1 on Cycle 2, got data=0x%02h, ready=%b", mem_rdata, mem_ready);
            $fatal(1);
        end
        $display("PASS [FLASH 20MHz]: Flash read ready on cycle 2 (100ns > 55ns t_ACC).");

        eng_oe_req    = 1'b0;
        eng_sel_flash = 1'b0;
        clk_spd       = 1'b1;   // Restore 40 MHz mode
        clk_half_period = 12.5;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 5: Dual-Client Arbitration Priority
        // -----------------------------------------------------------------
        $display("\n--- Test 5: Dual-Client Arbitration Priority ---");
        host_addr   = 8'h30;
        host_wdata  = 8'hAA;
        host_we_req = 1'b1;

        eng_addr    = 15'h4000;
        eng_wdata   = 8'h55;
        eng_we_req  = 1'b1;

        @(posedge mclk); #1;
        if (ca !== 15'h4000 || cd !== 8'h55) begin
            $display("FAIL [ARBITRATION]: Client 1 (Engine) should have won priority! Got ca=%h, cd=%h", ca, cd);
            $fatal(1);
        end
        $display("PASS [ARBITRATION]: Client 1 (Engine) correctly won priority over Client 0 (Host).");

        eng_we_req  = 1'b0;
        host_we_req = 1'b0;
        @(posedge mclk);

        $display("\n=================================================");
        $display("=== SUCCESS: All Private Memory Tests Passed! ===");
        $display("=================================================");

        $finish;
    end

    // --- System Watchdog Timer ---
    initial begin
        #500000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end

endmodule