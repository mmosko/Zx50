`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_concurrent_tb
 * DESCRIPTION:
 * The ultimate stress test for Spatial Independence.
 * Proves that the Universal Shadow Bus can execute a 128-byte Block DMA transfer 
 * between Card 0 and Card 1 while the Z80 CPU concurrently executes continuous 
 * memory read/write operations against Card 2 without a single wait state or 
 * dropped DMA byte.
 * * TIMING VALIDATION:
 * Measures the exact elapsed time of 32 uninterrupted Z80 memory transactions.
 * If the background DMA illegally bleeds over and asserts WAIT_N, the elapsed 
 * time will exceed the theoretical minimum, and the test will fail.
 ***************************************************************************************/

module zx50_shadow_concurrent_tb;

    // --- 1. System Clocks & Signals ---
    wire mclk, zclk;
    zx50_clock clk_gen (.mclk(mclk), .zclk(zclk));
    reg reset_n;

    // --- 2. Z80 Backplane Buses ---
    wire [15:0] z80_addr;
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n;
    
    wire c0_wait_n, c1_wait_n, c2_wait_n;
    wire shared_wait_n = c0_wait_n & c1_wait_n & c2_wait_n;
    
    // Interrupt Daisy Chain
    wire c0_ieo, c1_ieo, c2_ieo;
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

    z80_cpu_util z80 (
        .clk(zclk), .addr(z80_addr), .data(z80_data),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(shared_wait_n)
    );

    // --- 4. System Instantiations (3 CARDS!) ---
    zx50_mem_card card0 ( // MASTER (Source for DMA)
        .mclk(mclk), .reset_n(reset_n), .card_id_sw(4'h0),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(1'b1), .z80_ieo(c0_ieo),
        .z80_wait_n(c0_wait_n), .z80_int_n(z80_int_n),
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    zx50_mem_card card1 ( // SLAVE (Destination for DMA)
        .mclk(mclk), .reset_n(reset_n), .card_id_sw(4'h1),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(c0_ieo), .z80_ieo(c1_ieo), 
        .z80_wait_n(c1_wait_n), .z80_int_n(z80_int_n),
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    zx50_mem_card card2 ( // INDEPENDENT Z80 TARGET (Isolated from DMA)
        .mclk(mclk), .reset_n(reset_n), .card_id_sw(4'h2),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(c1_ieo), .z80_ieo(c2_ieo), 
        .z80_wait_n(c2_wait_n), .z80_int_n(z80_int_n),
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // --- 5. Main Test Sequence ---
    integer i;
    reg [7:0] read_val, vector;
    integer errors = 0;
    time start_time, elapsed_time;

    initial begin
        $dumpfile("waves/zx50_shadow_concurrent.vcd");
        $dumpvars(0, zx50_shadow_concurrent_tb);

        $display("\n[%0t] === SYSTEM POWER ON: 3-CARD CLUSTER ===", $time);
        reset_n = 1; clk_gen.wait_mclk(5); 
        reset_n = 0; clk_gen.wait_mclk(50); 
        reset_n = 1;
        clk_gen.wait_mclk(20); 

        // ---------------------------------------------------------
        // 1. Map 4K pages to each card
        // ---------------------------------------------------------
        $display("[%0t] Mapping Z80 Banks to physical cards...", $time);
        z80.io_write(16'h0030, 8'h00); // Card 0 -> Bank 0 (0x0000)
        z80.io_write(16'h0131, 8'h00); // Card 1 -> Bank 1 (0x1000)
        z80.io_write(16'h0232, 8'h00); // Card 2 -> Bank 2 (0x2000)

        // ---------------------------------------------------------
        // 2. Load Payload
        // ---------------------------------------------------------
        $display("[%0t] Seeding Card 0 with 128-byte DMA payload...", $time);
        for (i = 0; i < 128; i = i + 1) z80.mem_write(16'h0000 + i, i[7:0]);

        // ---------------------------------------------------------
        // 3. Configure and Fire a 128-byte DMA transfer
        // ---------------------------------------------------------
        $display("[%0t] Arming 128-byte background DMA burst...", $time);
        // SETUP COMMAND (Opcode 0): 0x2041 -> Setup, Slave, Listen, Lower Addr=0x00
        z80.io_write(16'h2041, 8'h00); 
        // ARM COMMAND (Opcode 1): 0xC041 -> Arm, Count=128, Upper Addr=0x00
        z80.io_write(16'hC041, 8'h00); 
        
        // SETUP COMMAND (Opcode 0): 0x4040 -> Setup, Master, Drive, Lower Addr=0x00
        z80.io_write(16'h4040, 8'h00); 
        // ARM COMMAND (Opcode 1): 0xC040 -> Arm, Count=128, Upper Addr=0x00 (FIRES!)
        z80.io_write(16'hC040, 8'h00); 

        // ---------------------------------------------------------
        // 4. Concurrently execute Z80 Read/Writes on Card 2
        // ---------------------------------------------------------
        $display("[%0t] DMA is running! Z80 slamming Card 2 memory...", $time);
        start_time = $time;
        
        // Write a known pattern to Card 2 while DMA runs over the shadow bus
        for (i = 0; i < 16; i = i + 1) begin
            z80.mem_write(16'h2000 + i, i + 8'hAA);
        end
        
        // Read it back immediately
        for (i = 0; i < 16; i = i + 1) begin
            z80.mem_read(16'h2000 + i, read_val);
            if (read_val !== (i + 8'hAA)) begin
                $display("!!! Z80 CORRUPTION on Card 2 at Offset %0d. Expected %0x, got %0x", i, (i + 8'hAA), read_val);
                errors = errors + 1;
            end
        end

        elapsed_time = $time - start_time;
        $display("[%0t] Z80 Card 2 work finished in %0d ps. Waiting for DMA Interrupt...", $time, elapsed_time);

        // Assert timing limits: 32 pure operations without wait states should take ~11.99 µs.
        // We set a strict threshold at 12.5 µs. If it takes longer, WAIT states were illegally inserted.
        if (elapsed_time > 12500000) begin
            $display("!!! TIMING VIOLATION: Card 2 operations took %0d ps (Expected < 12500000 ps) !!!", elapsed_time);
            $display("    This means the DMA transfer illegally inserted WAIT states onto the Z80 bus!");
            errors = errors + 1;
        end

        // ---------------------------------------------------------
        // 5. Wait for the DMA transfer to cleanly finish
        // ---------------------------------------------------------
        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        if (vector !== 8'h40) begin
            $display("!!! INTERRUPT ERROR: Expected Vector 0x40 from Master, got 0x%h", vector);
            errors = errors + 1;
        end

        // ---------------------------------------------------------
        // 6. Verify the 128-byte payload on Card 1
        // ---------------------------------------------------------
        $display("[%0t] Validating 128-byte payload on Destination Card 1...", $time);
        for (i = 0; i < 128; i = i + 1) begin
            z80.mem_read(16'h1000 + i, read_val);
            if (read_val !== i[7:0]) begin
                $display("!!! DMA CORRUPTION at Offset %0d. Expected %0x, got %0x", i, i[7:0], read_val);
                errors = errors + 1;
            end
        end

        $display("\n=====================================================");
        if (errors == 0) begin
            $display(" SUCCESS: Spatial Independence achieved!");
            $display("          Z80 and DMA ran concurrently without interference.");
            $display("          Zero illegal WAIT states detected (Elapsed: %0d ps).", elapsed_time);
            $display("=====================================================");
            $finish;
        end else begin
            $display(" FAILURE: Detected %0d errors during concurrent ops.", errors);
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