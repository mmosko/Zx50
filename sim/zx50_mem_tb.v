`timescale 1ns/1ps

module zx50_mem_tb;

    // --- 1. Clocks ---
    reg mclk;
    reg [1:0] clk_div;
    wire z80_clk = clk_div[1]; // 6MHz Z80 Clock

    initial begin
        mclk = 0;
        clk_div = 0;
    end
    always #20.83 mclk = ~mclk; // 24MHz
    always @(posedge mclk) clk_div <= clk_div + 1'b1;

    // --- 2. Z80 Bus Signals ---
    reg reset_n, iorq_n, wr_n, rd_n, mreq_n, boot_en;
    reg [15:0] addr_reg;
    reg [7:0]  d_bus_reg;

    wire [15:0] addr = addr_reg;
    wire [7:0]  d_bus = (rd_n == 0) ? 8'bz : d_bus_reg;

    // --- 3. Internal Nets ---
    wire [3:0] sram_a;
    wire [7:0] sram_d, p_hi;
    wire sram_we_n, sram_oe_n, active;

    // --- 4. Hardware Under Test ---
    zx50_mmu_sram mmu (
        .mclk(mclk), .addr(addr), .d_bus(d_bus), .iorq_n(iorq_n), .wr_n(wr_n), 
        .mreq_n(mreq_n), .reset_n(reset_n), .boot_en_n(boot_en), .card_id_sw(4'h0),
        .sram_a(sram_a), .sram_d(sram_d), .sram_we_n(sram_we_n), .sram_oe_n(sram_oe_n),
        .p_addr_hi(p_hi), .active(active)
    );

    zx50_mem mem (
        .addr_low(addr[11:0]), .d_bus(d_bus), .rd_n(rd_n), .wr_n(wr_n), 
        .mreq_n(mreq_n), .p_addr_hi(p_hi), .active(active)
    );

    // --- 5. Mock SRAM (MMU Lookup Table) ---
    reg [7:0] mock_lut_sram [0:15];
    wire [7:0] lut_data_out;
    
    // 10ns access delay
    assign #10 lut_data_out = mock_lut_sram[sram_a];

    // Drive sram_d bus only when MMU Output Enable is active
    assign sram_d = (!sram_oe_n && sram_we_n) ? lut_data_out : 8'hzz;

    // Write on the negedge, after signals have stabilized.
    // This avoids the delta-cycle race when the CPU ends the write cycle.
    always @(negedge sram_we_n) begin
        #5 mock_lut_sram[sram_a] <= sram_d;
    end

    // --- 6. Z80 Hardware Tasks ---
    task mmu_map(input [3:0] page, input [7:0] bank);
        begin
            @(posedge z80_clk);
            // Z80 OUT (C), r instruction:
            // A15-A8 = B reg (Page), A7-A0 = C reg (Port 0x30)
            addr_reg = {4'h0, page, 8'h30}; 
            d_bus_reg = bank;
            @(negedge z80_clk);
            iorq_n = 0; wr_n = 0;
            @(posedge z80_clk);
            @(posedge z80_clk);
            iorq_n = 1; wr_n = 1;
            d_bus_reg = 8'hzz;
        end
    endtask

    task mem_write(input [15:0] a, input [7:0] d);
        begin
            @(posedge z80_clk);
            addr_reg = a; d_bus_reg = d;
            @(negedge z80_clk);
            mreq_n = 0; wr_n = 0;
            @(posedge z80_clk);
            @(posedge z80_clk);
            mreq_n = 1; wr_n = 1;
            d_bus_reg = 8'hzz;
        end
    endtask

    task mem_read(input [15:0] a, output [7:0] data);
        begin
            @(posedge z80_clk);
            addr_reg = a;
            @(negedge z80_clk);
            mreq_n = 0; rd_n = 0;
            @(posedge z80_clk);
            @(posedge z80_clk); // Wait for T3
            data = d_bus;       // Sample data
            mreq_n = 1; rd_n = 1;
        end
    endtask

    // --- 7. Main Test Sequence ---
    reg [7:0] r_data;
    initial begin
        $dumpfile("waves/zx50_mem.vcd");
        $dumpvars(0, zx50_mem_tb);
        
        // Initial States to prevent 'X' propagation!
        reset_n = 1; iorq_n = 1; wr_n = 1; rd_n = 1; mreq_n = 1; boot_en = 0;
        addr_reg = 16'h0000; 
        d_bus_reg = 8'hzz;

        // Hardware Wipe
        #100 reset_n = 0; #700 reset_n = 1; #100;

        $display("--- Step 0: CPU Claims Lower 32KB (Pages 0-7) ---");
        for (integer i=0; i<8; i=i+1) mmu_map(i[3:0], i[7:0]);

        $display("--- Step 1: Writing Pattern 0xA0+page to Memory ---");
        for (integer i=0; i<16; i=i+1) mem_write(i << 12, 8'hA0 + i);

        $display("--- Step 2: Swap Page 5 to Bank 0xEE ---");
        mmu_map(4'h5, 8'hEE);
        mem_read(16'h5000, r_data);
        $display("Read Page 5 (Bank EE): Got %h", r_data);

        $display("--- Step 3: Map Bank 0x05 to Logical Page 1 ---");
        mmu_map(4'h1, 8'h05); 
        mem_read(16'h1000, r_data);
        if (r_data === 8'hA5) $display("SUCCESS: Found 0xA5 at Page 1!");
        else                  $display("FAIL: Got %h", r_data);

        $display("--- Step 4: Map Page 5 back to Bank 0x05 ---");
        mmu_map(4'h5, 8'h05); 
        mem_read(16'h5000, r_data);
        if (r_data === 8'hA5) $display("SUCCESS: Page 5 Restored!");
        else                  $display("FAIL: Got %h", r_data);

        $finish;
    end
endmodule