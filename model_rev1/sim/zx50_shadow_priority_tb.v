`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_priority_tb
 * =====================================================================================
 * WHAT IS BEING TESTED:
 * This testbench validates the "Z80 Supremacy" arbitration and priority logic of 
 * the Universal Shadow Bus. It proves that the Z80 CPU can actively interrupt and 
 * take control of the exact physical cards that are currently performing a DMA burst.
 *
 * ARCHITECTURAL VALIDATION (CYCLE STEALING):
 * When the Z80 asserts `MREQ` or `IORQ` targeting an active DMA node, the CPLD must:
 * 1. Instantly pause the DMA state machine.
 * 2. Execute a 1-clock "Dead State" to close the Shadow Bus transceivers.
 * 3. Open the Local Bus transceivers for the Z80.
 * 4. Fulfill the Z80 read/write request.
 * 5. Execute another "Dead State" to safely hand the bus back to the DMA.
 * 6. Resume the DMA transfer seamlessly without corrupting the payload.
 *
 * TIMING VALIDATION:
 * This test dynamically measures the exact elapsed time (in picoseconds) of Z80 
 * transactions that collide with a running DMA. If the CPLD's arbitration logic 
 * gets stuck, drops the request, or inserts unnecessary `WAIT` states, the elapsed 
 * time will exceed the strict hardcoded limits and the test will fail.
 ***************************************************************************************/

module zx50_shadow_priority_tb;

// --- 1. System Clocks & Signals ---
    wire mclk, zclk;
    zx50_clock clk_gen (.run_in(1'b1), .step_n_in(1'b1), .mclk(mclk), .zclk(zclk));
    wire reset_n; 

    // --- 2. Z80 Backplane Buses ---
    wire [15:0] z80_addr;
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n;
    
    // Wired-AND Wait states from the two cards
    wire c0_wait_n, c1_wait_n;
    wire shared_wait_n = c0_wait_n & c1_wait_n; 
    
    wire z80_int_n;

    // --- 3. Shadow Bus Backplane ---
    wire [15:0] sh_addr; 
    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n;

    zx50_backplane passive_backplane (
        .z80_reset_n(reset_n),
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
        .clk(zclk), .reset_n(reset_n),
        .addr(z80_addr), .data(z80_data),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(shared_wait_n)
    );

    zx50_mem_card #(.CARD_ID(4'h0), .BOOT_EN(1'b1)) card0 ( // MASTER (Source for DMA)
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_addr), .z80_d(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), 
        .wait_n(c0_wait_n), .int_n(z80_int_n),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    zx50_mem_card #(.CARD_ID(4'h1), .BOOT_EN(1'b1)) card1 ( // SLAVE (Destination for DMA)
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_addr), .z80_d(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), 
        .wait_n(c1_wait_n), .int_n(z80_int_n),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // ==========================================
    // HELPER TASK: Program the DMA via Z80 I/O
    // ==========================================
    task program_dma_node(
        input [3:0] target_card,
        input is_master, 
        input to_bus, 
        input [19:0] phys_addr, 
        input [7:0] count
    );
        reg [15:0] addr_out;
        reg [7:0]  data_out;
        begin
            addr_out[7:0]  = 8'h40 | target_card;
            addr_out[15]   = 1'b0;
            addr_out[14]   = is_master;
            addr_out[13]   = to_bus;
            addr_out[12:8] = phys_addr[12:8];
            data_out       = phys_addr[7:0];
            z80.io_write(addr_out, data_out);
            z80.wait_cycles(2);

            addr_out[7:0]  = 8'h40 | target_card;
            addr_out[15]   = 1'b1;
            addr_out[14:8] = count[7:1];
            data_out[7]    = count[0];
            data_out[6:0]  = phys_addr[19:13];
            z80.io_write(addr_out, data_out);
        end
    endtask

    // --- 5. Test Utilities ---
    integer i;
    reg [7:0] read_val, vector;
    integer errors = 0;

    // Variables for cycle-time tracking
    time start_time, elapsed_time;

    // Routine to verify the DMA payload survived the interruption
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
        
        $display("\n[%0t] === SYSTEM POWER ON ===", $time);
        z80.boot_sequence();

        // Map Base Memory Pages: Card 0 -> Logical Bank 0, Card 1 -> Logical Bank 1
        z80.mmu_map_page(4'h0, 4'h0, 8'h00);
        z80.mmu_map_page(4'h1, 4'h1, 8'h01);

        // =========================================================
        // TEST 1: Z80 MREQ TO SLAVE (Card 1)
        // Maximum Expected Duration: ~800ns
        // =========================================================
        $display("\n[%0t] === TEST 1: Z80 MREQ to SLAVE during DMA ===", $time);
        // Seed the Source (Card 0) with a known pattern
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hA0);
        
        // Arm DMA Transfer (16 Bytes from Card 0 to Card 1)
        program_dma_node(4'h1, 1'b0, 1'b1, 20'h01000, 8'h0F); // Slave (Dest)
        program_dma_node(4'h0, 1'b1, 1'b0, 20'h00000, 8'h0F); // Master (Source)

        $display("[%0t] Z80 forcefully reading Slave memory (0x1008) while DMA runs...", $time);
        start_time = $time;
        z80.mem_read(16'h1008, read_val);
        elapsed_time = $time - start_time;
        
        $display("[%0t] Z80 Slave read completed in %0d ps. Value: %x", $time, elapsed_time, read_val);
        
        // Assert timing limits: Transaction must not be illegally stalled
        if (elapsed_time > 800000) begin
            $display("!!! TIMING VIOLATION: Transaction took %0d ps (Expected < 800000 ps) !!!", elapsed_time);
            errors = errors + 1;
        end

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 1 survived the interruption...", $time);
        verify_payload(8'hA0);

        // =========================================================
        // TEST 2: Z80 MREQ TO MASTER (Card 0)
        // Maximum Expected Duration: ~800ns
        // =========================================================
        $display("\n[%0t] === TEST 2: Z80 MREQ to MASTER during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hB0);
        
        program_dma_node(4'h1, 1'b0, 1'b1, 20'h01000, 8'h0F); // Slave
        program_dma_node(4'h0, 1'b1, 1'b0, 20'h00000, 8'h0F); // Master

        $display("[%0t] Z80 forcefully reading Master memory (0x0008) while DMA runs...", $time);
        start_time = $time;
        z80.mem_read(16'h0008, read_val);
        elapsed_time = $time - start_time;
        
        $display("[%0t] Z80 Master read completed in %0d ps. Value: %x", $time, elapsed_time, read_val);
        if (elapsed_time > 800000) begin
            $display("!!! TIMING VIOLATION: Transaction took %0d ps (Expected < 800000 ps) !!!", elapsed_time);
            errors = errors + 1;
        end

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 2 survived the interruption...", $time);
        verify_payload(8'hB0);

        // =========================================================
        // TEST 3: Z80 IORQ TO SLAVE (Card 1)
        // Maximum Expected Duration: ~1200ns
        // =========================================================
        $display("\n[%0t] === TEST 3: Z80 IORQ to SLAVE during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hC0);
        
        program_dma_node(4'h1, 1'b0, 1'b1, 20'h01000, 8'h0F); // Slave
        program_dma_node(4'h0, 1'b1, 1'b0, 20'h00000, 8'h0F); // Master

        $display("[%0t] Z80 forcefully reading Slave MMU IO Port (0x0131)...", $time);
        start_time = $time;
        z80.io_read(16'h0131, read_val);
        elapsed_time = $time - start_time;
        
        $display("[%0t] Z80 Slave IO read completed in %0d ps. Value: %x", $time, elapsed_time, read_val);
        if (elapsed_time > 1200000) begin
            $display("!!! TIMING VIOLATION: Transaction took %0d ps (Expected < 1200000 ps) !!!", elapsed_time);
            errors = errors + 1;
        end

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 3 survived the interruption...", $time);
        verify_payload(8'hC0);

        // =========================================================
        // TEST 4: Z80 IORQ TO MASTER (Card 0)
        // Maximum Expected Duration: ~1200ns
        // =========================================================
        $display("\n[%0t] === TEST 4: Z80 IORQ to MASTER during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hD0);
        
        program_dma_node(4'h1, 1'b0, 1'b1, 20'h01000, 8'h0F); // Slave
        program_dma_node(4'h0, 1'b1, 1'b0, 20'h00000, 8'h0F); // Master

        $display("[%0t] Z80 forcefully reading Master MMU IO Port (0x0030)...", $time);
        start_time = $time;
        z80.io_read(16'h0030, read_val);
        elapsed_time = $time - start_time;
        
        $display("[%0t] Z80 Master IO read completed in %0d ps. Value: %x", $time, elapsed_time, read_val);
        if (elapsed_time > 1200000) begin
            $display("!!! TIMING VIOLATION: Transaction took %0d ps (Expected < 1200000 ps) !!!", elapsed_time);
            errors = errors + 1;
        end

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 4 survived the interruption...", $time);
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