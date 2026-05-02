`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_concurrent_tb
 * =====================================================================================
 * WHAT IS BEING TESTED:
 * The ultimate stress test for Spatial Independence on the Universal Shadow Bus.
 * It proves that the backplane can execute a massive 128-byte Block DMA transfer 
 * between Card 0 and Card 1 over the Shadow Bus, while the Z80 CPU concurrently 
 * executes continuous memory read/write operations against Card 2 over the Local Bus.
 *
 * ARCHITECTURAL VALIDATION:
 * - Isolation: Proves the CPLD routing matrices correctly isolate the shared Local 
 * Bus from the Shadow Bus when cards are acting as DMA nodes.
 * - Non-Interference: Proves that Card 2's Z80 transceivers remain open and 
 * responsive to the CPU while the backplane is flooded with DMA traffic.
 *
 * TIMING VALIDATION (THE TRUE STRESS TEST):
 * Measures the exact elapsed time of 32 uninterrupted Z80 memory transactions 
 * executed while the DMA burst is active. If the background DMA illegally bleeds 
 * over and forces Card 2 to assert `WAIT_N`, the Z80 state machine will stall.
 * The elapsed time will exceed the theoretical minimum limit, and the test will fail.
 ***************************************************************************************/

module zx50_shadow_concurrent_tb;

    // --- 1. System Clocks & Signals ---
    wire mclk, zclk;
    zx50_clock clk_gen (.run_in(1'b1), .step_n_in(1'b1), .mclk(mclk), .zclk(zclk));
    wire reset_n;

    // --- 2. Z80 Backplane Buses ---
    wire [15:0] z80_addr;
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n;
    
    // Wired-AND Wait states from all 3 cards
    wire c0_wait_n, c1_wait_n, c2_wait_n;
    wire shared_wait_n = c0_wait_n & c1_wait_n & c2_wait_n; 
    
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

    // --- 4. System Instantiations (3 CARDS!) ---
    
    z80_cpu_util z80 (
        .clk(zclk), .reset_n(reset_n),
        .addr(z80_addr), .data(z80_data),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(shared_wait_n)
    );

    zx50_mem_card #(.CARD_ID(4'h0)) card0 ( // MASTER (Source for DMA)
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_addr), .z80_d(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), 
        .wait_n(c0_wait_n), .int_n(z80_int_n),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    zx50_mem_card #(.CARD_ID(4'h1)) card1 ( // SLAVE (Destination for DMA)
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_addr), .z80_d(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n),  
        .wait_n(c1_wait_n), .int_n(z80_int_n),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    zx50_mem_card #(.CARD_ID(4'h2)) card2 ( // INDEPENDENT Z80 TARGET
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_addr), .z80_d(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n),  
        .wait_n(c2_wait_n), .int_n(z80_int_n),
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
            // WRITE 1: Opcode 0
            // A[15]=0, A[14]=Master, A[13]=Dir, A[12:8]=PA[12:8] | D[7:0]=PA[7:0]
            addr_out[7:0]  = 8'h40 | target_card; // Base Port
            addr_out[15]   = 1'b0;
            addr_out[14]   = is_master;
            addr_out[13]   = to_bus;
            addr_out[12:8] = phys_addr[12:8];
            data_out       = phys_addr[7:0];
            z80.io_write(addr_out, data_out);
            z80.wait_cycles(2);
            
            // WRITE 2: Opcode 1 (Arms the DMA)
            // A[15]=1, A[14:8]=Count[7:1] | D[7]=Count[0], D[6:0]=PA[19:13]
            addr_out[7:0]  = 8'h40 | target_card;
            addr_out[15]   = 1'b1;
            addr_out[14:8] = count[7:1];
            data_out[7]    = count[0];
            data_out[6:0]  = phys_addr[19:13];
            z80.io_write(addr_out, data_out);
        end
    endtask

    // --- 5. Main Test Sequence ---
    integer i;
    reg [7:0] read_val, vector;
    integer errors = 0;
    time start_time, elapsed_time;

    initial begin
        $dumpfile("waves/zx50_shadow_concurrent.vcd");
        $dumpvars(0, zx50_shadow_concurrent_tb);
        
        $display("\n[%0t] === SYSTEM POWER ON: 3-CARD CLUSTER ===", $time);
        z80.boot_sequence(); 

        // ---------------------------------------------------------
        // 1. Map 4K pages to each card
        // ---------------------------------------------------------
        $display("[%0t] Mapping Z80 Banks to physical cards...", $time);
        z80.mmu_map_page(4'h0, 4'h0, 8'h00); // Card 0 -> Logical Bank 0 (0x0000)
        z80.mmu_map_page(4'h1, 4'h1, 8'h01); // Card 1 -> Logical Bank 1 (0x1000)
        z80.mmu_map_page(4'h2, 4'h2, 8'h02); // Card 2 -> Logical Bank 2 (0x2000)

        // ---------------------------------------------------------
        // 2. Load Payload
        // ---------------------------------------------------------
        $display("[%0t] Seeding Card 0 with 128-byte DMA payload...", $time);
        for (i = 0; i < 128; i = i + 1) z80.mem_write(16'h0000 + i, i[7:0]);
        
        // ---------------------------------------------------------
        // 3. Configure and Fire a 128-byte DMA transfer
        // ---------------------------------------------------------
        $display("[%0t] Arming 128-byte background DMA burst...", $time);
        // Setup Card 1 as Slave: FromBus(1), PA=0x01000. Count=127 (transfers 128 bytes).
        program_dma_node(4'h1, 1'b0, 1'b1, 20'h01000, 8'h7F);
        
        // Setup Card 0 as Master: ToBus(0), PA=0x00000. Count=127. (FIRES!)
        program_dma_node(4'h0, 1'b1, 1'b0, 20'h00000, 8'h7F);
        
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