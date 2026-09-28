`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: fpu_mgmt_tb
 * FILE: sim/fpu_mgmt_tb.v
 * DESCRIPTION:
 * Standalone unit test for zx50_fpu_mgmt (Stack & Management Engine).
 *
 * TEST COVERAGE:
 * - Direct execution of Format 0xF management opcodes:
 *     * 0xF0 (CLR_STK) : Clears stack pointer to 0x00.
 *     * 0xF1 (POP_TOS) : Decrements SP by 4 bytes.
 *     * 0xFF (RESET)   : Resets stack pointer to 0x00.
 *     * 0xF8 (INVALID) : Asserts err_flag.
 * - Validates 1-tick alignment of done_p and sp_write_en strobes.
 ***************************************************************************************/

module fpu_mgmt_tb;

    // =========================================================================
    // 1. Clock Generation via System Clock Mezzanine (zx50_clock)
    // =========================================================================
    wire mclk, zclk;
    zx50_clock clk_gen (
        .run_in(1'b1),
        .step_n_in(1'b1), 
        .mclk(mclk), 
        .zclk(zclk)
    );

    // =========================================================================
    // 2. System Control Nets
    // =========================================================================
    reg        reset_n;
    reg        start_p;
    reg  [7:0] opcode;
    reg  [7:0] sp_in;

    wire [7:0] sp_out;
    wire       sp_write_en;
    wire       mgmt_sram_we_req;
    wire       mgmt_sram_oe_req;
    wire [7:0] mgmt_sram_wdata;
    wire [7:0] mgmt_sram_addr;
    wire       done_p;
    wire       err_flag;

    // =========================================================================
    // 3. Device Under Test (DUT)
    // =========================================================================
    zx50_fpu_mgmt dut (
        .mclk(mclk),
        .reset_n(reset_n),
        .start_p(start_p),
        .opcode(opcode),
        .sp_in(sp_in),
        .sp_out(sp_out),
        .sp_write_en(sp_write_en),
        .mgmt_sram_we_req(mgmt_sram_we_req),
        .mgmt_sram_oe_req(mgmt_sram_oe_req),
        .mgmt_sram_wdata(mgmt_sram_wdata),
        .mgmt_sram_addr(mgmt_sram_addr),
        .done_p(done_p),
        .err_flag(err_flag)
    );

    // =========================================================================
    // 4. Test Trigger Task (MCLK Domain)
    // =========================================================================
    task trigger_mgmt(
        input [7:0] cmd_opcode,
        input [7:0] current_sp
    );
        begin
            @(posedge mclk);
            opcode  = cmd_opcode;
            sp_in   = current_sp;
            start_p = 1'b1; // Pulse start trigger for 1 MCLK cycle

            @(posedge mclk);
            start_p = 1'b0;

            // Wait for 1-tick completion pulse
            while (!done_p) begin
                @(posedge mclk);
            end
        end
    endtask

    // =========================================================================
    // 5. Test Sequence
    // =========================================================================
    initial begin
        $dumpfile("waves/fpu_mgmt.vcd");
        $dumpvars(0, fpu_mgmt_tb);

        $display("=================================================");
        $display("=== Starting ZX50 Management Engine Unit Test ===");
        $display("=================================================");

        // Boot Reset
        reset_n = 1'b0;
        start_p = 1'b0;
        opcode  = 8'h00;
        sp_in   = 8'h00;

        #100;
        reset_n = 1'b1;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 1: Reset & Idle Verification
        // -----------------------------------------------------------------
        $display("\n--- Test 1: Reset & Idle Verification ---");
        if (done_p !== 1'b0 || err_flag !== 1'b0 || sp_write_en !== 1'b0) begin
            $display("FAIL [IDLE]: Strobes should be inactive LOW! done_p=%b, err=%b, sp_we=%b", done_p, err_flag, sp_write_en);
            $fatal(1);
        end
        $display("PASS [IDLE]: Management engine correctly idle on reset.");

        // -----------------------------------------------------------------
        // TEST 2: CLR_STK Opcode (0xF0)
        // -----------------------------------------------------------------
        $display("\n--- Test 2: CLR_STK Opcode (0xF0) ---");
        trigger_mgmt(8'hF0, 8'h1C);

        if (err_flag !== 1'b0 || sp_write_en !== 1'b1 || sp_out !== 8'h00) begin
            $display("FAIL [CLR_STK]: Expected sp_out=0x00, sp_we=1, got sp_out=0x%02h, sp_we=%b", sp_out, sp_write_en);
            $fatal(1);
        end
        $display("PASS [CLR_STK]: Stack pointer cleared to 0x00 with sp_write_en=1.");

        // -----------------------------------------------------------------
        // TEST 3: POP_TOS Opcode (0xF1)
        // -----------------------------------------------------------------
        $display("\n--- Test 3: POP_TOS Opcode (0xF1) ---");
        trigger_mgmt(8'hF1, 8'h10); // Current SP = 16 (4 frames)

        if (err_flag !== 1'b0 || sp_write_en !== 1'b1 || sp_out !== 8'h0C) begin
            $display("FAIL [POP_TOS]: Expected sp_out=0x0C (16-4), sp_we=1, got sp_out=0x%02h, sp_we=%b", sp_out, sp_write_en);
            $fatal(1);
        end
        $display("PASS [POP_TOS]: Stack pointer decremented from 0x10 to 0x0C with sp_write_en=1.");

        // -----------------------------------------------------------------
        // TEST 4: Soft RESET Opcode (0xFF)
        // -----------------------------------------------------------------
        $display("\n--- Test 4: Soft RESET Opcode (0xFF) ---");
        trigger_mgmt(8'hFF, 8'h20);

        if (err_flag !== 1'b0 || sp_write_en !== 1'b1 || sp_out !== 8'h00) begin
            $display("FAIL [RESET]: Expected sp_out=0x00, sp_we=1, got sp_out=0x%02h", sp_out);
            $fatal(1);
        end
        $display("PASS [RESET]: Executed soft reset and cleared SP output.");

        // -----------------------------------------------------------------
        // TEST 5: Unmapped Management Opcode (0xF8)
        // -----------------------------------------------------------------
        $display("\n--- Test 5: Unmapped Management Opcode (0xF8) ---");
        trigger_mgmt(8'hF8, 8'h08);

        if (err_flag !== 1'b1 || sp_write_en !== 1'b0) begin
            $display("FAIL [ERR 0xF8]: Expected err_flag=1 and sp_we=0, got err=%b, sp_we=%b", err_flag, sp_write_en);
            $fatal(1);
        end
        $display("PASS [ERR 0xF8]: Unmapped opcode correctly flagged error.");

        $display("\n=================================================");
        $display("=== SUCCESS: All Management Engine Tests Passed! ");
        $display("=================================================");

        $finish;
    end

    // =========================================================================
    // 6. System Watchdog Timer
    // =========================================================================
    initial begin
        #200000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end

endmodule
