`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_shadow_priority_tb
 * DESCRIPTION:
 * Validates the bus arbitration and priority logic of the Universal Shadow Bus.
 * The Z80 is the supreme bus master. If a background DMA transfer is actively 
 * blasting data across the shadow bus, and the Z80 suddenly initiates an MREQ 
 * or IORQ cycle targeting one of the active DMA nodes, the targeted node must 
 * safely pause the DMA burst, service the Z80, and then seamlessly resume.
 *
 * TESTS PERFORMED:
 * 1. Z80 MREQ to SLAVE (Destination Card) during active DMA.
 * 2. Z80 MREQ to MASTER (Source Card) during active DMA.
 * 3. Z80 IORQ to SLAVE during active DMA.
 * 4. Z80 IORQ to MASTER during active DMA.
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
    wire [15:0] shd_addr; 
    wire [7:0]  shd_data;
    wire shd_en_n, shd_rw_n, shd_inc_n, shd_stb_n, shd_done_n, shd_busy_n;

    zx50_backplane passive_backplane (
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), 
        .z80_rd_n(z80_rd_n), .z80_wr_n(z80_wr_n), .z80_m1_n(z80_m1_n), 
        .z80_wait_n(shared_wait_n), .z80_int_n(z80_int_n),
        
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

    // Card 0 (ID 0x0) - MASTER (Source)
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

    // Card 1 (ID 0x1) - SLAVE (Destination)
    zx50_mem_card card1 (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(4'h1),
        .z80_addr(z80_addr), .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n), .z80_iei(c0_ieo), .z80_ieo(c1_ieo), 
        .z80_wait_n(c1_wait_n), .z80_int_n(z80_int_n),
        .shd_addr(shd_addr), .shd_data(shd_data),
        .shd_en_n(shd_en_n), .shd_rw_n(shd_rw_n), .shd_inc_n(shd_inc_n), 
        .shd_stb_n(shd_stb_n), .shd_done_n(shd_done_n), .shd_busy_n(shd_busy_n)
    );

    // --- 5. Test Utilities ---
    integer i;
    reg [7:0] read_val, vector;
    integer errors = 0;

    // A helper task to verify a full 16-byte payload after a DMA burst
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

        // Map Z80 Bank 0 (0x0000) to Card 0, Phys Page 0
        z80.io_write(16'h0030, 8'h00);
        // Map Z80 Bank 1 (0x1000) to Card 1, Phys Page 0
        z80.io_write(16'h0131, 8'h00);

        // =========================================================
        // TEST 1: Z80 MREQ TO SLAVE
        // =========================================================
        $display("\n[%0t] === TEST 1: Z80 MREQ to SLAVE during DMA ===", $time);
        // Seed Card 0 with 0xA0
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hA0);

        z80.io_write(16'h2041, 8'h00); // Slave Listen
        z80.io_write(16'h8841, 8'h00); // Slave Count=16, Arm
        z80.io_write(16'h4040, 8'h00); // Master Drive
        z80.io_write(16'h8840, 8'h00); // Master Count=16, Arm (DMA FIRES!)

        // BOOM: Immediate collision! Z80 tries to read Card 1 memory right as it's being written.
        $display("[%0t] Z80 forcefully reading Slave memory (0x1008)...", $time);
        z80.mem_read(16'h1008, read_val);
        $display("[%0t] Z80 Slave read completed. Value: %x", $time, read_val);

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 1...", $time);
        verify_payload(8'hA0);

        // =========================================================
        // TEST 2: Z80 MREQ TO MASTER
        // =========================================================
        $display("\n[%0t] === TEST 2: Z80 MREQ to MASTER during DMA ===", $time);
        // Re-seed Card 0 with 0xB0 to guarantee fresh transfer
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hB0);

        z80.io_write(16'h2041, 8'h00); 
        z80.io_write(16'h8841, 8'h00); 
        z80.io_write(16'h4040, 8'h00); 
        z80.io_write(16'h8840, 8'h00); // DMA FIRES!

        $display("[%0t] Z80 forcefully reading Master memory (0x0008)...", $time);
        z80.mem_read(16'h0008, read_val);
        $display("[%0t] Z80 Master read completed. Value: %x", $time, read_val);

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 2...", $time);
        verify_payload(8'hB0);

        // =========================================================
        // TEST 3: Z80 IORQ TO SLAVE
        // =========================================================
        $display("\n[%0t] === TEST 3: Z80 IORQ to SLAVE during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hC0);

        z80.io_write(16'h2041, 8'h00); 
        z80.io_write(16'h8841, 8'h00); 
        z80.io_write(16'h4040, 8'h00); 
        z80.io_write(16'h8840, 8'h00); // DMA FIRES!

        $display("[%0t] Z80 forcefully reading Slave MMU IO Port (0x0131)...", $time);
        z80.io_read(16'h0131, read_val);
        $display("[%0t] Z80 Slave IO read completed. Value: %x", $time, read_val);

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 3...", $time);
        verify_payload(8'hC0);

        // =========================================================
        // TEST 4: Z80 IORQ TO MASTER
        // =========================================================
        $display("\n[%0t] === TEST 4: Z80 IORQ to MASTER during DMA ===", $time);
        for (i = 0; i < 16; i = i + 1) z80.mem_write(16'h0000 + i, i + 8'hD0);

        z80.io_write(16'h2041, 8'h00); 
        z80.io_write(16'h8841, 8'h00); 
        z80.io_write(16'h4040, 8'h00); 
        z80.io_write(16'h8840, 8'h00); // DMA FIRES!

        $display("[%0t] Z80 forcefully reading Master MMU IO Port (0x0030)...", $time);
        z80.io_read(16'h0030, read_val);
        $display("[%0t] Z80 Master IO read completed. Value: %x", $time, read_val);

        wait(z80_int_n == 1'b0);
        z80.wait_cycles(2); z80.intack(vector); z80.wait_cycles(2);
        
        $display("[%0t] Verifying Payload 4...", $time);
        verify_payload(8'hD0);

        $display("\n=====================================================");
        if (errors == 0) begin
            $display(" SUCCESS: Arbitration perfectly deferred DMA bursts!");
        end else begin
            $display(" FAILURE: Detected %0d errors during arbitration.", errors);
            $fatal(1);
        end
        $display("=====================================================");
        $finish;
    end

    // --- System Watchdog Timer ---
    initial begin
        #5000000; // Expanded to 5ms to allow all 4 tests to complete
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
endmodule