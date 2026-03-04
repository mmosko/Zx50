`timescale 1ns/1ps

module zx50_dma_tb;

    reg mclk, reset_n;
    
    // --- Backplane Shadow Bus Nets ---
    wire [15:0] shd_addr;
    wire [7:0]  shd_data;
    wire shd_en_n, shd_rw_n, shd_inc_n, shd_busy_n;

    // ==========================================
    // PHYSICAL BACKPLANE PULL-UP RESISTORS
    // ==========================================
    // These ensure the control lines idle HIGH when no one is driving them,
    // exactly like the RN (Resistor Network) on your KiCad schematic.
    pullup(shd_en_n);
    pullup(shd_rw_n);
    pullup(shd_inc_n);
    pullup(shd_busy_n);
    
    // Note: We typically don't pull up the Address/Data bus, 
    // we let them stay floating (Z) to save power.

    // --- Instantiate the DMA Controller ---
    zx50_dma uut (
        .mclk(mclk), .reset_n(reset_n),
        
        // Wire outputs directly to the shared bus
        .shd_addr_out(shd_addr), 
        .shd_data_out(shd_data), 
        .shd_data_in(shd_data), 
        
        .shd_en_n_out(shd_en_n), 
        .shd_rw_n_out(shd_rw_n), 
        .shd_inc_n_out(shd_inc_n),
        
        .shd_busy_n_in(shd_busy_n),
        .shd_inc_n_in(shd_inc_n),
        
        .dma_active() // We can monitor this in GTKWave
    );

    // ... Clock & Test sequence ...

    // DMA is just a placeholder for now
endmodule