`timescale 1ns/1ps

module zx50_dma_tb;

    // --- 1. Clocks & Reset ---
    reg mclk;
    reg reset_n;

    // --- 2. Z80 Interface (For Programming the DMA) ---
    reg [15:0] z80_addr;
    reg [7:0]  z80_data_in;
    reg z80_iorq_n;
    reg z80_wr_n;

    // --- 3. Local Memory Bus (DMA acting as Master) ---
    wire [15:0] dma_addr_out;
    wire [7:0]  dma_data_out;
    reg  [7:0]  dma_data_in;

    // --- 4. Shadow Bus Master Outputs ---
    wire dma_shd_en_n_out;
    wire dma_shd_rw_n_out;
    wire dma_shd_inc_n_out;
    wire dma_shd_stb_n_out;
    wire dma_shd_done_n_out;

    // --- 5. Shadow Bus Target/Status Inputs ---
    reg shd_busy_n_in;
    reg shd_inc_n_in;
    reg shd_stb_n_in;
    reg shd_done_n_in;

    // --- 6. Status Output ---
    wire dma_active;

    // --- 7. Clock Generation (36MHz Master) ---
    initial mclk = 0;
    always #13.88 mclk = ~mclk; // ~27.7ns period

    // --- 8. DUT Instantiation ---
    zx50_dma dut (
        .mclk(mclk), 
        .reset_n(reset_n),
        .z80_addr(z80_addr), 
        .z80_data_in(z80_data_in), 
        .z80_iorq_n(z80_iorq_n), 
        .z80_wr_n(z80_wr_n),
        .dma_addr_out(dma_addr_out), 
        .dma_data_out(dma_data_out), 
        .dma_data_in(dma_data_in), 
        .shd_en_n_out(dma_shd_en_n_out), 
        .shd_rw_n_out(dma_shd_rw_n_out), 
        .shd_inc_n_out(dma_shd_inc_n_out),
        .shd_stb_n_out(dma_shd_stb_n_out), 
        .shd_done_n_out(dma_shd_done_n_out),
        .shd_busy_n_in(shd_busy_n_in), 
        .shd_inc_n_in(shd_inc_n_in), 
        .shd_stb_n_in(shd_stb_n_in), 
        .shd_done_n_in(shd_done_n_in),
        .dma_active(dma_active)
    );

    // --- 9. Test Sequence ---
    initial begin
        $dumpfile("waves/zx50_dma.vcd");
        $dumpvars(0, zx50_dma_tb);
        
        // Initialize default inactive states
        reset_n = 1;
        z80_addr = 16'h0000;
        z80_data_in = 8'h00;
        z80_iorq_n = 1;
        z80_wr_n = 1;
        dma_data_in = 8'h00;
        
        shd_busy_n_in = 1;
        shd_inc_n_in = 1;
        shd_stb_n_in = 1;
        shd_done_n_in = 1;

        // Apply Reset
        #50 reset_n = 0;
        #100 reset_n = 1;
        
        repeat(5) @(posedge mclk);

        // ==========================================
        // PHASE 1: Verify No-Op / Dormant State
        // ==========================================
        $display("[%0t] --- Phase 1: Verifying Dormant Reset State ---", $time);
        
        if (dma_active !== 1'b0) begin
            $display("FATAL: DMA woke up immediately after reset! (dma_active=%b)", dma_active);
            $fatal(1);
        end
        
        if (dma_shd_en_n_out !== 1'b1 || dma_shd_stb_n_out !== 1'b1) begin
            $display("FATAL: DMA is driving Shadow Bus control lines active without permission!");
            $fatal(1);
        end

        // ==========================================
        // PHASE 2: Verify Immunity to Z80 I/O Noise
        // ==========================================
        $display("[%0t] --- Phase 2: Verifying Z80 I/O Immunity ---", $time);
        
        // Simulate the Z80 writing to an I/O port (e.g., programming the MMU)
        // The DMA should ignore this and stay inactive.
        @(posedge mclk);
        z80_addr = 16'h0030; // Hitting the MMU base port
        z80_data_in = 8'hAA;
        z80_iorq_n = 0;
        
        #10 z80_wr_n = 0;
        repeat(3) @(posedge mclk);
        
        if (dma_active !== 1'b0) begin
            $display("FATAL: DMA falsely triggered on unrelated Z80 I/O write!");
            $fatal(1);
        end
        
        z80_wr_n = 1;
        #10 z80_iorq_n = 1;
        repeat(3) @(posedge mclk);

        // ==========================================
        // PHASE 3: Future-Proofing (Placeholder for real DMA test)
        // ==========================================
        // When you implement the DMA, you will add logic here to write to the 
        // DMA's specific configuration ports (e.g., 0x40), trigger a transfer, 
        // and verify that dma_active goes HIGH and it drives dma_addr_out.
        
        $display("=====================================================");
        $display(" SUCCESS: DMA No-Op Stub passed all safety checks.");
        $display("=====================================================");
        $finish;
    end

    // --- 10. System Watchdog Timer ---
    initial begin
        #10000; 
        $display("FATAL [%0t]: Watchdog Timer Expired! Testbench deadlock detected.", $time);
        $fatal(1);
    end

endmodule