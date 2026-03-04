`timescale 1ns/1ps

module zx50_dma (
    input wire mclk,
    input wire reset_n,

    // --- Z80 Configuration Interface ---
    input wire [15:0] z80_addr,
    input wire [7:0]  z80_data_in,
    input wire z80_iorq_n,
    input wire z80_wr_n,

    // --- Shadow Bus Master Interface ---
    output wire [15:0] shd_addr_out,
    output wire [7:0]  shd_data_out,
    input  wire [7:0]  shd_data_in,
    
    output wire shd_en_n_out,  
    output wire shd_rw_n_out,  
    output wire shd_inc_n_out, 
    output wire shd_stb_n_out,   // NEW: Shadow Strobe (Master drives)
    output wire shd_done_n_out,  // NEW: Shadow Done (Master drives)
    
    input  wire shd_busy_n_in, 
    input  wire shd_inc_n_in,  
    input  wire shd_stb_n_in,    // NEW: Snoop Strobe
    input  wire shd_done_n_in,   // NEW: Snoop Done

    // --- State & Control ---
    output wire dma_active     
);

    reg is_active;
    initial is_active = 1'b0; 
    
    assign dma_active = is_active;

    // --- Bus Yielding Logic ---
    assign shd_en_n_out   = is_active ? 1'b1 : 1'bz;
    assign shd_rw_n_out   = is_active ? 1'b1 : 1'bz;
    assign shd_inc_n_out  = is_active ? 1'b1 : 1'bz;
    assign shd_stb_n_out  = is_active ? 1'b1 : 1'bz;
    assign shd_done_n_out = is_active ? 1'b1 : 1'bz;
    
    assign shd_addr_out   = is_active ? 16'h0000 : 16'hzzzz;
    assign shd_data_out   = is_active ? 8'h00    : 8'hzz;

endmodule