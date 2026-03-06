`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_cpld_core
 * DESCRIPTION:
 * The top-level CPLD logic that integrates the MMU, Z80 Arbiter, and DMA.
 * It is responsible for extremely strict multiplexing of the physical IC pins, 
 * ensuring that the Z80, the SRAM chips, and the Backplane transceivers never 
 * contend with each other. 
 ***************************************************************************************/

module zx50_cpld_core (
    input  wire mclk,
    input  wire reset_n,
    input  wire boot_en_n,
    input  wire [3:0] duplex_in, 
    
    // --- Z80 Backplane ---
    input  wire z80_m1_n,       
    input  wire z80_iei,        
    output wire z80_ieo,        
    inout  wire z80_int_n,      
    inout  wire z80_wait_n,     
    input  wire [15:0] z80_addr, 
    
    // --- Local Shared Bus ---
    inout  wire [7:0]  l_data, 
    
    // --- Shadow Bus Controls (Bidirectional) ---
    inout  wire shadow_en_n, 
    inout  wire shd_rw_n, 
    inout  wire shd_inc_n, 
    inout  wire shd_stb_n, 
    inout  wire shd_done_n, 
    inout  wire shd_busy_n, 
    
    // --- Transceiver Controls ---
    output wire shd_c_dir,      
    output wire shd_c_oe_n,     
    output wire z80_data_oe_n, 
    output wire shd_data_oe_n, 
    output wire d_dir,
    
    // --- Local Memory & LUT Routing ---
    output wire [10:0] l_addr,  
    output wire [3:0]  atl_addr, 
    inout  wire [7:0]  atl_data, 
    output wire atl_we_n, 
    output wire atl_oe_n, 
    output wire atl_ce_n,
    output wire ce0_n, ce1_n,
    output wire ram_oe_n,
    output wire ram_we_n           
);

    // ==========================================
    // 1. DUPLEX CONFIGURATION LATCH
    // ==========================================
    reg [3:0] latched_id;   
    wire z80_rd_n   = duplex_in[0]; 
    wire z80_wr_n   = duplex_in[1]; 
    wire z80_mreq_n = duplex_in[2]; 
    wire z80_iorq_n = duplex_in[3]; 

    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) latched_id <= duplex_in; 
    end

    // ==========================================
    // 2. INTERNAL SUBSYSTEM WIRES & HIT LOGIC
    // ==========================================
    wire internal_active, mmu_busy;
    
    // PHANTOM HIT SHIELD: The MMU purely decodes the Z80 address bus combinatorially. 
    // We strictly qualify the MMU hit with an active MREQ or IORQ cycle to prevent 
    // the Arbiter from throwing fake yield requests when the Z80 is floating the bus.
    wire active_bus_cycle = !z80_mreq_n || !z80_iorq_n;
    wire mmu_card_hit;
    wire qualified_mmu_hit = mmu_card_hit && active_bus_cycle;
    wire dma_card_hit = (!z80_iorq_n && (z80_addr[7:0] == (8'h40 | latched_id)));
    wire internal_z80_card_hit = qualified_mmu_hit | dma_card_hit;

    wire arbiter_shd_busy_n;
    wire arbiter_d_dir; 
    wire arbiter_shd_data_oe_n; 
    wire arbiter_z80_data_oe_n;
    wire arbiter_wait_n;
    
    wire z80_grant = !z80_data_oe_n;
    
    wire [19:0] dma_phys_addr;
    wire dma_local_we_n, dma_local_oe_n, dma_dir_to_bus;
    wire dma_is_active, dma_int_pending, dma_is_master;

    wire memory_cycle = !z80_mreq_n;

    // ==========================================
    // 3. INTERRUPT & INTACK LOGIC
    // ==========================================
    wire intack_cycle = !z80_m1_n && !z80_iorq_n;
    wire responding_to_intack = intack_cycle && z80_iei && dma_int_pending;

    reg [1:0] iorq_sync;
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) iorq_sync <= 2'b11;
        else iorq_sync <= {iorq_sync[0], z80_iorq_n};
    end
    
    wire iorq_rising = (iorq_sync == 2'b01);
    wire intack_clear = iorq_rising && z80_iei && dma_int_pending;

    assign z80_int_n = dma_int_pending ? 1'b0 : 1'bz; 
    assign z80_ieo = z80_iei && !dma_int_pending; 

    // ==========================================
    // 4. CORE SUB-MODULE INSTANTIATIONS
    // ==========================================
    wire arbiter_hit  = internal_z80_card_hit || responding_to_intack;
    wire arbiter_rd_n = responding_to_intack ? 1'b0 : z80_rd_n;

    // SPATIAL INDEPENDENCE SHIELD: If this card is NOT participating in a DMA burst, 
    // it does not care if the backplane is busy! Feed the Arbiter a constant 1 (Idle) 
    // so it doesn't unnecessarily assert WAIT when the Z80 requests local access.
    wire safe_shadow_en_n = dma_is_active ? shadow_en_n : 1'b1;

    zx50_bus_arbiter arbiter_unit (
        .mclk(mclk), .reset_n(reset_n),
        .shadow_en_n(safe_shadow_en_n), // SHIELDED!
        .z80_card_hit(arbiter_hit), 
        .z80_wait_n(arbiter_wait_n), .shd_busy_n(arbiter_shd_busy_n), 
        .z80_rd_n(arbiter_rd_n), .shd_rw_n(shd_rw_n),
        .z80_data_oe_n(arbiter_z80_data_oe_n), 
        .shd_data_oe_n(arbiter_shd_data_oe_n), 
        .d_dir(arbiter_d_dir)                  
    );

    wire safe_z80_iorq_n = dma_is_active ? 1'b1 : z80_iorq_n;

    zx50_mmu_sram mmu_unit (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(latched_id), 
        .z80_addr(z80_addr), .l_addr_hi(z80_addr[15:12]), 
        .l_data(l_data), .z80_iorq_n(safe_z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_mreq_n(z80_mreq_n), 
        .atl_addr(atl_addr), .atl_data(atl_data), .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n),
        .p_addr_hi(), .active(internal_active), 
        .z80_card_hit(mmu_card_hit), 
        .is_busy(mmu_busy) 
    );

    zx50_dma dma_unit (
        .mclk(mclk), .reset_n(reset_n), .card_id(latched_id),
        .z80_addr(z80_addr), .z80_data_in(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n),
        .dma_phys_addr(dma_phys_addr), .dma_data_out(), .dma_data_in(l_data), 
        .dma_local_we_n(dma_local_we_n), .dma_local_oe_n(dma_local_oe_n),
        .shd_en_n(shadow_en_n), .shd_rw_n(shd_rw_n), .shd_inc_n(shd_inc_n),
        .shd_stb_n(shd_stb_n), .shd_done_n(shd_done_n), 
        .shd_busy_n(shd_busy_n), 
        .dma_active(dma_is_active), .shd_c_dir(shd_c_dir), .dma_dir_to_bus(dma_dir_to_bus),
        .dma_is_master(dma_is_master), .int_pending(dma_int_pending), .intack_clear(intack_clear)
    );

    // ==========================================
    // 5. LOCAL MEMORY & LUT TAKEOVER MULTIPLEXING
    // ==========================================
    assign l_addr = z80_grant ? z80_addr[10:0] : (dma_is_active ? dma_phys_addr[10:0] : 11'bz);
    assign atl_ce_n = dma_is_active ? 1'b1 : !(internal_z80_card_hit || mmu_busy); 
    assign atl_data = dma_is_active ? dma_phys_addr[18:11] : (!atl_we_n ? l_data : 8'hzz);

    wire bank_select = dma_is_active ? dma_phys_addr[19] : atl_data[7];
    wire safe_to_access_ram = dma_is_active || (internal_z80_card_hit && atl_we_n && memory_cycle);
    
    assign ce0_n = (safe_to_access_ram && bank_select == 1'b0) ? 1'b0 : 1'b1;
    assign ce1_n = (safe_to_access_ram && bank_select == 1'b1) ? 1'b0 : 1'b1;

    assign ram_oe_n = dma_is_active ? dma_local_oe_n : ((z80_grant && memory_cycle) ? z80_rd_n : 1'b1);
    assign ram_we_n = dma_is_active ? dma_local_we_n : ((z80_grant && memory_cycle) ? z80_wr_n : 1'b1);

    wire [7:0] interrupt_vector = 8'h40 | latched_id;
    assign l_data = responding_to_intack ? interrupt_vector : 8'hzz;

    // ==========================================
    // 6. CYCLE STEALING: INTERCEPT & OVERRIDE LOGIC
    // ==========================================
    assign shd_c_oe_n = 1'b0; 

    assign z80_wait_n = ((arbiter_hit && dma_is_active) || arbiter_wait_n == 1'b0) ? 1'b0 : 1'bz;
    assign z80_data_oe_n = dma_is_active ? 1'b1 : arbiter_z80_data_oe_n;
    
    // We ONLY pull shd_busy_n low to command a yield IF we are actively participating 
    // in a DMA burst. Independent cards let the shadow bus keep flying!
    assign shd_busy_n = (arbiter_hit && dma_is_active) ? 1'b0 : 1'bz;

    assign shd_data_oe_n = dma_is_active ? 1'b0 : arbiter_shd_data_oe_n;
    assign d_dir         = dma_is_active ? dma_dir_to_bus : arbiter_d_dir;

endmodule