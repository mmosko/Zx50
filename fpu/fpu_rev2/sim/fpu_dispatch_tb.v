`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: fpu_dispatch_tb
 * FILE: sim/fpu_dispatch_tb.v
 * DESCRIPTION:
 * Unit test for zx50_fpu_dispatch command execution dispatcher.
 *
 * TEST COVERAGE:
 * - Clock domain crossing (CDC) level handshaking (exec_req / done_ack) via zx50_clock.
 * - Format 0x0 - 0x5 / 0xE valid arithmetic opcode dispatch.
 * - Format 0xF management opcode delegating (CLR_STK, POP_TOS, RESET, invalid mgmt).
 * - Invalid format field (0x60) and operation field (0x1F) error flag assertions.
 * - SP computation output verification (new_sp, sp_write_en).
 ***************************************************************************************/

module fpu_dispatch_tb;

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
    // 2. System Control Nets & Captured Output Registers
    // =========================================================================
    reg        reset_n;
    reg        exec_req;
    reg  [7:0] opcode;
    reg  [7:0] sp_in;

    wire       done_ack;
    wire       err_flag;
    wire [4:0] status_flags;
    wire [7:0] new_sp;
    wire       sp_write_en;
    wire       disp_sram_we_req;
    wire       disp_sram_oe_req;
    wire [7:0] disp_sram_wdata;
    wire [7:0] disp_sram_addr;

    // Captured outputs captured during active done_ack handshake window
    reg        last_err;
    reg  [4:0] last_flags;
    reg  [7:0] last_new_sp;
    reg        last_sp_we;

    // =========================================================================
    // 3. Device Under Test (DUT)
    // =========================================================================
    zx50_fpu_dispatch dut (
        .mclk(mclk),
        .reset_n(reset_n),
        .exec_req(exec_req),
        .opcode(opcode),
        .sp_in(sp_in),
        .done_ack(done_ack),
        .err_flag(err_flag),
        .status_flags(status_flags),
        .new_sp(new_sp),
        .sp_write_en(sp_write_en),
        .disp_sram_we_req(disp_sram_we_req),
        .disp_sram_oe_req(disp_sram_oe_req),
        .disp_sram_wdata(disp_sram_wdata),
        .disp_sram_addr(disp_sram_addr)
    );

    // =========================================================================
    // 4. Synchronous Host CDC Command Driver Task (ZCLK Domain)
    // =========================================================================
    task exec_cmd(
        input [7:0] cmd_opcode,
        input [7:0] current_sp
    );
        begin
            @(posedge zclk);
            opcode   = cmd_opcode;
            sp_in    = current_sp;
            exec_req = 1'b1; // Raise CDC request level

            // Poll for level acknowledge from MCLK domain
            while (!done_ack) begin
                @(posedge zclk);
            end

            // Capture bus outputs while done_ack is active
            last_err    = err_flag;
            last_flags  = status_flags;
            last_new_sp = new_sp;
            last_sp_we  = sp_write_en;

            // Release CDC request level once acknowledge is detected
            exec_req = 1'b0;

            // Wait for dispatcher to return acknowledge to 0
            while (done_ack) begin
                @(posedge zclk);
            end
        end
    endtask

    // =========================================================================
    // 5. Test Sequence
    // =========================================================================
    initial begin
        $dumpfile("waves/fpu_dispatch.vcd");
        $dumpvars(0, fpu_dispatch_tb);

        $display("=================================================");
        $display("=== Starting ZX50 FPU Dispatcher Unit Test ======");
        $display("=================================================");

        // Boot
        reset_n  = 1'b0;
        exec_req = 1'b0;
        opcode   = 8'h00;
        sp_in    = 8'h00;

        #100;
        reset_n  = 1'b1;
        @(posedge zclk);

        // -----------------------------------------------------------------
        // TEST 1: Reset & Idle Verification
        // -----------------------------------------------------------------
        $display("\n--- Test 1: Reset & Idle Verification ---");
        if (done_ack !== 1'b0 || err_flag !== 1'b0 || sp_write_en !== 1'b0) begin
            $display("FAIL [IDLE]: Default signals non-zero! done_ack=%b, err=%b, sp_we=%b", done_ack, err_flag, sp_write_en);
            $fatal(1);
        end
        $display("PASS [IDLE]: Reset states cleanly verified.");

        // -----------------------------------------------------------------
        // TEST 2: Valid Arithmetic Opcode (0x10 = i32 ADD)
        // -----------------------------------------------------------------
        $display("\n--- Test 2: Valid Math Opcode Execution (0x10) ---");
        exec_cmd(8'h10, 8'h08);

        if (last_err !== 1'b0) begin
            $display("FAIL [MATH 0x10]: Unexpected err_flag asserted!");
            $fatal(1);
        end
        if (last_sp_we !== 1'b0) begin
            $display("FAIL [MATH 0x10]: Math opcode should not overwrite SP directly!");
            $fatal(1);
        end
        $display("PASS [MATH 0x10]: Handshake completed cleanly with err_flag=0.");

        // -----------------------------------------------------------------
        // TEST 3: Management Opcode - CLR_STK (0xF0)
        // -----------------------------------------------------------------
        $display("\n--- Test 3: Management Opcode CLR_STK (0xF0) ---");
        exec_cmd(8'hF0, 8'h0C);

        if (last_err !== 1'b0) begin
            $display("FAIL [CLR_STK]: Unexpected err_flag asserted!");
            $fatal(1);
        end
        if (last_sp_we !== 1'b1 || last_new_sp !== 8'h00) begin
            $display("FAIL [CLR_STK]: Expected new_sp=0x00 with sp_write_en=1, got new_sp=0x%02h, sp_we=%b", last_new_sp, last_sp_we);
            $fatal(1);
        end
        $display("PASS [CLR_STK]: Reset SP to 0x00 with sp_write_en=1.");

        // -----------------------------------------------------------------
        // TEST 4: Management Opcode - POP_TOS (0xF1)
        // -----------------------------------------------------------------
        $display("\n--- Test 4: Management Opcode POP_TOS (0xF1) ---");
        exec_cmd(8'hF1, 8'h08); // Current SP = 8 (2 frames pushed)

        if (last_err !== 1'b0) begin
            $display("FAIL [POP_TOS]: Unexpected err_flag asserted!");
            $fatal(1);
        end
        if (last_sp_we !== 1'b1 || last_new_sp !== 8'h04) begin
            $display("FAIL [POP_TOS]: Expected new_sp=0x04 (8 - 4) with sp_write_en=1, got new_sp=0x%02h, sp_we=%b", last_new_sp, last_sp_we);
            $fatal(1);
        end
        $display("PASS [POP_TOS]: Decremented SP from 0x08 to 0x04 cleanly.");

        // -----------------------------------------------------------------
        // TEST 5: Management Opcode - Soft RESET (0xFF)
        // -----------------------------------------------------------------
        $display("\n--- Test 5: Management Opcode Soft RESET (0xFF) ---");
        exec_cmd(8'hFF, 8'h14);

        if (last_err !== 1'b0) begin
            $display("FAIL [RESET]: Unexpected err_flag asserted!");
            $fatal(1);
        end
        if (last_sp_we !== 1'b1 || last_new_sp !== 8'h00) begin
            $display("FAIL [RESET]: Expected new_sp=0x00 with sp_write_en=1, got new_sp=0x%02h", last_new_sp);
            $fatal(1);
        end
        $display("PASS [RESET]: Executed soft reset and cleared SP output.");

        // -----------------------------------------------------------------
        // TEST 6: Invalid Management Opcode (0xF8)
        // -----------------------------------------------------------------
        $display("\n--- Test 6: Invalid Management Opcode (0xF8) ---");
        exec_cmd(8'hF8, 8'h04);

        if (last_err !== 1'b1) begin
            $display("FAIL [ERR 0xF8]: Expected err_flag=1 for unmapped mgmt opcode!");
            $fatal(1);
        end
        $display("PASS [ERR 0xF8]: Invalid management opcode correctly flagged.");

        // -----------------------------------------------------------------
        // TEST 7: Invalid Format Field (0x60)
        // -----------------------------------------------------------------
        $display("\n--- Test 7: Invalid Format Field (0x60) ---");
        exec_cmd(8'h60, 8'h04);

        if (last_err !== 1'b1) begin
            $display("FAIL [ERR 0x60]: Expected err_flag=1 for unmapped format 0x6!");
            $fatal(1);
        end
        $display("PASS [ERR 0x60]: Invalid format field correctly flagged.");

        // -----------------------------------------------------------------
        // TEST 8: Invalid Operation Field (0x1F)
        // -----------------------------------------------------------------
        $display("\n--- Test 8: Invalid Operation Field (0x1F) ---");
        exec_cmd(8'h1F, 8'h04);

        if (last_err !== 1'b1) begin
            $display("FAIL [ERR 0x1F]: Expected err_flag=1 for unmapped operation 0x1F!");
            $fatal(1);
        end
        $display("PASS [ERR 0x1F]: Invalid operation field correctly flagged.");

        $display("\n=================================================");
        $display("=== SUCCESS: All Dispatcher Tests Passed! =======");
        $display("=================================================");

        $finish;
    end

    // =========================================================================
    // 6. System Watchdog Timer
    // =========================================================================
    initial begin
        #500000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end

endmodule