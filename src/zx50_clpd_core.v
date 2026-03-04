`timescale 1ns/1ps

module zx50_cpld_core (
    input wire mclk, reset_n, boot_en_n,
    input wire [3:0] card_id_sw,

    // --- Backplane Z80 Bus ---
    input wire [15:0] z80_addr,
    input wire [7:0]  z80_data,
    input wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n,
    output wire z80_wait_n,
    
    // --- Backplane Shadow Bus (All Inouts for Master/Target mode) ---
    inout wire shadow_en_n, 
    inout wire shd_rw_n,
    inout wire shd_inc_n,
    inout wire shd_stb_n,
    inout wire shd_done_n,
    inout wire shd_busy_n,

    // --- Local Hardware Bus ---
    inout wire [15:0] l_addr,
    
    output wire [3:0] atl_addr,
    inout  wire [7:0] atl_data,
    output wire atl_we_n, atl_oe_n,
    output wire ce0_n, ce1_n,

    // --- Transceiver Controls ---
    output wire z80_addr_oe_n, z80_data_oe_n, z80_data_dir,
    output wire shd_addr_oe_n, shd_data_oe_n, shd_data_dir,
    output wire shd_addr_dir 
);

    wire internal_z80_card_hit, internal_active;
    
    // DMA Master internal wires
    wire dma_is_active;
    wire [15:0] dma_shd_addr;
    wire [7:0]  dma_shd_data;
    wire dma_shd_en_n, dma_shd_rw_n, dma_shd_inc_n, dma_shd_stb_n, dma_shd_done_n;
    
    // Arbiter internal wires
    wire arbiter_shd_busy_n;

    zx50_mmu_sram mmu_unit (
        .mclk(mclk), .z80_addr(z80_addr), .l_addr_hi(l_addr[15:12]), .z80_data(z80_data), 
        .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_mreq_n(z80_mreq_n), 
        .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(card_id_sw),
        .atl_addr(atl_addr), .atl_data(atl_data), .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n),
        .p_addr_hi(), .active(internal_active), .z80_card_hit(internal_z80_card_hit)
    );

    zx50_bus_arbiter arbiter_unit (
        .mclk(mclk), .reset_n(reset_n),
        .shadow_en_n(shadow_en_n), .z80_card_hit(internal_z80_card_hit), 
        .z80_rd_n(z80_rd_n), .shd_rw_n(shd_rw_n),
        
        .z80_wait_n(z80_wait_n), .shd_busy_n(arbiter_shd_busy_n), 
        .z80_addr_oe_n(z80_addr_oe_n), .z80_data_oe_n(z80_data_oe_n), .z80_data_dir(z80_data_dir),
        .shd_addr_oe_n(shd_addr_oe_n), .shd_data_oe_n(shd_data_oe_n), .shd_data_dir(shd_data_dir)
    );

    zx50_dma dma_unit (
        .mclk(mclk), .reset_n(reset_n),
        .z80_addr(z80_addr), .z80_data_in(z80_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n),
        .shd_addr_out(dma_shd_addr), .shd_data_out(dma_shd_data), .shd_data_in(8'h00), 
        .shd_en_n_out(dma_shd_en_n), .shd_rw_n_out(dma_shd_rw_n), .shd_inc_n_out(dma_shd_inc_n),
        .shd_stb_n_out(dma_shd_stb_n), .shd_done_n_out(dma_shd_done_n),
        .shd_busy_n_in(shd_busy_n), .shd_inc_n_in(shd_inc_n), 
        .shd_stb_n_in(shd_stb_n), .shd_done_n_in(shd_done_n),
        .dma_active(dma_is_active)
    );

    // ==========================================
    // 2. Backplane Muxing (Master vs Target)
    // ==========================================
    assign shadow_en_n = dma_shd_en_n;
    assign shd_rw_n    = dma_shd_rw_n;
    assign shd_inc_n   = dma_shd_inc_n;
    assign shd_stb_n   = dma_shd_stb_n;
    assign shd_done_n  = dma_shd_done_n;
    
    assign shd_busy_n  = (!arbiter_shd_busy_n) ? 1'b0 : 1'bz;
    
    // UPDATED: Drive the bidirectional local address bus if we are the master, otherwise float.
    assign l_addr = dma_is_active ? dma_shd_addr : 16'hzzzz;
    
    assign shd_addr_dir = dma_is_active ? 1'b0 : 1'b1;

    // ==========================================
    // 3. Cypress Chip Enables
    // ==========================================
    wire local_bus_active = ((!z80_addr_oe_n && internal_active) || !shd_addr_oe_n);
    wire safe_to_read = local_bus_active && atl_we_n;
    assign ce0_n = (safe_to_read && atl_data[7] === 1'b0) ? 1'b0 : 1'b1;
    assign ce1_n = (safe_to_read && atl_data[7] === 1'b1) ? 1'b0 : 1'b1;

endmodule