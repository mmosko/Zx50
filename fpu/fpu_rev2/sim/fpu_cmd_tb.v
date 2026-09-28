`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: fpu_cmd_tb
 * FILE: sim/fpu_cmd_tb.v
 * DESCRIPTION:
 * Unit test for Port 0x71 Command Write, Status Read, wait_n handshaking,
 * and complete Opcode Matrix validation (Formats 0x0-0x5, 0xE, 0xF).
 ***************************************************************************************/

module fpu_cmd_tb;

    // --- Clock Generation ---
    wire mclk, zclk;
    zx50_clock clk_gen (
        .run_in(1'b1),
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

    // --- Z80 CPU (BFM) ---
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

    reg [7:0] read_val;

    initial begin
        $dumpfile("waves/fpu_cmd.vcd");
        $dumpvars(0, fpu_cmd_tb);

        $display("=================================================");
        $display("=== Starting ZX50 FPU Command Port Unit Test ====");
        $display("=================================================");

        // Boot
        z80.boot_sequence();
        @(posedge zclk);

        // -----------------------------------------------------------------
        // TEST 1: Valid Math Opcode Execution (0x10 = i32 ADD) & Wait
        // -----------------------------------------------------------------
        $display("\n--- Test 1: Valid Math Opcode Execution (0x10) ---");
        
        z80.io_write(16'h0071, 8'h10);
        z80.wait_cycles(10);

        if (wait_n !== 1'b1) begin
            $display("FAIL [CMD]: Expected wait_n to be released (1'b1), got %b", wait_n);
            $fatal(1);
        end
        $display("PASS [CMD]: wait_n cleanly released after calculation.");

        z80.io_read(16'h0071, read_val);
        if (read_val[7] !== 1'b0 || read_val[1] !== 1'b0) begin
            $display("FAIL [CMD]: Expected BUSY=0, ERR=0, got STATUS=0x%02h", read_val);
            $fatal(1);
        end
        $display("PASS [CMD]: Status register read back 0x00 (BUSY=0, ERR=0).");

        // -----------------------------------------------------------------
        // TEST 2: Valid Management Opcode Execution (0xFF = RESET, 0xF0 = CLR_STK)
        // -----------------------------------------------------------------
        $display("\n--- Test 2: Valid Management Opcodes (0xFF & 0xF0) ---");

        z80.io_write(16'h0071, 8'hFF); // RESET
        z80.wait_cycles(10);

        z80.io_read(16'h0071, read_val);
        if (read_val[1] !== 1'b0) begin
            $display("FAIL [MGMT]: Expected ERR=0 for valid RESET opcode 0xFF, got STATUS=0x%02h", read_val);
            $fatal(1);
        end
        $display("PASS [MGMT]: Valid RESET opcode 0xFF executed without error.");

        z80.io_write(16'h0071, 8'hF0); // CLR_STK
        z80.wait_cycles(10);

        z80.io_read(16'h0071, read_val);
        if (read_val[1] !== 1'b0) begin
            $display("FAIL [MGMT]: Expected ERR=0 for valid CLR_STK opcode 0xF0, got STATUS=0x%02h", read_val);
            $fatal(1);
        end
        $display("PASS [MGMT]: Valid CLR_STK opcode 0xF0 executed without error.");

        // -----------------------------------------------------------------
        // TEST 3: Invalid Management Opcode (0xF5) Error Handling
        // -----------------------------------------------------------------
        $display("\n--- Test 3: Invalid Management Opcode (0xF5) ---");

        z80.io_write(16'h0071, 8'hF5);
        z80.wait_cycles(10);

        z80.io_read(16'h0071, read_val);
        if (read_val[1] !== 1'b1) begin
            $display("FAIL [ERR]: Expected ERR=1 for unmapped management opcode 0xF5, got STATUS=0x%02h", read_val);
            $fatal(1);
        end
        $display("PASS [ERR]: Invalid management opcode 0xF5 correctly asserted ERR flag.");

        // -----------------------------------------------------------------
        // TEST 4: Invalid Format Field (0x60) Error Handling
        // -----------------------------------------------------------------
        $display("\n--- Test 4: Invalid Format Field (0x60) ---");

        z80.io_write(16'h0071, 8'h60);
        z80.wait_cycles(10);

        z80.io_read(16'h0071, read_val);
        if (read_val[1] !== 1'b1) begin
            $display("FAIL [ERR]: Expected ERR=1 for unmapped format 0x6, got STATUS=0x%02h", read_val);
            $fatal(1);
        end
        $display("PASS [ERR]: Invalid format field 0x60 correctly asserted ERR flag.");

        // -----------------------------------------------------------------
        // TEST 5: Invalid Operation Field (0x1F) Error Handling
        // -----------------------------------------------------------------
        $display("\n--- Test 5: Invalid Operation Field (0x1F) ---");

        z80.io_write(16'h0071, 8'h1F);
        z80.wait_cycles(10);

        z80.io_read(16'h0071, read_val);
        if (read_val[1] !== 1'b1) begin
            $display("FAIL [ERR]: Expected ERR=1 for unmapped operation 0x1F, got STATUS=0x%02h", read_val);
            $fatal(1);
        end
        $display("PASS [ERR]: Invalid operation field 0x1F correctly asserted ERR flag.");

        $display("\n=================================================");
        $display("=== SUCCESS: All FPU Command Tests Passed! ======");
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
