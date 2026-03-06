`timescale 1ns/1ps

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
    // 1. Duplex Config / Run-Time Logic
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
    // 2. Internal Subsystem Wires
    // ==========================================
    wire internal_z80_card_hit, internal_active, mmu_busy;
    wire arbiter_shd_busy_n; 
    wire z80_grant = !z80_data_oe_n;
    
    wire [19:0] dma_phys_addr;
    wire dma_local_we_n, dma_local_oe_n, dma_dir_to_bus;
    wire dma_is_active, dma_int_pending;

    // ==========================================
    // 3. Interrupt & INTACK Logic
    // ==========================================
    
    // Z80 asserts M1 and IORQ simultaneously to request an interrupt vector
    wire intack_cycle = !z80_m1_n && !z80_iorq_n;
    
    // We only respond if we have a pending interrupt AND higher-priority cards allow it (IEI=1)
    wire responding_to_intack = intack_cycle && z80_iei && dma_int_pending;

    // Edge detector: The Z80 drops IORQ at the very end of the INTACK cycle. 
    // We use this rising edge to auto-clear the DMA's pending interrupt flag.
    reg [1:0] iorq_sync;
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) iorq_sync <= 2'b11;
        else iorq_sync <= {iorq_sync[0], z80_iorq_n};
    end
    
    wire iorq_rising = (iorq_sync == 2'b01);
    wire intack_clear = iorq_rising && !z80_m1_n && z80_iei && dma_int_pending;

    // Open-Drain Interrupt Request to the Z80 Backplane
    assign z80_int_n = dma_int_pending ? 1'b0 : 1'bz; 
    
    // Daisy Chain Output: High only if input is High AND we aren't interrupting
    assign z80_ieo = z80_iei && !dma_int_pending; 

    // ==========================================
    // 4. Core Sub-Modules
    // ==========================================
    
    // The Arbiter needs to open the Z80 data transceivers pointing inward (Card -> Master).
    // We trick it by synthesizing a "Hit" and a "Read" condition during INTACK.
    wire arbiter_hit  = internal_z80_card_hit || responding_to_intack;
    wire arbiter_rd_n = responding_to_intack ? 1'b0 : z80_rd_n;

    zx50_bus_arbiter arbiter_unit (
        .mclk(mclk), .reset_n(reset_n),
        .shadow_en_n(shadow_en_n), .z80_card_hit(arbiter_hit), 
        .z80_wait_n(z80_wait_n), .shd_busy_n(arbiter_shd_busy_n), 
        .z80_rd_n(arbiter_rd_n), .shd_rw_n(shd_rw_n),
        .z80_data_oe_n(z80_data_oe_n), .shd_data_oe_n(shd_data_oe_n), .d_dir(d_dir)
    );

    // The MMU only translates during standard Z80 accesses. Bypassed by DMA.
    zx50_mmu_sram mmu_unit (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(latched_id), 
        .z80_addr(z80_addr), .l_addr_hi(z80_addr[15:12]), 
        .l_data(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_mreq_n(z80_mreq_n), 
        .atl_addr(atl_addr), .atl_data(atl_data), .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n),
        .p_addr_hi(), .active(internal_active), .z80_card_hit(internal_z80_card_hit),
        .is_busy(mmu_busy) 
    );

    zx50_dma dma_unit (
        .mclk(mclk), .reset_n(reset_n),
        .z80_addr(z80_addr), .z80_data_in(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n),
        .dma_phys_addr(dma_phys_addr), .dma_data_out(), .dma_data_in(l_data), 
        .dma_local_we_n(dma_local_we_n), .dma_local_oe_n(dma_local_oe_n),
        .shd_en_n(shadow_en_n), .shd_rw_n(shd_rw_n), .shd_inc_n(shd_inc_n),
        .shd_stb_n(shd_stb_n), .shd_done_n(shd_done_n),
        .dma_active(dma_is_active), .shd_c_dir(shd_c_dir), .dma_dir_to_bus(dma_dir_to_bus),
        .int_pending(dma_int_pending), .intack_clear(intack_clear)
    );

    // ==========================================
    // 5. Memory & LUT Takeover Multiplexing
    // ==========================================
    
    // Address Multiplexing
    assign l_addr = z80_grant ? z80_addr[10:0] : (dma_is_active ? dma_phys_addr[10:0] : 11'bz);

    // LUT Power Control:
    // The LUT must be put to sleep during a DMA burst so it releases the atl_data bus.
    assign atl_ce_n = dma_is_active ? 1'b1 : !(internal_z80_card_hit || mmu_busy); 

    // Repurposing the atl_data traces:
    // When the Z80 writes to the MMU, the core routes l_data into the LUT.
    // When the DMA is active, the core drives the 20-bit physical address upper bytes out to the SRAMs.
    assign atl_data = dma_is_active ? dma_phys_addr[18:11] : (!atl_we_n ? l_data : 8'hzz);

    // Bank Selection: Bit 19 from DMA overrides Bit 7 from the LUT
    wire bank_select = dma_is_active ? dma_phys_addr[19] : atl_data[7];
    
    // Safety Interlock: Only fire the Main Cypress SRAMs for actual memory cycles.
    // 'internal_z80_card_hit' naturally ignores INTACK cycles, preventing SRAM corruption.
    wire safe_to_access_ram = dma_is_active || (internal_z80_card_hit && atl_we_n);
    
    assign ce0_n = (safe_to_access_ram && bank_select == 1'b0) ? 1'b0 : 1'b1;
    assign ce1_n = (safe_to_access_ram && bank_select == 1'b1) ? 1'b0 : 1'b1;

    // Route WE/OE based on who currently owns the local card bus
    assign ram_oe_n = dma_is_active ? dma_local_oe_n : (z80_grant ? z80_rd_n : 1'b1);
    assign ram_we_n = dma_is_active ? dma_local_we_n : (z80_grant ? z80_wr_n : 1'b1);

    // The Interrupt Vector is the Base Port (0x40) OR'd with the Card ID
    wire [7:0] interrupt_vector = 8'h40 | latched_id;

    // Only drive l_data actively from the CPLD if we are returning an Interrupt Vector.
    // During a DMA burst, the Shadow Transceivers handle getting data to/from the SRAM.
    assign l_data = responding_to_intack ? interrupt_vector : 8'hzz;

    // ==========================================
    // 6. Backplane Controls
    // ==========================================
    
    assign shd_c_oe_n = 1'b0; // Shadow control transceiver is always active
    assign shd_busy_n = (!dma_is_active && !arbiter_shd_busy_n) ? 1'b0 : 1'bz;

endmodule