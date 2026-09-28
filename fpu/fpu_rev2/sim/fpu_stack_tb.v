`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: fpu_stack_tb
 * DESCRIPTION:
 * Unit test for Port 0x70 Stack operations with automatic SRAM dump on failure.
 ***************************************************************************************/

module fpu_stack_tb;

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

    // --- Test Bench Variables ---
    reg [7:0] read_val;

    // --- Memory Stack Diagnostic Dump Task ---
    task dump_stack(input integer count);
        integer idx;
        begin
            $display("--- PRIVATE SRAM STACK DUMP (Current SP=0x%02h) ---", card0.cpld.sp);
            for (idx = 0; idx < count; idx = idx + 1) begin
                $display("  SRAM[0x%02h] = 0x%02h", idx[7:0], card0.fpu_sram.memory_array[idx]);
            end
            $display("--------------------------------------------------");
        end
    endtask

    // --- Test Sequence ---
    initial begin
        $dumpfile("waves/fpu_stack.vcd");
        $dumpvars(0, fpu_stack_tb);

        $display("=================================================");
        $display("=== Starting ZX50 FPU Stack PUSH/POP Unit Test ==");
        $display("=================================================");

        // Boot
        z80.boot_sequence();
        @(posedge zclk);

        if (card0.cpld.sp !== 8'h00) begin
            $display("FAIL [BOOT]: Initial SP expected 0x00, got %h", card0.cpld.sp);
            dump_stack(8);
            $fatal(1);
        end
        $display("PASS [BOOT]: Stack Pointer initialized to 0x00.");

        // TEST 1
        $display("\n--- Test 1: Single Byte PUSH & POP ---");
        z80.io_write(16'h0070, 8'hA5);
        if (card0.cpld.sp !== 8'h01) begin
            $display("FAIL [PUSH]: SP failed to increment on PUSH!");
            dump_stack(8);
            $fatal(1);
        end
        $display("PASS [PUSH]: Pushed byte 0xA5. SP advanced to 0x01.");

        z80.io_read(16'h0070, read_val);
        if (read_val !== 8'hA5 || card0.cpld.sp !== 8'h00) begin
            $display("FAIL [POP]: Expected 0xA5 (SP=0x00), got %h (SP=%h)", read_val, card0.cpld.sp);
            dump_stack(8);
            $fatal(1);
        end
        $display("PASS [POP]: Popped byte 0xA5 correctly. SP decremented to 0x00.");

        // TEST 2
        $display("\n--- Test 2: 4-Byte Frame PUSH & POP (32-Bit LIFO) ---");
        z80.io_write(16'h0070, 8'hDE); $display("PASS [PUSH]: Pushed byte 0xDE (SP=0x01).");
        z80.io_write(16'h0070, 8'hAD); $display("PASS [PUSH]: Pushed byte 0xAD (SP=0x02).");
        z80.io_write(16'h0070, 8'hBE); $display("PASS [PUSH]: Pushed byte 0xBE (SP=0x03).");
        z80.io_write(16'h0070, 8'hEF); $display("PASS [PUSH]: Pushed byte 0xEF (SP=0x04).");

        z80.io_read(16'h0070, read_val);
        if (read_val !== 8'hEF || card0.cpld.sp !== 8'h03) begin
            $display("FAIL [POP 1]: Expected 0xEF (SP=0x03), got %h (SP=%h)", read_val, card0.cpld.sp);
            dump_stack(8);
            $fatal(1);
        end
        $display("PASS [POP 1]: Popped byte 0xEF (SP=0x03).");

        z80.io_read(16'h0070, read_val);
        if (read_val !== 8'hBE || card0.cpld.sp !== 8'h02) begin
            $display("FAIL [POP 2]: Expected 0xBE (SP=0x02), got %h (SP=%h)", read_val, card0.cpld.sp);
            dump_stack(8);
            $fatal(1);
        end
        $display("PASS [POP 2]: Popped byte 0xBE (SP=0x02).");

        z80.io_read(16'h0070, read_val);
        if (read_val !== 8'hAD || card0.cpld.sp !== 8'h01) begin
            $display("FAIL [POP 3]: Expected 0xAD (SP=0x01), got %h (SP=%h)", read_val, card0.cpld.sp);
            dump_stack(8);
            $fatal(1);
        end
        $display("PASS [POP 3]: Popped byte 0xAD (SP=0x01).");

        z80.io_read(16'h0070, read_val);
        if (read_val !== 8'hDE || card0.cpld.sp !== 8'h00) begin
            $display("FAIL [POP 4]: Expected 0xDE (SP=0x00), got %h (SP=%h)", read_val, card0.cpld.sp);
            dump_stack(8);
            $fatal(1);
        end
        $display("PASS [POP 4]: Popped byte 0xDE (SP=0x00).");

        // TEST 3
        $display("\n--- Test 3: Interleaved PUSH & POP ---");
        z80.io_write(16'h0070, 8'h11);
        z80.io_write(16'h0070, 8'h22);

        z80.io_read(16'h0070, read_val);
        if (read_val !== 8'h22 || card0.cpld.sp !== 8'h01) begin
            $display("FAIL [INTERLEAVED]: Expected 0x22 (SP=0x01), got %h", read_val);
            dump_stack(8);
            $fatal(1);
        end

        z80.io_write(16'h0070, 8'h33);

        z80.io_read(16'h0070, read_val);
        if (read_val !== 8'h33 || card0.cpld.sp !== 8'h01) begin
            $display("FAIL [INTERLEAVED]: Expected 0x33 (SP=0x01), got %h", read_val);
            dump_stack(8);
            $fatal(1);
        end

        z80.io_read(16'h0070, read_val);
        if (read_val !== 8'h11 || card0.cpld.sp !== 8'h00) begin
            $display("FAIL [INTERLEAVED]: Expected 0x11 (SP=0x00), got %h", read_val);
            dump_stack(8);
            $fatal(1);
        end
        $display("PASS [INTERLEAVED]: Sequence validated successfully.");

        $display("\n=================================================");
        $display("=== SUCCESS: All FPU Stack Tests Passed! ========");
        $display("=================================================");

        $finish;
    end

    initial begin
        #500000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end

endmodule