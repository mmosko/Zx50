`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_bus_tb
 * =====================================================================================
 * Description:
 * This testbench physically simulates a direct card-to-card DMA transfer over the 
 * Universal Shadow Bus.
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
        // PREP: Map Memory and Load Payloads
        // ---------------------------------------------------------
        $display("[%0t] Preloading Card 0 ROM with 16-byte payload...", $time);
        for (i = 0; i < 16; i = i + 1) begin
            card0.rom.memory_array[i] = i + 8'hC0;
        end

        // Map Card 0 RAM (Physical Page 0x10 = 0x10000) to Z80 Logical Page 8 (0x8000)
        z80.io_write(16'h0830, 8'h10);
        
        $display("[%0t] Z80 seeding Card 0 RAM with 16-byte payload at 0x8000...", $time);
        for (i = 0; i < 16; i = i + 1) begin
            z80.mem_write(16'h8000 + i, i + 8'hA0);
        end

        // ---------------------------------------------------------
        // TEST 1: ROM (Card 0) to RAM (Card 1)
        // ---------------------------------------------------------
        $display("\n[%0t] --- TEST 1: DMA ROM (Card 0) to RAM (Card 1) ---", $time);

        // Map Card 1 RAM (Physical Page 0x01 = 0x01000) to Z80 Logical Page 1 (0x1000)
        z80.io_write(16'h0131, 8'h01);

        $display("[%0t] Programming Card 1 as SLAVE (Dest: Phys Page 0x01000)...", $time);
        // Setup: Slave(0), FromBus(1), PA[12:0]=0x1000. Operand = 15'b0_1_1000000000000 = 15'h3000.
        z80.io_write(16'h3041, 8'h00); 
        // Arm: Count=16 (0x10), PA[19:13]=0. Operand = 15'h0800
        z80.io_write(16'h8841, 8'h00);

        $display("[%0t] Programming Card 0 as MASTER (Source: ROM Phys Page 0x00000). Firing DMA...", $time);
        // Setup: Master(1), ToBus(0), PA[12:0]=0. Operand = 15'h4000
        z80.io_write(16'h4040, 8'h00); 
        // Arm: Count=16 (0x10), PA[19:13]=0. Operand = 15'h0800
        z80.io_write(16'h8840, 8'h00);

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
            if (read_val !== (i + 8'hC0)) begin
                $display("!!! DATA CORRUPTION at Offset %0d. Expected %0x, got %0x", i, (i + 8'hC0), read_val);
                errors = errors + 1;
            end
        end
        if (errors == 0) $display("  > ROM to RAM Transfer OK!");

        // ---------------------------------------------------------
        // TEST 2: RAM (Card 0) to RAM (Card 1)
        // ---------------------------------------------------------
        $display("\n[%0t] --- TEST 2: DMA RAM (Card 0) to RAM (Card 1) ---", $time);

        // Map Card 1 RAM (Physical Page 0x12 = 0x12000) to Z80 Logical Page 9 (0x9000)
        z80.io_write(16'h0931, 8'h12);

        $display("[%0t] Programming Card 1 as SLAVE (Dest: Phys Page 0x12000)...", $time);
        // PA=0x12000. PA[12:0]=0. PA[19:13]=0x09.
        // Setup: Slave(0), FromBus(1), PA[12:0]=0. Operand = 15'h2000
        z80.io_write(16'h2041, 8'h00);
        // Arm: Count=16 (0x10), PA[19:13]=0x09. Operand = 15'h0809
        z80.io_write(16'h8841, 8'h09); 

        $display("[%0t] Programming Card 0 as MASTER (Source: RAM Phys Page 0x10000). Firing DMA...", $time);
        // PA=0x10000. PA[12:0]=0. PA[19:13]=0x08.
        // Setup: Master(1), ToBus(0), PA[12:0]=0. Operand = 15'h4000
        z80.io_write(16'h4040, 8'h00);
        // Arm: Count=16 (0x10), PA[19:13]=0x08. Operand = 15'h0808
        z80.io_write(16'h8840, 8'h08);

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