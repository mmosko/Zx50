`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_priority_tb
 * DESCRIPTION:
 * Validates the bus arbitration and priority logic of the Universal Shadow Bus.
 * * TIMING VALIDATION ADDED:
 * This test now dynamically measures the elapsed time of the Z80 transactions 
 * during a DMA collision. If the CPLD's state machine inserts unnecessary WAIT 
 * states or stalls the handoff, the test will flag a TIMING VIOLATION and fail, 
 * even if the payload data is ultimately correct.
 ***************************************************************************************/

module zx50_shadow_priority_tb;

    // --- 1. System Clocks & Signals ---
    wire mclk, zclk;
    zx50_clock clk_gen (.mclk(mclk), .zclk(zclk));

    reg reset_n, boot_en_n;

    // --- 2. Z80 Backplane Buses ---
    wire [15:0] z80_addr;
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n;
    
    wire c0_wait_n, c1_wait_n;
    wire shared_wait_n = c0_wait_n & c1_wait_n; 
    
    wire c0_ieo, c1_ieo;
    wire z80_int_n; 

    // --- 3. Shadow Bus Backplane ---
    wire [15:0] sh_addr; 
    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n;

    zx50_backplane passive_backplane (
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), 
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n), 
        .z80_wait_n(shared_wait_n), .z80_int_n(z80_int_n),
        
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // --- 4. System Instantiations ---
    z80_cpu_util z80 (
        .clk(zclk), .addr(z80_addr), .data(z80_data),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(shared_wait_n)
    );

    zx50_mem_card card0 ( // MASTER
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(4'h0),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(1'b1), .z80_ieo(c0_ieo),
        .z80_wait_n(c0_wait_n), .z80_int_n(z80_int_n),
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    zx50_mem_card card1 ( // SLAVE
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(4'h1),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(c0_ieo), .z80_ieo(c1_ieo), 
        .z80_wait_n(c1_wait_n), .z80_int_n(z80_int_n),
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // --- 5. Test Utilities ---
    integer i;
    reg [7:0] read_val, vector;
    integer errors = 0;
    
    // Variables for cycle-time tracking
    time start_time, elapsed_time;

    task verify_payload;
        input [7:0] base_val;
        begin
            for (i = 0; i < 16; i = i + 1) begin
                z80.mem_read(16'h1000 + i, read_val); 
                if (read_val !== (i + base_val)) begin
                    $display("!!! DATA CORRUPTION at Offset %0d. Expected %0x, got %0x", i, (i + base_val), read_val);
                    errors = errors + 1;
                end
            end
        end
    endtask

    // --- 6. Main Test Sequence ---
    initial begin
        $dumpfile("waves/zx50_shadow_priority.vcd");
        $dumpvars(0, zx50_shadow_priority_tb);
        
        boot_en_n = 1; 

        $display("\n[%0t] === SYSTEM POWER ON ===", $time);
        reset_n = 1; clk_gen.wait_mclk(5); 
        reset_n = 0; clk_gen.wait_mclk(50); 
        reset_n = 1; 
        clk_gen.wait_mclk(20); 

        z80.io_write(16'h0030, 8'h00);
        z80.io_write(16'h0131, 8'h00);

        // =========================================================
        // TEST 1: Z80 MREQ TO SLAVE
        // Maximum Expected Duration: ~550ns
        // =========================================================
        $display("\n[%0t] === TEST 1: Z80 MREQ to SLAVE during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hA0);

        z80.io_write(16'h2041, 8'h00); 
        z80.io_write(16'h8841, 8'h00); 
        z80.io_write(16'h4040, 8'h00); 
        z80.io_write(16'h8840, 8'h00); 

        $display("[%0t] Z80 forcefully reading Slave memory (0x1008)...", $time);
        start_time = $time;
        z80.mem_read(16'h1008, read_val);
        elapsed_time = $time - start_time;
        
        $display("[%0t] Z80 Slave read completed in %0d ps. Value: %x", $time, elapsed_time, read_val);
        
        // Assert timing limits
        if (elapsed_time > 550000) begin
            $display("!!! TIMING VIOLATION: Transaction took %0d ps (Expected < 550000 ps) !!!", elapsed_time);
            errors = errors + 1;
        end

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 1...", $time);
        verify_payload(8'hA0);

        // =========================================================
        // TEST 2: Z80 MREQ TO MASTER
        // Maximum Expected Duration: ~450ns
        // =========================================================
        $display("\n[%0t] === TEST 2: Z80 MREQ to MASTER during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hB0);

        z80.io_write(16'h2041, 8'h00); 
        z80.io_write(16'h8841, 8'h00); 
        z80.io_write(16'h4040, 8'h00); 
        z80.io_write(16'h8840, 8'h00); 

        $display("[%0t] Z80 forcefully reading Master memory (0x0008)...", $time);
        start_time = $time;
        z80.mem_read(16'h0008, read_val);
        elapsed_time = $time - start_time;
        
        $display("[%0t] Z80 Master read completed in %0d ps. Value: %x", $time, elapsed_time, read_val);

        // Assert timing limits
        if (elapsed_time > 450000) begin
            $display("!!! TIMING VIOLATION: Transaction took %0d ps (Expected < 450000 ps) !!!", elapsed_time);
            errors = errors + 1;
        end

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 2...", $time);
        verify_payload(8'hB0);

        // =========================================================
        // TEST 3: Z80 IORQ TO SLAVE
        // Maximum Expected Duration: ~700ns
        // =========================================================
        $display("\n[%0t] === TEST 3: Z80 IORQ to SLAVE during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hC0);

        z80.io_write(16'h2041, 8'h00); 
        z80.io_write(16'h8841, 8'h00); 
        z80.io_write(16'h4040, 8'h00); 
        z80.io_write(16'h8840, 8'h00); 

        $display("[%0t] Z80 forcefully reading Slave MMU IO Port (0x0131)...", $time);
        start_time = $time;
        z80.io_read(16'h0131, read_val);
        elapsed_time = $time - start_time;
        
        $display("[%0t] Z80 Slave IO read completed in %0d ps. Value: %x", $time, elapsed_time, read_val);

        // Assert timing limits
        if (elapsed_time > 700000) begin
            $display("!!! TIMING VIOLATION: Transaction took %0d ps (Expected < 700000 ps) !!!", elapsed_time);
            errors = errors + 1;
        end

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 3...", $time);
        verify_payload(8'hC0);

        // =========================================================
        // TEST 4: Z80 IORQ TO MASTER
        // Maximum Expected Duration: ~700ns
        // =========================================================
        $display("\n[%0t] === TEST 4: Z80 IORQ to MASTER during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hD0);

        z80.io_write(16'h2041, 8'h00); 
        z80.io_write(16'h8841, 8'h00); 
        z80.io_write(16'h4040, 8'h00); 
        z80.io_write(16'h8840, 8'h00); 

        $display("[%0t] Z80 forcefully reading Master MMU IO Port (0x0030)...", $time);
        start_time = $time;
        z80.io_read(16'h0030, read_val);
        elapsed_time = $time - start_time;
        
        $display("[%0t] Z80 Master IO read completed in %0d ps. Value: %x", $time, elapsed_time, read_val);

        // Assert timing limits
        if (elapsed_time > 700000) begin
            $display("!!! TIMING VIOLATION: Transaction took %0d ps (Expected < 700000 ps) !!!", elapsed_time);
            errors = errors + 1;
        end

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 4...", $time);
        verify_payload(8'hD0);

        $display("\n=====================================================");
        if (errors == 0) begin
            $display(" SUCCESS: Arbitration & Timing perfectly verified!");
            $display("=====================================================");
            $finish;
        end else begin
            $display(" FAILURE: Detected %0d errors during arbitration.", errors);
            $display("=====================================================");
            $fatal(1); 
        end
    end

    // --- System Watchdog Timer ---
    initial begin
        #5000000; 
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
endmodule