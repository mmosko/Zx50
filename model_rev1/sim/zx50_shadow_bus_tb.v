`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_bus_tb
 * =====================================================================================
 * WHAT IS BEING TESTED:
 * This testbench is the ultimate physical simulation of a direct card-to-card DMA 
 * transfer over the Universal Shadow Bus. It proves that the Z80 can configure two 
 * distinct memory cards, step out of the way, and let the CPLDs autonomously blast 
 * data across the backplane at high speed.
 *
 * TEST SEQUENCE:
 * 1. Payload Prep: Preloads Card 0's ROM with a payload, and uses the Z80 to seed 
 * Card 0's Upper RAM with a second payload.
 * 2. TEST 1 (ROM to RAM): Programs Card 0 DMA to read from Physical Page 0x00000 (ROM)
 * and Card 1 DMA to write to Physical Page 0x01000 (RAM). Fires DMA and verifies.
 * 3. TEST 2 (RAM to RAM): Programs Card 0 DMA to read from Physical Page 0x10000 (RAM)
 * and Card 1 DMA to write to Physical Page 0x12000 (RAM). Fires DMA and verifies.
 * 4. Interrupt & Acknowledge: Upon completion of each transfer, the Master pulls the 
 * shared Z80_INT_n line low. The Z80 performs an INTACK cycle, the Master drops 
 * its vector (0x40) onto the bus, and clears the interrupt.
 ***************************************************************************************/

module zx50_shadow_bus_tb;

    // --- 1. System Clocks & Signals ---
    wire mclk, zclk;
    zx50_clock clk_gen (.run_in(1'b1), .step_n_in(1'b1), .mclk(mclk), .zclk(zclk));
    wire reset_n;

    // --- 2. Z80 Backplane Buses ---
    wire [15:0] z80_addr;
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n;
    
    wire c0_wait_n, c1_wait_n;
    wire shared_wait_n = c0_wait_n & c1_wait_n; 
    wire z80_int_n;

    // --- 3. Standardized Shadow Bus Backplane ---
    wire [15:0] sh_addr; 
    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n;

    // --- 4. Passive Backplane Instantiation ---
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

    // --- 5. System Instantiations ---
    z80_cpu_util z80 (
        .clk(zclk), .reset_n(reset_n),
        .addr(z80_addr), .data(z80_data),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(shared_wait_n)
    );

    // Card 0 (ID 0x0) - Will be the MASTER (Source)
    zx50_mem_card #(.CARD_ID(4'h0)) card0 (
        .mclk(mclk), .zclk(zclk), .reset_n(reset_n),
        .z80_a(z80_addr), .z80_d(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n),
        .wait_n(c0_wait_n), .int_n(z80_int_n),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // Card 1 (ID 0x1) - Will be the SLAVE (Destination)
    zx50_mem_card #(.CARD_ID(4'h1)) card1 (
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

    // --- 6. Test Sequence ---
    integer i;
    reg [7:0] read_val, vector;
    integer errors = 0;

    initial begin
        $dumpfile("waves/zx50_shadow_bus.vcd");
        $dumpvars(0, zx50_shadow_bus_tb);
        
        $display("[%0t] System Power On. Resetting dual cards...", $time);
        z80.boot_sequence();

        // Map Card 0 RAM (Physical Page 0x10 = 0x10000) to Z80 Logical Page 8 (0x8000)
        z80.mmu_map_page(4'h0, 4'h8, 8'h10);
        $display("[%0t] Z80 seeding Card 0 RAM with 16-byte payload at 0x8000...", $time);
        for (i = 0; i < 16; i = i + 1) begin
            z80.mem_write(16'h8000 + i, i + 8'hA0);
        end

        // ---------------------------------------------------------
        // TEST 1: ROM (Card 0) to RAM (Card 1)
        // ---------------------------------------------------------
        $display("\n[%0t] --- TEST 1: DMA ROM (Card 0) to RAM (Card 1) ---", $time);
        // Map Card 1 RAM (Physical Page 0x01 = 0x01000) to Z80 Logical Page 1 (0x1000)
        z80.mmu_map_page(4'h1, 4'h1, 8'h01);
        $display("[%0t] Programming Card 1 as SLAVE (Dest: Phys Page 0x01000)...", $time);
        // Setup: Slave(0), FromBus(1), PA=0x01000. Count=15 (transfers 16 bytes).
        program_dma_node(4'h1, 1'b0, 1'b1, 20'h01000, 8'h0F);
        
        $display("[%0t] Programming Card 0 as MASTER (Source: ROM Phys Page 0x00000). Firing DMA...", $time);
        // Setup: Master(1), ToBus(0), PA=0x00000. Count=15.
        program_dma_node(4'h0, 1'b1, 1'b0, 20'h00000, 8'h0F);

        $display("[%0t] Z80 yields bus. Waiting for Shadow Bus transfer...", $time);
        wait(z80_int_n == 1'b0);
        $display("[%0t] ROM->RAM Transfer Complete! Z80_INT_N asserted.", $time);
        z80.wait_cycles(2);

        $display("[%0t] Z80 executing INTACK cycle...", $time);
        z80.intack(vector); 
        z80.wait_cycles(2);
        
        if (vector !== 8'h40) begin
            $display("!!! INTACK FAILURE: Expected Vector 0x40, got 0x%h", vector);
            errors = errors + 1;
        end else begin
            $display("[%0t] Successfully received Vector 0x40. Interrupt cleared.", $time);
        end

        $display("[%0t] Z80 reading Card 1 memory to verify ROM->RAM payload...", $time);
        for (i = 0; i < 16; i = i + 1) begin
            z80.mem_read(16'h1000 + i, read_val);
            begin : verify_hash
                reg [19:0] src_addr;
                reg [7:0] expected_val;
                
                // The DMA copied data starting from 0x007F8
                src_addr = 20'h00000 + i; 
                
                // Back-door read directly from the ROM model's internal memory array!
                expected_val = card0.rom.memory_array[src_addr];
                
                if (read_val !== expected_val) begin
                    $display("!!! DATA CORRUPTION at Offset %0d. Expected %0x, got %0x", i, expected_val, read_val);
                    errors = errors + 1;
                end
            end
        end
        if (errors == 0) $display("  > ROM to RAM Transfer OK!");
        
        // ---------------------------------------------------------
        // TEST 2: RAM (Card 0) to RAM (Card 1)
        // ---------------------------------------------------------
        $display("\n[%0t] --- TEST 2: DMA RAM (Card 0) to RAM (Card 1) ---", $time);
        // Map Card 1 RAM (Physical Page 0x12 = 0x12000) to Z80 Logical Page 9 (0x9000)
        z80.mmu_map_page(4'h1, 4'h9, 8'h12);
        $display("[%0t] Programming Card 1 as SLAVE (Dest: Phys Page 0x12000)...", $time);
        program_dma_node(4'h1, 1'b0, 1'b1, 20'h12000, 8'h0F);
        
        $display("[%0t] Programming Card 0 as MASTER (Source: RAM Phys Page 0x10000). Firing DMA...", $time);
        program_dma_node(4'h0, 1'b1, 1'b0, 20'h10000, 8'h0F);
        
        $display("[%0t] Z80 yields bus. Waiting for Shadow Bus transfer...", $time);
        wait(z80_int_n == 1'b0);
        $display("[%0t] RAM->RAM Transfer Complete! Z80_INT_N asserted.", $time);
        z80.wait_cycles(2);

        $display("[%0t] Z80 executing INTACK cycle...", $time);
        z80.intack(vector); 
        z80.wait_cycles(2);
        
        if (vector !== 8'h40) begin
            $display("!!! INTACK FAILURE: Expected Vector 0x40, got 0x%h", vector);
            errors = errors + 1;
        end else begin
            $display("[%0t] Successfully received Vector 0x40. Interrupt cleared.", $time);
        end

        $display("[%0t] Z80 reading Card 1 memory to verify RAM->RAM payload...", $time);
        for (i = 0; i < 16; i = i + 1) begin
            z80.mem_read(16'h9000 + i, read_val);
            if (read_val !== (i + 8'hA0)) begin
                $display("!!! DATA CORRUPTION at Offset %0d. Expected %0x, got %0x", i, (i + 8'hA0), read_val);
                errors = errors + 1;
            end
        end
        if (errors == 0) $display("  > RAM to RAM Transfer OK!");

        // ---------------------------------------------------------
        // Verification Complete
        // ---------------------------------------------------------
        $display("\n=====================================================");
        if (errors == 0) begin
            $display(" SUCCESS: Universal Shadow Bus perfectly transferred data!");
            $display("=====================================================");
            $finish;
        end else begin
            $display(" FAILURE: Detected %0d errors during verification.", errors);
            $display("=====================================================");
            $fatal(1); 
        end
    end

    // --- System Watchdog Timer ---
    initial begin
        #500000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
endmodule