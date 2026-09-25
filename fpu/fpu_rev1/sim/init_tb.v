`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: init_tb
 * DESCRIPTION:
 * Testbench to verify post-reset initialization of the Zx50 FPU Subsystem (card0).
 * Validates internal CPLD registers, private memory deselect lines, open-drain 
 * handshake lines, and initial address bus states following a Z80 boot sequence.
 ***************************************************************************************/

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

    // --- Shadow Bus ---
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n;
    wire [15:0] sh_addr;
    wire [7:0]  sh_data;

    // --- Backplane ---
    zx50_backplane backplane (
        .z80_addr(z80_a),
        .z80_data(z80_d),
        .z80_mreq_n(z80_mreq_n),
        .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n),
        .z80_wr_n(z80_wr_n),
        .z80_m1_n(z80_m1_n),
        .z80_wait_n(wait_n),
        .z80_int_n(int_n),
        .z80_reset_n(reset_n),
        .sh_addr(sh_addr), 
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), 
        .sh_rw_n(sh_rw_n), 
        .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n),
        .sh_done_n(sh_done_n),
        .sh_busy_n(sh_busy_n)
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

    // --- Device Under Test ---
    zx50_fpu_block #(
        .RAM_INIT_FILE(""),
        .ROM_INIT_FILE("")
    ) card0 (
        .mclk(mclk),
        .zclk(zclk),
        .reset_n(reset_n),
        .clk_spd(1'b1), // Fast clock (40MHz)
        .z80_a(z80_a),
        .z80_d(z80_d),
        .z80_mreq_n(z80_mreq_n),
        .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n),
        .z80_wr_n(z80_wr_n),
        .z80_m1_n(z80_m1_n),
        .wait_n(wait_n),
        .int_n(int_n)
    );

    // --- Test Sequence ---
    initial begin
        $dumpfile("waves/init.vcd");
        $dumpvars(0, init_tb);

        $display("=================================================");
        $display("=== Starting ZX50 FPU Reset & Init Validation ===");
        $display("=================================================");

        // 1. Execute Z80 Boot & Reset Pulse
        z80.boot_sequence();
        @(posedge zclk);

        // 2. Validate CPLD Internal Register States
        if (card0.cpld.sp !== 8'h00) begin
            $display("FAIL [INIT]: Expected Stack Pointer SP=00, got %h", card0.cpld.sp);
            $fatal(1);
        end
        $display("PASS [INIT]: Stack Pointer initialized to 0x00.");

        if (card0.cpld.status_reg !== 8'h00) begin
            $display("FAIL [INIT]: Expected STATUS=00 (BUSY=0, ERR=0), got %h", card0.cpld.status_reg);
            $fatal(1);
        end
        $display("PASS [INIT]: Status register initialized to 0x00.");

        if (card0.cpld.opcode_reg !== 8'h00) begin
            $display("FAIL [INIT]: Expected OPCODE=00, got %h", card0.cpld.opcode_reg);
            $fatal(1);
        end
        $display("PASS [INIT]: Opcode register initialized to 0x00.");

        // 3. Validate Open-Drain Handshake Bus Lines (Should be High-Z, pulled HIGH by backplane)
        if (wait_n !== 1'b1) begin
            $display("FAIL [INIT]: Expected wait_n=1 (High-Z pulled high), got %b", wait_n);
            $fatal(1);
        end
        $display("PASS [INIT]: wait_n line cleanly released to High-Z.");

        if (int_n !== 1'b1) begin
            $display("FAIL [INIT]: Expected int_n=1 (High-Z pulled high), got %b", int_n);
            $fatal(1);
        end
        $display("PASS [INIT]: int_n line cleanly released to High-Z.");

        // 4. Validate Private Memory Controls (All deselects must be HIGH/1)
        if (card0.m_ce_n !== 1'b1 || card0.c_oe_n !== 1'b1 || card0.c_we_n !== 1'b1) begin
            $display("FAIL [INIT]: Private SRAM controls active during idle! m_ce_n=%b, c_oe_n=%b, c_we_n=%b",
                     card0.m_ce_n, card0.c_oe_n, card0.c_we_n);
            $fatal(1);
        end
        $display("PASS [INIT]: Private SRAM (U12) control signals deselected.");

        if (card0.f_ce_n !== 1'b1 || card0.c_oe_n !== 1'b1 || card0.c_we_n !== 1'b1) begin
            $display("FAIL [INIT]: Private Flash controls active during idle! f_ce_n=%b, c_oe_n=%b, c_we_n=%b",
                     card0.f_ce_n, card0.c_oe_n, card0.c_we_n);
            $fatal(1);
        end
        $display("PASS [INIT]: Private Flash (U13) control signals deselected.");

        // 5. Validate Private Address Bus
        if (card0.ca !== 14'h0000) begin
            $display("FAIL [INIT]: Expected Private Address CA=0000, got %h", card0.ca);
            $fatal(1);
        end
        $display("PASS [INIT]: Private Address bus CA driven to 0x0000.");

        $display("=================================================");
        $display("=== SUCCESS: All Init Checks Passed Cleanly! ===");
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
