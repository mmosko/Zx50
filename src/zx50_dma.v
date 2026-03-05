`timescale 1ns/1ps

// ========================================================================
// REFINED TERMINOLOGY
// ========================================================================
// Master Mode (dma_active): This specific card has successfully requested the 
// bus and is now driving the Shadow Address, Data, and Control lines.
// 
// Target Mode (!dma_active): The card is not the master; it is "listening" to the 
// backplane to see if a Shadow Address matches its local ID.
//
// Bus Hit (target_hit): A condition in Target Mode where the
// external shd_en_n is asserted and the address on the bus matches this card.
//
// Shadow Busy (busy_n): An open-drain signal driven by a Target to tell the Master to wait.
// ========================================================================

module zx50_dma (
    input wire mclk,
    input wire reset_n,

    // --- Z80 Configuration Interface ---
    input wire [15:0] z80_addr,
    input wire [7:0]  z80_data_in,
    input wire z80_iorq_n,
    input wire z80_wr_n,

    // --- Local & Shadow Bus Master Interface ---
    // (Note: Tri-stating to the actual backplane is handled by zx50_cpld_core)
    output wire [15:0] dma_addr_out,
    output wire [7:0]  dma_data_out,
    input  wire [7:0]  dma_data_in,
    
    output wire shd_en_n_out,   // Active-Low: Enabled when 0 
    output wire shd_rw_n_out,   // 0=Write, 1=Read 
    output wire shd_inc_n_out,  // Auto-increment flag 
    output wire shd_stb_n_out,  // Shadow Strobe 
    output wire shd_done_n_out, // Shadow Done 
    
    // --- Shadow Bus Target/Status Inputs ---
    input  wire shd_busy_n_in,  // Feedback from Target 
    input  wire shd_inc_n_in,   
    input  wire shd_stb_n_in,    
    input  wire shd_done_n_in,   

    // --- State & Control ---
    output wire dma_active      // High when this card is the Master (formerly dma_is_master)
);

    // Internal registers for Master mode
    reg is_master;
    reg [15:0] master_addr_reg;
    reg [7:0]  master_data_reg;
    reg master_rw_n;
    reg master_stb_n;
    reg master_done_n;

    // Output the internal state to the Top-Level muxes
    assign dma_active = is_master;

    // ==========================================
    // BUS DRIVING LOGIC (Clean Logic Levels)
    // ==========================================
    // Because zx50_cpld_core handles the 1'bz isolation, we simply output 
    // the register values or safe inactive highs (1'b1).

    assign shd_en_n_out   = is_master ? 1'b0 : 1'b1; 
    assign shd_rw_n_out   = is_master ? master_rw_n   : 1'b1;
    assign shd_inc_n_out  = is_master ? 1'b0          : 1'b1; 
    assign shd_stb_n_out  = is_master ? master_stb_n  : 1'b1;
    assign shd_done_n_out = is_master ? master_done_n : 1'b1;

    assign dma_addr_out   = master_addr_reg;
    assign dma_data_out   = master_data_reg;

    // ==========================================
    // DMA STATE MACHINE (No-Op Stub)
    // ==========================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            is_master       <= 1'b0;
            master_addr_reg <= 16'h0000;
            master_data_reg <= 8'h00;
            master_rw_n     <= 1'b1;
            master_stb_n    <= 1'b1;
            master_done_n   <= 1'b1;
        end else begin
            // Placeholder: Z80 I/O Decode logic goes here.
            // Example:
            // if (!z80_iorq_n && !z80_wr_n && z80_addr[7:0] == 8'h40) begin
            //     master_addr_reg[7:0] <= z80_data_in;
            // end
        end
    end

endmodule