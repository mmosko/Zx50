`timescale 1ns/1ps

module zx50_mmu_sram_tb;
    reg z80_clk;
    reg [15:0] addr;
    reg [7:0] d_bus;
    reg iorq_n, wr_n, mreq_n, reset_n;
    reg boot_en;
    reg [3:0] id_sw;

    wire [3:0] sram_a;
    wire [7:0] sram_d;
    wire sram_we_n, sram_oe_n;
    wire [7:0] p_hi;
    wire active;

    reg mclk;
    initial mclk = 0;
    always #20.83 mclk = ~mclk; // 24MHz clock (~41.6ns period)

    // Generate Z80_CLK (6MHz) as 1/4 of MCLK
    // Using a counter ensures the rising edges are perfectly aligned
    reg [1:0] clk_div;
    initial begin
        z80_clk = 0;
        clk_div = 2'b00;
    end

    always @(posedge mclk) begin
        clk_div <= clk_div + 1;
        if (clk_div == 2'b01) // Toggles every 2 MCLK cycles for a 1/4 freq
            z80_clk <= ~z80_clk;
    end

    // 2. DUT Instance
    zx50_mmu_sram dut (
        .mclk(mclk), .addr(addr), .d_bus(d_bus), 
        .iorq_n(iorq_n), .wr_n(wr_n), .mreq_n(mreq_n), .reset_n(reset_n), 
        .boot_en_n(boot_en), .card_id_sw(id_sw), 
        .sram_a(sram_a), .sram_d(sram_d), .sram_we_n(sram_we_n), .sram_oe_n(sram_oe_n),
        .p_addr_hi(p_hi), .active(active)
    );

    // 3. Behavioral SRAM Model (15ns)
    reg [7:0] mock_sram [0:15];
    wire [7:0] sram_read_data;
    assign #15 sram_read_data = mock_sram[sram_a];
    assign sram_d = (!sram_oe_n && sram_we_n) ? sram_read_data : 8'hzz;

    always @(negedge sram_we_n) begin
        #5 mock_sram[sram_a] <= sram_d;
    end

    // 4. Test Sequence
    initial begin
        $dumpfile("waves/zx50_mmu_sram.vcd");
        $dumpvars(0, zx50_mmu_sram_tb);
        
        iorq_n = 1; wr_n = 1; mreq_n = 1;
        id_sw = 4'h0; boot_en = 0; addr = 0; d_bus = 0;

        reset_n = 1; 
        #50;
        addr = 16'bz; 
        d_bus = 8'bz;

        reset_n = 0;

        #700;
        reset_n = 1;

        addr = 0; d_bus = 0;

        // Wait for 16-cycle Hardware Wipe
        repeat (20) @(posedge z80_clk); 

        // Check for 1:1 Mapping
        $display("--- Testing Auto-Init 1:1 Mapping ---");
        addr = 16'h8000; #70; mreq_n = 0; #50;

        if (active === 1'b1 && p_hi === 8'h08)
            $display("****** AUTO-INIT PASSED ******");
        else
            $display("!!!!!! AUTO-INIT FAILED: p_hi=%h !!!!!!", p_hi);

        $finish;
    end
endmodule