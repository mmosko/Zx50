`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_bus_tb
 * =====================================================================================
 * Description:
 * This testbench physically simulates a direct card-to-card DMA transfer over the 
 * Universal Shadow Bus. It proves that the Z80 can configure two distinct memory cards 
 * (one as a Master/Source, one as a Slave/Destination), step out of the way, and let 
 * the CPLDs autonomously blast data across the backplane.
 *
 * Test Sequence:
 * 1. Payload Prep: The Z80 loads a 16-byte payload into Card 0's local SRAM.
 * 2. DMA Setup: The Z80 sends bit-packed I/O commands to program Card 1 as a Slave 
 * listening on the Shadow Bus, and Card 0 as a Master driving the Shadow Bus.
 * 3. Autonomous Transfer: The Master CPLD orchestrates the transfer, generating the 
 * strobe and increment signals, while the Slave precisely tracks them.
 * 4. Interrupt & Acknowledge: Upon completion, the Master pulls the shared Z80_INT_n 
 * line low. The Z80 performs an INTACK cycle, and the Master drops its vector (0x40) 
 * onto the bus and clears the interrupt.
 * 5. Verification: The Z80 reads Card 1's memory to ensure the payload arrived safely.
 ***************************************************************************************/

module zx50_shadow_bus_tb;

    // --- 1. System Clocks & Signals ---
    wire mclk, zclk;
    zx50_clock clk_gen (.mclk(mclk), .zclk(zclk));

    reg reset_n;

    // --- 2. Z80 Backplane Buses ---
    wire [15:0] z80_addr;
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n;
    
    wire c0_wait_n, c1_wait_n;
    wire shared_wait_n = c0_wait_n & c1_wait_n; 
    
    wire c0_ieo, c1_ieo;
    wire z80_int_n;

    // --- 3. Standardized Shadow Bus Backplane ---
    wire [15:0] sh_addr; 
    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n;

    // --- 4. Passive Backplane Instantiation ---
    zx50_backplane passive_backplane (
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
        .clk(zclk), .addr(z80_addr), .data(z80_data),
        .mreq_n(z80_mreq_n), .iorq_n(z80_iorq_n), 
        .rd_n(z80_rd_n), .wr_n(z80_wr_n), .m1_n(z80_m1_n),
        .wait_n(shared_wait_n)
    );

    // Card 0 (ID 0x0) - Will be the MASTER (Source)
    zx50_mem_card card0 (
        .mclk(mclk), .reset_n(reset_n), .card_id_sw(4'h0),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(1'b1), .z80_ieo(c0_ieo),
        .z80_wait_n(c0_wait_n), .z80_int_n(z80_int_n),
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // Card 1 (ID 0x1) - Will be the SLAVE (Destination)
    zx50_mem_card card1 (
        .mclk(mclk), .reset_n(reset_n), .card_id_sw(4'h1),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(c0_ieo), .z80_ieo(c1_ieo), // Daisy-chained
        .z80_wait_n(c1_wait_n), .z80_int_n(z80_int_n),
        .sh_addr(sh_addr), .sh_data(sh_data),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n)
    );

    // --- 6. Test Sequence ---
    integer i;
    reg [7:0] read_val, vector;
    integer errors = 0;

    initial begin
        $dumpfile("waves/zx50_shadow_bus.vcd");
        $dumpvars(0, zx50_shadow_bus_tb);

        $display("[%0t] System Power On. Resetting dual cards...", $time);
        reset_n = 1; clk_gen.wait_mclk(5); 
        reset_n = 0; clk_gen.wait_mclk(50); 
        reset_n = 1; 
        clk_gen.wait_mclk(20);

        // ---------------------------------------------------------
        // PREP: Map Memory and Load Payload
        // ---------------------------------------------------------
        // Map Bank 0 to Physical Page 0 on Card 0, and Bank 1 to Physical Page 0 on Card 1
        z80.io_write(16'h0030, 8'h00); // Card 0 (ID 0x0) -> Bank 0 maps to Phys 0x00
        z80.io_write(16'h0131, 8'h00); // Card 1 (ID 0x1) -> Bank 1 maps to Phys 0x00

        $display("[%0t] Seeding Card 0 with 16-byte payload...", $time);
        for (i = 0; i < 16; i = i + 1) begin
            // Write payload to Bank 0 (which hits Card 0, Phys Page 0)
            z80.mem_write(16'h0000 + i, i + 8'hA0);
        end

        // ---------------------------------------------------------
        // PHASE 1: Program DMA Nodes (Bit-Packed I/O Writes)
        // ---------------------------------------------------------
        
        $display("[%0t] Programming Card 1 as SLAVE (Destination)...", $time);
        // SETUP COMMAND (Opcode 0): 0x2041
        // A[15]=0 (Setup), A[14]=0 (Slave), A[13]=1 (Listen to Bus/Write to RAM), A[12:8]=0x00
        // Data = 0x00. Address is 0x00000. Port = 0x41 (Card 1 DMA)
        z80.io_write(16'h2041, 8'h00);

        // ARM COMMAND (Opcode 1): 0x8841
        // A[15]=1 (Arm), A[14:8]=0x08 (Count=16 bytes)
        // Data[7]=0, Data[6:0]=0x00 (Upper Address = 0x00). Port = 0x41
        z80.io_write(16'h8841, 8'h00);

        $display("[%0t] Programming Card 0 as MASTER (Source). Firing DMA...", $time);
        // SETUP COMMAND (Opcode 0): 0x4040
        // A[15]=0 (Setup), A[14]=1 (Master), A[13]=0 (Drive Bus/Read from RAM), A[12:8]=0x00
        // Data = 0x00. Address is 0x00000. Port = 0x40 (Card 0 DMA)
        z80.io_write(16'h4040, 8'h00);

        // ARM COMMAND (Opcode 1): 0x8840
        // A[15]=1 (Arm), A[14:8]=0x08 (Count=16 bytes)
        // Data[7]=0, Data[6:0]=0x00 (Upper Address = 0x00). Port = 0x40
        z80.io_write(16'h8840, 8'h00);

        // ---------------------------------------------------------
        // PHASE 2: Wait for Transfer and Interrupt
        // ---------------------------------------------------------
        $display("[%0t] Z80 yields bus. Waiting for Shadow Bus transfer...", $time);
        // The Z80 BFM just waits here while the CPLDs take over the backplane
        wait(z80_int_n == 1'b0);
        $display("[%0t] Transfer Complete! Z80_INT_N asserted.", $time);
        z80.wait_cycles(2);

        // ---------------------------------------------------------
        // PHASE 3: Interrupt Acknowledge
        // ---------------------------------------------------------
        $display("[%0t] Z80 executing INTACK cycle...", $time);
        z80.intack(vector); // BFM pulls M1 and IORQ low
        
        z80.wait_cycles(2);

        // Verify the Master DMA node correctly identified itself with its interrupt vector
        if (vector !== 8'h40) begin
            $display("!!! INTACK FAILURE: Expected Vector 0x40, got 0x%h", vector);
            errors = errors + 1;
        end else begin
            $display("[%0t] Successfully received Vector 0x40. Interrupt cleared.", $time);
        end
        
        // The INTACK cycle should have automatically reset the int_pending flip-flop in the CPLD
        if (z80_int_n !== 1'b1) begin
            $display("!!! FATAL: z80_int_n did not release after INTACK!");
            $fatal(1);
        end

        // ---------------------------------------------------------
        // PHASE 4: Verification
        // ---------------------------------------------------------
        // The DMA should have copied Physical Page 0 from Card 0 to Physical Page 0 on Card 1.
        // We mapped Bank 1 (0x1000 - 0x1FFF) to Physical Page 0 on Card 1 during Prep.
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