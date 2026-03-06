`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_bus_tb
 * ... (Keep your excellent header block here) ...
 ***************************************************************************************/

module zx50_shadow_bus_tb;

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
    wire [15:0] shd_addr; 
    wire [7:0]  shd_data;
    wire shd_en_n, shd_rw_n, shd_inc_n, shd_stb_n, shd_done_n, shd_busy_n;

    // --- NEW: Passive Backplane Instantiation ---
    zx50_backplane passive_backplane (
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), 
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n), 
        .z80_wait_n(z80_wait_n), .z80_int_n(z80_int_n),
        
        .shd_addr(shd_addr), .shd_data(shd_data),
        .shd_en_n(shd_en_n), .shd_rw_n(shd_rw_n), .shd_inc_n(shd_inc_n), 
        .shd_stb_n(shd_stb_n), .shd_done_n(shd_done_n), .shd_busy_n(shd_busy_n)
    );

    // --- 4. System Instantiations ---
    z80_cpu_util z80 (
        .clk(zclk), .addr(z80_addr), .data(z80_data),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(shared_wait_n)
    );

    // Card 0 (ID 0x0) - Will be the MASTER (Source)
    zx50_mem_card card0 (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(4'h0),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(1'b1), .z80_ieo(c0_ieo),
        .z80_wait_n(c0_wait_n), .z80_int_n(z80_int_n),
        .shd_addr(shd_addr), .shd_data(shd_data),
        .shd_en_n(shd_en_n), .shd_rw_n(shd_rw_n), .shd_inc_n(shd_inc_n), 
        .shd_stb_n(shd_stb_n), .shd_done_n(shd_done_n), .shd_busy_n(shd_busy_n)
    );

    // Card 1 (ID 0x1) - Will be the SLAVE (Destination)
    zx50_mem_card card1 (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(4'h1),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(c0_ieo), .z80_ieo(c1_ieo), // Daisy-chained
        .z80_wait_n(c1_wait_n), .z80_int_n(z80_int_n),
        .shd_addr(shd_addr), .shd_data(shd_data),
        .shd_en_n(shd_en_n), .shd_rw_n(shd_rw_n), .shd_inc_n(shd_inc_n), 
        .shd_stb_n(shd_stb_n), .shd_done_n(shd_done_n), .shd_busy_n(shd_busy_n)
    );

    // --- 5. Test Sequence ---
    // (The exact same test sequence as before goes here...)
    integer i;
    reg [7:0] read_val, vector;
    integer errors = 0;

    initial begin
        $dumpfile("waves/zx50_shadow_bus.vcd");
        $dumpvars(0, zx50_shadow_bus_tb);
        
        boot_en_n = 1; 

        $display("[%0t] System Power On. Resetting dual cards...", $time);
        reset_n = 1; clk_gen.wait_mclk(5); 
        reset_n = 0; clk_gen.wait_mclk(50); 
        reset_n = 1; 
        clk_gen.wait_mclk(20); 

        // ---------------------------------------------------------
        // PREP: Map Memory and Load Payload
        // ---------------------------------------------------------
        z80.io_write(16'h0030, 8'h00);
        z80.io_write(16'h0131, 8'h00);

        $display("[%0t] Seeding Card 0 with 16-byte payload...", $time);
        for (i = 0; i < 16; i = i + 1) begin
            z80.mem_write(16'h0000 + i, i + 8'hA0); 
        end

        // ---------------------------------------------------------
        // PHASE 1: Program DMA Nodes
        // ---------------------------------------------------------
        $display("[%0t] Programming Card 1 as SLAVE (Destination)...", $time);
        z80.io_write(16'h2041, 8'h00);
        z80.io_write(16'h8841, 8'h00);

        $display("[%0t] Programming Card 0 as MASTER (Source). Firing DMA...", $time);
        z80.io_write(16'h4040, 8'h00);
        z80.io_write(16'h8840, 8'h00);

        // ---------------------------------------------------------
        // PHASE 2: Wait for Transfer and Interrupt
        // ---------------------------------------------------------
        $display("[%0t] Z80 yields bus. Waiting for Shadow Bus transfer...", $time);
        
        wait(z80_int_n == 1'b0);
        $display("[%0t] Transfer Complete! Z80_INT_N asserted.", $time);
        z80.wait_cycles(2);

        // ---------------------------------------------------------
        // PHASE 3: Interrupt Acknowledge
        // ---------------------------------------------------------
        $display("[%0t] Z80 executing INTACK cycle...", $time);
        z80.intack(vector);
        
        z80.wait_cycles(2);

        if (vector !== 8'h40) begin
            $display("!!! INTACK FAILURE: Expected Vector 0x40, got 0x%h", vector);
            errors = errors + 1;
        end else begin
            $display("[%0t] Successfully received Vector 0x40. Interrupt cleared.", $time);
        end
        
        if (z80_int_n !== 1'b1) begin
            $display("!!! FATAL: z80_int_n did not release after INTACK!");
            $fatal(1);
        end

        // ---------------------------------------------------------
        // PHASE 4: Verification
        // ---------------------------------------------------------
        $display("[%0t] Z80 reading Card 1 memory to verify DMA payload...", $time);
        for (i = 0; i < 16; i = i + 1) begin
            z80.mem_read(16'h1000 + i, read_val); 
            
            if (read_val !== (i + 8'hA0)) begin
                $display("!!! DATA CORRUPTION at Offset %0d. Expected %0x, got %0x", i, (i + 8'hA0), read_val);
                errors = errors + 1;
            end
        end

        $display("=====================================================");
        if (errors == 0) begin
            $display(" SUCCESS: Universal Shadow Bus perfectly transferred data!");
            $display("=====================================================");
            $finish;
        end else begin
            $display(" FAILURE: Detected %0d errors during verification.", errors);
            $display("=====================================================");
            $fatal(1); // Force a non-zero exit code so Make aborts!
        end
    end

    // --- System Watchdog Timer ---
    initial begin
        #500000; 
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
endmodule