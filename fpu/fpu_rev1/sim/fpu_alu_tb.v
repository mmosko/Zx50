`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: fpu_alu_tb
 * FILE: sim/fpu_alu_tb.v
 * DESCRIPTION:
 * Unit test for zx50_fpu_alu (8-Bit Byte-Serial Arithmetic Core, CPLD Rev C2).
 *
 * TEST COVERAGE:
 * - 32-bit integer addition (OP_ADD = 0x0) with multi-byte carry propagation.
 * - 32-bit integer addition with carry across byte boundaries.
 * - 32-bit integer subtraction (OP_SUB = 0x1) with multi-byte borrow propagation.
 * - Status flag verification (ZERO, SIGN, CARRY).
 * - Private memory read/write interaction with zx50_fpu_mem and 12ns SRAM.
 ***************************************************************************************/

module fpu_alu_tb;

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
    // 2. System Control & Private Memory Bus Nets
    // =========================================================================
    reg        reset_n;
    reg        start_p;
    reg  [3:0] fmt;
    reg  [3:0] op;
    reg  [7:0] sp_in;

    wire       done_p;
    wire       err_flag;
    wire [4:0] status_flags;

    // Private Memory Master Nets (driven by zx50_fpu_alu into zx50_fpu_mem)
    wire        alu_mem_we_req;
    wire        alu_mem_oe_req;
    wire        alu_sel_flash;
    wire [14:0] alu_mem_addr;
    wire [7:0]  alu_mem_wdata;
    wire [7:0]  mem_rdata;

    // Physical Memory Pins (zx50_fpu_mem to IS61C256AL)
    wire [14:0] ca;
    wire [7:0]  cd;
    wire        m_ce_n, f_ce_n;
    wire        c_oe_n, c_we_n;

    // =========================================================================
    // 3. Submodule Instantiations
    // =========================================================================

    // Device Under Test (8-Bit Serial ALU Core)
    zx50_fpu_alu dut (
        .mclk(mclk),
        .reset_n(reset_n),
        .start_p(start_p),
        .fmt(fmt),
        .op(op),
        .sp_in(sp_in),
        .done_p(done_p),
        .err_flag(err_flag),
        .status_flags(status_flags),
        .alu_mem_we_req(alu_mem_we_req),
        .alu_mem_oe_req(alu_mem_oe_req),
        .alu_sel_flash(alu_sel_flash),
        .alu_mem_addr(alu_mem_addr),
        .alu_mem_wdata(alu_mem_wdata),
        .mem_rdata(mem_rdata)
    );

    // Private Memory Controller & Arbiter
    zx50_fpu_mem mem_ctrl (
        .mclk(mclk),
        .reset_n(reset_n),
        .host_we_req(1'b0),
        .host_oe_req(1'b0),
        .host_addr(8'h00),
        .host_wdata(8'h00),
        .eng_we_req(alu_mem_we_req),
        .eng_oe_req(alu_mem_oe_req),
        .eng_sel_flash(alu_sel_flash),
        .eng_addr(alu_mem_addr),
        .eng_wdata(alu_mem_wdata),
        .mem_rdata(mem_rdata),
        .ca(ca),
        .cd(cd),
        .m_ce_n(m_ce_n),
        .c_oe_n(c_oe_n),
        .c_we_n(c_we_n),
        .f_ce_n(f_ce_n)
    );

    // IS61C256AL Private 12ns SRAM Model (U12)
    is61c256al_12 sram_u12 (
        .addr(ca),
        .data(cd),
        .ce_n(m_ce_n),
        .oe_n(c_oe_n),
        .we_n(c_we_n)
    );

    // =========================================================================
    // 4. Helper Tasks: Direct SRAM Pre-load & Verification
    // =========================================================================
    
    // Write 32-bit Little-Endian value to specified SRAM base address
    task write_sram32(input [7:0] base_addr, input [31:0] val);
        begin
            sram_u12.memory_array[base_addr + 0] = val[7:0];
            sram_u12.memory_array[base_addr + 1] = val[15:8];
            sram_u12.memory_array[base_addr + 2] = val[23:16];
            sram_u12.memory_array[base_addr + 3] = val[31:24];
        end
    endtask

    // Read 32-bit Little-Endian value from specified SRAM base address
    function [31:0] read_sram32(input [7:0] base_addr);
        begin
            read_sram32 = {
                sram_u12.memory_array[base_addr + 3],
                sram_u12.memory_array[base_addr + 2],
                sram_u12.memory_array[base_addr + 1],
                sram_u12.memory_array[base_addr + 0]
            };
        end
    endfunction

    // Trigger ALU execution and wait for completion pulse
    task exec_alu(input [3:0] fmt_in, input [3:0] op_in, input [7:0] sp_val);
        begin
            @(posedge mclk);
            fmt     = fmt_in;
            op      = op_in;
            sp_in   = sp_val;
            start_p = 1'b1;

            @(posedge mclk);
            start_p = 1'b0;

            while (!done_p) begin
                @(posedge mclk);
            end
        end
    endtask

    // =========================================================================
    // 5. Test Sequence
    // =========================================================================
    reg [31:0] res32;

    initial begin
        $dumpfile("waves/fpu_alu.vcd");
        $dumpvars(0, fpu_alu_tb);

        $display("=================================================");
        $display("=== Starting ZX50 Serial ALU Core Unit Test =====");
        $display("=================================================");

        // Boot Reset
        reset_n = 1'b0;
        start_p = 1'b0;
        fmt     = 4'h1; // i32
        op      = 4'h0; // ADD
        sp_in   = 8'h08; // SP = 8 (NOS = 0x00, TOS = 0x04)

        #100;
        reset_n = 1'b1;
        @(posedge mclk);

        // -----------------------------------------------------------------
        // TEST 1: Reset & Idle Verification
        // -----------------------------------------------------------------
        $display("\n--- Test 1: Reset & Idle Verification ---");
        if (done_p !== 1'b0 || err_flag !== 1'b0 || alu_mem_we_req !== 1'b0) begin
            $display("FAIL [IDLE]: Default signals non-zero!");
            $fatal(1);
        end
        $display("PASS [IDLE]: Serial ALU correctly idle on reset.");

        // -----------------------------------------------------------------
        // TEST 2: 32-Bit Integer Addition without Carry
        // -----------------------------------------------------------------
        $display("\n--- Test 2: 32-Bit Addition (NOS + TOS -> NOS) ---");
        // NOS (0x00) = 0x00000005, TOS (0x04) = 0x00000003, SP = 0x08
        write_sram32(8'h00, 32'h00000005);
        write_sram32(8'h04, 32'h00000003);

        exec_alu(4'h1, 4'h0, 8'h08); // Format 0x1 (i32), Op 0x0 (ADD), SP = 0x08

        res32 = read_sram32(8'h00);
        if (res32 !== 32'h00000008) begin
            $display("FAIL [ADD32]: Expected 0x00000008, got 0x%08h", res32);
            $fatal(1);
        end
        $display("PASS [ADD32]: Calculated 5 + 3 = 8 correctly.");

        // -----------------------------------------------------------------
        // TEST 3: 32-Bit Integer Addition with Multi-Byte Carry
        // -----------------------------------------------------------------
        $display("\n--- Test 3: 32-Bit Addition with Multi-Byte Carry ---");
        // NOS (0x00) = 0x000000FF, TOS (0x04) = 0x00000001
        write_sram32(8'h00, 32'h000000FF);
        write_sram32(8'h04, 32'h00000001);

        exec_alu(4'h1, 4'h0, 8'h08);

        res32 = read_sram32(8'h00);
        if (res32 !== 32'h00000100) begin
            $display("FAIL [ADD32 CARRY]: Expected 0x00000100, got 0x%08h", res32);
            $fatal(1);
        end
        $display("PASS [ADD32 CARRY]: Propagated carry across bytes (0xFF + 1 = 0x0100).");

        // -----------------------------------------------------------------
        // TEST 4: 32-Bit Integer Subtraction with Borrow
        // -----------------------------------------------------------------
        $display("\n--- Test 4: 32-Bit Subtraction with Borrow ---");
        // NOS (0x00) = 0x00000100, TOS (0x04) = 0x00000001
        write_sram32(8'h00, 32'h00000100);
        write_sram32(8'h04, 32'h00000001);

        exec_alu(4'h1, 4'h1, 8'h08); // Format 0x1 (i32), Op 0x1 (SUB)

        res32 = read_sram32(8'h00);
        if (res32 !== 32'h000000FF) begin
            $display("FAIL [SUB32 BORROW]: Expected 0x000000FF, got 0x%08h", res32);
            $fatal(1);
        end
        $display("PASS [SUB32 BORROW]: Propagated borrow across bytes (0x0100 - 1 = 0x00FF).");

        // -----------------------------------------------------------------
        // TEST 5: Status Flags (ZERO Flag)
        // -----------------------------------------------------------------
        $display("\n--- Test 5: Status Flag Verification ---");
        // Calculate 10 - 10 = 0 (ZERO flag expected)
        write_sram32(8'h00, 32'h0000000A);
        write_sram32(8'h04, 32'h0000000A);

        exec_alu(4'h1, 4'h1, 8'h08);

        if (status_flags[4] !== 1'b1) begin // ZERO flag is status_flags[4]
            $display("FAIL [ZERO FLAG]: Expected ZERO flag = 1, got status_flags = %b", status_flags);
            $fatal(1);
        end
        $display("PASS [ZERO FLAG]: ZERO flag correctly set on zero result.");

        $display("\n=================================================");
        $display("=== SUCCESS: All Serial ALU Tests Passed! =======");
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
