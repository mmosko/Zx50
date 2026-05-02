`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_dma_tb
 * =====================================================================================
 * WHAT IS BEING TESTED:
 * This is an isolated unit test for the `zx50_dma` (Universal Shadow Bus Node).
 * It strictly verifies that the DMA state machine correctly decodes the Z80 24-bit 
 * bit-packed `OUT (C), A` configuration protocol and properly generates a contiguous 
 * physical address, respecting the 12-bit/8-bit counter optimization.
 *
 * TEST SEQUENCE:
 * - Phase 1 (Master Mode): The DMA is programmed to read from local memory and write 
 * to the Shadow Bus. The TB verifies it asserts the bus, cycles through STROBE/INC, 
 * accurately increments the address, and asserts `int_pending`.
 * - Phase 2 (Slave Mode): The DMA is programmed to listen to the Shadow Bus and write 
 * to local memory. The TB takes manual control of the shadow control lines to simulate 
 * an external master, verifying the Slave safely disarms on `sh_done_n`.
 ***************************************************************************************/

module zx50_dma_tb;

    // --- 1. System Clocks ---
    wire mclk, zclk;
    zx50_clock clk_gen (.mclk(mclk), .zclk(zclk));

    // --- 2. System Signals ---
    reg reset_n;

    // --- 3. Z80 Backplane Buses (Driven by BFM) ---
    wire [15:0] z80_addr;
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_rd_n, z80_wr_n, z80_m1_n;
    
    // --- 4. DMA Local Output Buses ---
    // Note: The data bus is no longer routed through the DMA module. It only 
    // manages the address generation and transceiver direction controls.
    wire [19:0] dma_phys_addr;
    wire dma_local_we_n, dma_local_oe_n;

    // --- 5. Shadow Bus Controls (inout) ---
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n;

    // Pull-ups for the open-drain/tristate shadow bus
    assign sh_en_n   = 1'b1;
    assign sh_rw_n   = 1'b1;
    
    // Testbench Override Registers (To simulate a remote Master driving the bus)
    reg tb_sh_drive;
    reg tb_sh_inc_n, tb_sh_stb_n, tb_sh_done_n;
    
    assign sh_inc_n  = tb_sh_drive ? tb_sh_inc_n  : 1'bz;
    assign sh_stb_n  = tb_sh_drive ? tb_sh_stb_n  : 1'bz;
    assign sh_done_n = tb_sh_drive ? tb_sh_done_n : 1'bz;

    // --- 6. Internal Status & Interrupts ---
    wire dma_active, sh_c_dir, dma_dir_to_bus, int_pending;
    reg intack_clear;

    // --- 7. BFM Instantiation ---
    z80_cpu_util z80 (
        .clk(zclk), .addr(z80_addr), .data(z80_data),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(1'b1)
    );

    // --- BRIDGE LOGIC: Centralized Decode Simulation ---
    // We replicate the top-level CPLD routing matrix decoding here so the 
    // optimized DMA module gets the exact boolean flag it expects.
    // Note: This testbench assumes Card ID is 0x0. Base port = 0x40.
    wire dma_io_write = (!z80_iorq_n && !z80_wr_n && (z80_addr[7:0] == 8'h40));

    // --- 8. DUT Instantiation ---
    zx50_dma dut (
        .mclk(mclk), .reset_n(reset_n),
        
        // --- FITTER OPTIMIZED PORTS ---
        .z80_addr_hi(z80_addr[15:8]), 
        .z80_data_in(z80_data), 
        .z80_iorq_n(z80_iorq_n), 
        .dma_io_write(dma_io_write),
        // ------------------------------
        
        .dma_phys_addr(dma_phys_addr), 
        .dma_local_we_n(dma_local_we_n), .dma_local_oe_n(dma_local_oe_n),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), 
        .sh_busy_n(1'b1), // Tied high for the standalone testbench so it never yields
        .dma_active(dma_active), .sh_c_dir(sh_c_dir), .dma_dir_to_bus(dma_dir_to_bus),
        .dma_is_master(dma_is_master), .int_pending(int_pending), .intack_clear(intack_clear)
    );

    // ==========================================
    // HELPER TASK: Program the DMA via Z80 I/O
    // ==========================================
    // Simulates the exact OUT (C), A instruction bit-packing.
    task program_dma_node(
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
            addr_out[7:0]  = 8'h40; // Base Port (Card 0)
            addr_out[15]   = 1'b0;
            addr_out[14]   = is_master;
            addr_out[13]   = to_bus;
            addr_out[12:8] = phys_addr[12:8];
            data_out       = phys_addr[7:0];
            z80.io_write(addr_out, data_out);
            z80.wait_cycles(2);

            // WRITE 2: Opcode 1 (Arms the DMA)
            // A[15]=1, A[14:8]=Count[7:1] | D[7]=Count[0], D[6:0]=PA[19:13]
            addr_out[7:0]  = 8'h40;
            addr_out[15]   = 1'b1;
            addr_out[14:8] = count[7:1];
            data_out[7]    = count[0];
            data_out[6:0]  = phys_addr[19:13];
            z80.io_write(addr_out, data_out);
        end
    endtask

    // ==========================================
    // Test Sequence
    // ==========================================
    initial begin
        $dumpfile("waves/zx50_dma.vcd");
        $dumpvars(0, zx50_dma_tb);
        
        // Setup defaults
        intack_clear = 0;
        tb_sh_drive  = 0;
        tb_sh_inc_n  = 1; tb_sh_stb_n = 1; tb_sh_done_n = 1;

        // Reset
        reset_n = 1;      
        clk_gen.wait_mclk(5); 
        reset_n = 0;  
        clk_gen.wait_mclk(50); 
        reset_n = 1;
        clk_gen.wait_mclk(20);

        // ---------------------------------------------------------
        // PHASE 1: Master Mode Test (Reading Local RAM -> Backplane)
        // ---------------------------------------------------------
        $display("[%0t] --- Phase 1: DMA Master Mode Output Test ---", $time);
        
        // Program as Master, ToBus=0 (Outputting), PA=0x12345, Count=4 bytes
        program_dma_node(1'b1, 1'b0, 20'h12345, 8'h04);
        
        // Wait for state machine to finish blasting the bytes
        wait(int_pending == 1'b1);

        // Because the count was 4 bytes (0, 1, 2, 3), the address should have incremented 4 times.
        if (dma_phys_addr !== 20'h12349) begin
            $display("FATAL: Master did not increment physical address correctly! Expected 12349, Got %0x", dma_phys_addr);
            $fatal(1);
        end
        
        $display("[%0t] Master transfer complete. INT_PENDING asserted.", $time);
        
        // Simulate an INTACK clear from the CPLD Core
        clk_gen.wait_mclk(2);
        intack_clear = 1;
        clk_gen.wait_mclk(2);
        intack_clear = 0;
        
        if (int_pending !== 1'b0) begin
            $display("FATAL: INT_PENDING failed to clear!");
            $fatal(1);
        end

        z80.wait_cycles(5);

        // ---------------------------------------------------------
        // PHASE 2: Slave Mode Test (Writing Backplane -> Local RAM)
        // ---------------------------------------------------------
        $display("[%0t] --- Phase 2: DMA Slave Mode Tracking Test ---", $time);
        
        // Program as Slave, ToBus=1 (Writing Local RAM), PA=0xA8CDE, Count=2 bytes
        program_dma_node(1'b0, 1'b1, 20'hA8CDE, 8'h02);
        
        // Assert testbench control over the shadow bus lines
        tb_sh_drive = 1;
        
        // Byte 1: Strobe and Increment
        clk_gen.wait_mclk(5);
        tb_sh_stb_n = 0; clk_gen.wait_mclk(2); tb_sh_stb_n = 1; // Pulse Strobe
        clk_gen.wait_mclk(2);
        tb_sh_inc_n = 0; clk_gen.wait_mclk(2); tb_sh_inc_n = 1; // Pulse Inc
        
        // Byte 2: Strobe and Done
        clk_gen.wait_mclk(5);
        tb_sh_stb_n = 0; clk_gen.wait_mclk(2); tb_sh_stb_n = 1; // Pulse Strobe
        clk_gen.wait_mclk(2);
        tb_sh_done_n = 0; clk_gen.wait_mclk(2); tb_sh_done_n = 1; // Pulse Done
        
        clk_gen.wait_mclk(5);
        tb_sh_drive = 0; // Release testbench control

        if (dma_active !== 1'b0) begin
            $display("FATAL: Slave failed to disarm after receiving sh_done_n!");
            $fatal(1);
        end

        $display("=====================================================");
        $display(" SUCCESS: DMA Node cleanly operates as Master and Slave.");
        $display("=====================================================");
        $finish;
    end

    // --- System Watchdog Timer ---
    initial begin
        #50000;
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
endmodule