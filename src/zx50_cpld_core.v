`timescale 1ns/1ps

module zx50_cpld_core (
    input  wire mclk,
    input  wire reset_n,
    input  wire boot_en_n,
    input  wire [3:0] duplex_in, 
    input  wire z80_m1_n,       
    input  wire z80_iei,        
    output wire z80_ieo,        
    inout  wire z80_int_n,      
    inout  wire z80_wait_n,     
    input  wire [15:0] z80_addr, 
    inout  wire [7:0]  l_data, 
    inout  wire shadow_en_n, 
    inout  wire shd_rw_n, 
    inout  wire shd_inc_n, 
    inout  wire shd_stb_n, 
    inout  wire shd_done_n, 
    inout  wire shd_busy_n, 
    output wire shd_c_dir,      
    output wire shd_c_oe_n,     
    output wire [10:0] l_addr,  
    output wire [3:0]  atl_addr, 
    inout  wire [7:0]  atl_data, 
    output wire atl_we_n, 
    output wire atl_oe_n, 
    output wire atl_ce_n,
    output wire ce0_n, ce1_n,
    output wire ram_oe_n,
    output wire ram_we_n,
    output wire z80_data_oe_n, 
    output wire shd_data_oe_n, 
    output wire d_dir           
);

    // --- 1. Duplex Logic ---
    reg [3:0] latched_id;   
    wire z80_rd_n   = duplex_in[0]; 
    wire z80_wr_n   = duplex_in[1]; 
    wire z80_mreq_n = duplex_in[2]; 
    wire z80_iorq_n = duplex_in[3]; 

    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) latched_id <= duplex_in; 
    end

    // --- 2. Internal Wires ---
    wire internal_z80_card_hit, internal_active, mmu_busy;
    wire dma_is_active; 
    wire [15:0] dma_addr_out; 
    wire [7:0]  dma_data_out; 
    wire dma_shd_en_n, dma_shd_rw_n, dma_shd_inc_n, dma_shd_stb_n, dma_shd_done_n; 
    wire arbiter_shd_busy_n; 
    wire z80_grant = !z80_data_oe_n;
    wire shd_grant = !shd_data_oe_n;

    // --- 3. Sub-Modules ---
    zx50_bus_arbiter arbiter_unit (
        .mclk(mclk), .reset_n(reset_n),
        .shadow_en_n(shadow_en_n), .z80_card_hit(internal_z80_card_hit), 
        .z80_wait_n(z80_wait_n), .shd_busy_n(arbiter_shd_busy_n), 
        .z80_rd_n(z80_rd_n), .shd_rw_n(shd_rw_n),
        .z80_data_oe_n(z80_data_oe_n), .shd_data_oe_n(shd_data_oe_n), .d_dir(d_dir)
    );

    zx50_mmu_sram mmu_unit (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(latched_id), 
        .z80_addr(z80_addr), .l_addr_hi(shd_grant ? dma_addr_out[15:12] : z80_addr[15:12]), 
        .l_data(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_mreq_n(z80_mreq_n), 
        .atl_addr(atl_addr), .atl_data(atl_data), .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n),
        .p_addr_hi(), .active(internal_active), .z80_card_hit(internal_z80_card_hit),
        .is_busy(mmu_busy) 
    );

    zx50_dma dma_unit (
        .mclk(mclk), .reset_n(reset_n),
        .z80_addr(z80_addr), .z80_data_in(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n),
        .dma_addr_out(dma_addr_out), .dma_data_out(dma_data_out), .dma_data_in(l_data), 
        .shd_en_n_out(dma_shd_en_n), .shd_rw_n_out(dma_shd_rw_n), .shd_inc_n_out(dma_shd_inc_n),
        .shd_stb_n_out(dma_shd_stb_n), .shd_done_n_out(dma_shd_done_n),
        .shd_busy_n_in(shd_busy_n), .shd_inc_n_in(shd_inc_n), 
        .shd_stb_n_in(shd_stb_n), .shd_done_n_in(shd_done_n),
        .dma_active(dma_is_active)
    );

    // --- 4. Assignments & Routing ---
    assign l_addr = z80_grant ? z80_addr[10:0] : (shd_grant ? dma_addr_out[10:0] : 11'bz);
    
    assign shd_c_dir  = dma_is_active ? 1'b0 : 1'b1;
    assign shd_c_oe_n = 1'b0;
    assign shadow_en_n = dma_is_active ? dma_shd_en_n : 1'bz;
    assign shd_rw_n    = dma_is_active ? dma_shd_rw_n : 1'bz;
    assign shd_inc_n   = dma_is_active ? dma_shd_inc_n : 1'bz;
    assign shd_stb_n   = dma_is_active ? dma_shd_stb_n : 1'bz;
    assign shd_done_n  = dma_is_active ? dma_shd_done_n : 1'bz;
    assign shd_busy_n  = (!dma_is_active && !arbiter_shd_busy_n) ? 1'b0 : 1'bz;

    assign l_data = (dma_is_active && !dma_shd_rw_n) ? dma_data_out : 8'hzz;

    // --- 5. Memory Logic ---
    wire local_hit = (z80_grant && internal_active) || shd_grant;
    assign atl_ce_n = !(mmu_busy || local_hit);
    wire safe_to_access_ram = local_hit && atl_we_n;
    
    assign ce0_n = (safe_to_access_ram && atl_data[7] == 1'b0) ? 1'b0 : 1'b1;
    assign ce1_n = (safe_to_access_ram && atl_data[7] == 1'b1) ? 1'b0 : 1'b1;
    assign ram_oe_n = z80_grant ? z80_rd_n : (shd_grant ? shd_rw_n : 1'b1);
    assign ram_we_n = z80_grant ? z80_wr_n : (shd_grant ? !shd_rw_n : 1'b1);

    reg int_pending; 
    assign z80_int_n = (int_pending && z80_iei && reset_n) ? 1'b0 : 1'bz; 
    assign z80_ieo   = (z80_iei && !int_pending); 

endmodule