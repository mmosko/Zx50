`timescale 1ns/1ps

module zx50_mmu_atl_tb;
    reg z80_clk;
    reg [15:0] addr;
    reg [7:0] d_bus;
    reg iorq_n, wr_n, mreq_n, reset_n;
    reg boot_en_n;
    reg [3:0] id_sw;

    wire [3:0] atl_addr;
    wire [7:0] atl_data;
    wire atl_we_n, atl_oe_n;
    wire [7:0] p_hi;
    wire active;
    wire z80_card_hit;

    // --- 1. Clock Generation (36MHz Master, 6MHz Z80) ---
    reg mclk;
    initial mclk = 0;
    always #13.88 mclk = ~mclk; // 36MHz clock (~27.7ns period)

    reg [1:0] clk_div;
    initial begin
        z80_clk = 0;
        clk_div = 2'b00;
    end

    // Divide by 6: Toggle z80_clk every 3 MCLK cycles
    always @(posedge mclk) begin
        if (clk_div == 2'd2) begin
            clk_div <= 2'b00;
            z80_clk <= ~z80_clk;
        end else begin
            clk_div <= clk_div + 1'b1;
        end
    end

    // --- 2. DUT Instantiation ---
    zx50_mmu_sram dut (
        .mclk(mclk), 
        .z80_addr(addr), 
        .l_addr_hi(addr[15:12]), 
        .l_data(d_bus),               // Updated port name
        .z80_iorq_n(iorq_n), 
        .z80_wr_n(wr_n), 
        .z80_mreq_n(mreq_n), 
        .reset_n(reset_n), 
        .boot_en_n(boot_en_n), 
        .card_id_sw(id_sw), 
        
        .atl_addr(atl_addr), 
        .atl_data(atl_data), 
        .atl_we_n(atl_we_n), 
        .atl_oe_n(atl_oe_n),
        .p_addr_hi(p_hi), 
        .active(active), 
        .z80_card_hit(z80_card_hit)   // Monitored for Arbiter sync
    );

    // --- 3. Behavioral SRAM Model (15ns) ---
    reg [7:0] mock_sram [0:15];
    wire [7:0] atl_read_data;
    
    // Simulate SRAM read access time
    assign #15 atl_read_data = mock_sram[atl_addr];
    
    // SRAM drives the bus only when OE is low and WE is high
    assign atl_data = (!atl_oe_n && atl_we_n) ? atl_read_data : 8'hzz;

    // Simulate SRAM write (captures data shortly after WE drops)
    always @(negedge atl_we_n) begin
        #5 mock_sram[atl_addr] <= atl_data;
    end

    // --- 4. Test Sequence ---
    initial begin
        $dumpfile("waves/zx50_mmu_sram.vcd");
        $dumpvars(0, zx50_mmu_atl_tb);
        
        iorq_n = 1; wr_n = 1; mreq_n = 1;
        id_sw = 4'h0; boot_en_n = 0; // Boot override active
        addr = 0; d_bus = 0;

        reset_n = 1; 
        #50;
        addr = 16'bz; 
        d_bus = 8'bz;

        // Trigger hardware reset
        reset_n = 0;
        #700;
        reset_n = 1;

        addr = 0; d_bus = 0;

        // Wait for 16-cycle Hardware Wipe to finish
        repeat (20) @(posedge z80_clk); 

        // ==========================================
        // PHASE 1: Auto-Init 1:1 Mapping Check
        // ==========================================
        $display("--- Testing Phase 1: Auto-Init 1:1 Mapping ---");
        // Because boot_en_n = 0, page 8 (0x8000) should be claimed by this card
        addr = 16'h8000; 
        #70; 
        mreq_n = 0; // Simulate Z80 memory read
        #50;

        if (active === 1'b1 && p_hi === 8'h08 && z80_card_hit === 1'b1) begin
            $display("****** PHASE 1 PASSED: Memory claimed, translated to Page 8 ******");
        end else begin
            $display("!!!!!! PHASE 1 FAILED: active=%b, p_hi=%h, hit=%b !!!!!!", active, p_hi, z80_card_hit);
            $fatal(1);
        end
        
        mreq_n = 1;
        #100;

        // ==========================================
        // PHASE 2: Dynamic MMU Reprogramming Check
        // ==========================================
        $display("--- Testing Phase 2: Z80 MMU I/O Write ---");
        // Simulate: OUT (0x30), 0xAA (Writing translation 0xAA to Bank 0x0)
        addr = 16'h0030;  // High byte = 0 (Bank 0), Low byte = 0x30 (Family ID + Card 0)
        d_bus = 8'hAA;    // New physical page = 0xAA
        
        #50;
        iorq_n = 0; 
        
        // Assert WR_n. The DUT should instantly assert z80_card_hit, and 
        // a few ns later (on the MCLK edge), sync_we and atl_we_n should fire.
        #20 wr_n = 0; 
        #100;

        if (z80_card_hit === 1'b1 && atl_we_n === 1'b0) begin
            $display("****** PHASE 2 PASSED: I/O Snoop detected, SRAM WR Strobe Fired ******");
        end else begin
            $display("!!!!!! PHASE 2 FAILED: hit=%b, we_n=%b !!!!!!", z80_card_hit, atl_we_n);
            $fatal(1);
        end

        // End the I/O cycle
        wr_n = 1;
        #20 iorq_n = 1;
        
        // Verify SRAM actually latched it (Read Bank 0x0)
        #100;
        addr = 16'h0000;
        mreq_n = 0;
        #50;
        
        if (p_hi === 8'hAA) begin
            $display("****** PHASE 3 PASSED: SRAM successfully updated to 0xAA ******");
        end else begin
            $display("!!!!!! PHASE 3 FAILED: p_hi=%h (Expected 0xAA) !!!!!!", p_hi);
            $fatal(1);
        end

        $display("=====================================================");
        $display(" SUCCESS: All MMU and Transceiver tests passed.");
        $display("=====================================================");
        $finish;
    end

    // --- System Watchdog Timer ---
    initial begin
        #10000; 
        $display("FATAL [%0t]: Watchdog Timer Expired! State machine deadlock detected.", $time);
        $fatal(1);
    end
endmodule