`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: fpu_mem_tb
 * FILE: sim/fpu_mem_tb.v
 * DESCRIPTION:
 * Unit test for zx50_fpu_mem private memory controller & arbiter.
 *
 * TEST COVERAGE:
 * - Test 1: Reset & Idle Controls (All chip selects and write strobes inactive HIGH).
 * - Test 2: Client 0 (Host) SRAM 2-Phase Write & Readback (Validates t_DH hold window).
 * - Test 3: Client 1 (Engine) Flash ROM LUT Read Access (Validates 55ns SST39SF040 timing).
 * - Test 4: Dual-Client Arbitration Priority (Verifies Engine wins priority over Host).
 ***************************************************************************************/

module fpu_mem_tb;

    // --- Clock & System Signals ---
    reg mclk;
    reg reset_n;

    // 40 MHz Coprocessor Clock Generation (25ns Period)
    always #12.5 mclk = ~mclk;

    // --- Client 0: Host Port Interface Signals ---
    reg        host_we_req;
    reg        host_oe_req;
    reg  [7:0] host_addr;
    reg  [7:0] host_wdata;

    // --- Client 1: Coprocessor Engine Interface Signals ---
    reg        eng_we_req;
    reg        eng_oe_req;
    reg        eng_sel_flash;
    reg [13:0] eng_addr;
    reg  [7:0] eng_wdata;

    // --- Controller Outputs & Physical Bus Nets ---
    wire [7:0]  mem_rdata;
    wire [13:0] ca;
    wire [7:0]  cd;
    wire        m_ce_n, m_oe_n, m_we_n;
    wire        f_ce_n, f_oe_n, f_we_n;

    // --- Device Under Test ---
    zx50_fpu_mem dut (
        .mclk(mclk),
        .reset_n(reset_n),
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
        .ca(ca),
        .cd(cd),
        .m_ce_n(m_ce_n),
        .m_oe_n(m_oe_n),
        .m_we_n(m_we_n),
        .f_ce_n(f_ce_n),
        .f_oe_n(f_oe_n),
        .f_we_n(f_we_n)
    );

    // --- IS61C5128AS Private SRAM Model (U12) ---
    is61c5128as sram_u12 (
        .addr({5'b00000, ca}),
        .data(cd),
        .ce_n(m_ce_n),
        .oe_n(m_oe_n),
        .we_n(m_we_n)
    );

    // --- SST39SF040 Private Flash ROM Model (U13) ---
    sst39sf040 flash_u13 (
        .addr({5'b00000, ca}),
        .data(cd),
        .ce_n(f_ce_n),
        .oe_n(f_oe_n),
        .we_n(f_we_n)
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
        host_we_req      = 1'b0;
        host_oe_req      = 1'b0;
        host_addr        = 8'h00;
        host_wdata       = 8'h00;
        eng_we_req       = 1'b0;
        eng_oe_req       = 1'b0;
        eng_sel_flash    = 1'b0;
        eng_addr         = 14'h0000;
        eng_wdata        = 8'h00;

        // Release Reset
        #50;
        reset_n = 1'b1;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 1: Reset / Idle Control Signals Verification
        // -----------------------------------------------------------------
        $display("\n--- Test 1: Reset & Idle Controls ---");
        if (m_ce_n !== 1'b1 || m_we_n !== 1'b1 || m_oe_n !== 1'b1 || f_ce_n !== 1'b1 || f_oe_n !== 1'b1) begin
            $display("FAIL [IDLE]: Memory strobes should be inactive HIGH!");
            $fatal(1);
        end
        $display("PASS [IDLE]: SRAM and Flash control strobes cleanly inactive HIGH.");

        // -----------------------------------------------------------------
        // TEST 2: Client 0 (Host) 2-Phase SRAM Write & Read
        // -----------------------------------------------------------------
        $display("\n--- Test 2: Client 0 SRAM Write & Read ---");
        host_addr   = 8'h05;
        host_wdata  = 8'hBE;
        host_we_req = 1'b1;

        // Step through Phase 1 (Strobe Phase: m_we_n = 0) and Phase 2 (Hold Phase: m_we_n = 1)
        @(posedge mclk); #1;
        @(posedge mclk); #1;
        host_we_req = 1'b0;
        @(posedge mclk); #1;

        // Read back from SRAM address 0x05 (Wait 30ns to satisfy IS61C5128AS 25ns t_AA)
        host_oe_req = 1'b1;
        host_addr   = 8'h05;
        #30;
        if (mem_rdata !== 8'hBE) begin
            $display("FAIL [SRAM RD]: Expected 0xBE from SRAM address 0x05, got 0x%02h", mem_rdata);
            $fatal(1);
        end
        $display("PASS [SRAM RD]: Read back 0xBE correctly from SRAM address 0x05.");
        host_oe_req = 1'b0;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 3: Client 1 (Engine) Flash ROM Read Access
        // -----------------------------------------------------------------
        $display("\n--- Test 3: Engine Flash ROM Read Access ---");
        
        // Pre-load test byte directly into Flash ROM memory array
        flash_u13.memory_array[14'h0123] = 8'h7E;

        // Assert Flash selection and Read Enable for Flash address 0x0123
        eng_sel_flash = 1'b1;
        eng_oe_req    = 1'b1;
        eng_addr      = 14'h0123;
        #60; // Allow 60ns to satisfy SST39SF040 55ns t_ACC propagation delay

        if (f_ce_n !== 1'b0 || f_oe_n !== 1'b0 || m_ce_n !== 1'b1) begin
            $display("FAIL [FLASH]: Control signals incorrect! f_ce_n=%b, f_oe_n=%b, m_ce_n=%b", f_ce_n, f_oe_n, m_ce_n);
            $fatal(1);
        end
        if (mem_rdata !== 8'h7E) begin
            $display("FAIL [FLASH RD]: Expected 0x7E from Flash address 0x0123, got 0x%02h", mem_rdata);
            $fatal(1);
        end
        $display("PASS [FLASH RD]: Read back 0x7E correctly from Flash ROM address 0x0123.");

        eng_oe_req    = 1'b0;
        eng_sel_flash = 1'b0;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 4: Arbitration Priority (Engine vs Host Conflict)
        // -----------------------------------------------------------------
        $display("\n--- Test 4: Dual-Client Arbitration Priority ---");

        // Simultaneously request Host Write (0xAA to 0x30) and Engine Write (0x55 to 0x40)
        host_addr   = 8'h30;
        host_wdata  = 8'hAA;
        host_we_req = 1'b1;

        eng_addr    = 14'h0040;
        eng_wdata   = 8'h55;
        eng_we_req  = 1'b1;

        @(posedge mclk); #1;
        if (ca !== 14'h0040 || cd !== 8'h55) begin
            $display("FAIL [ARBITRATION]: Client 1 (Engine) should have won priority! Got ca=%h, cd=%h", ca, cd);
            $fatal(1);
        end
        $display("PASS [ARBITRATION]: Client 1 (Engine) correctly won priority over Client 0 (Host).");

        // Clear requests
        eng_we_req  = 1'b0;
        host_we_req = 1'b0;
        @(posedge mclk);
        @(posedge mclk);

        $display("\n=================================================");
        $display("=== SUCCESS: All Private Memory Tests Passed! ===");
        $display("=================================================");

        $finish;
    end

    // --- System Watchdog Timer ---
    initial begin
        #100000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end

endmodule