`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_cpld_core
 * DESCRIPTION:
 * The top-level CPLD logic that integrates the MMU, Z80 Arbiter, and DMA.
 * It is responsible for extremely strict multiplexing of the physical IC pins, 
 * ensuring that the Z80, the SRAM chips, and the Backplane transceivers never 
 * contend with each other. 
 * * NOTE: The Shadow Bus and Z80 backplane share a single data transceiver direction pin, 
 * controlled by l_dir.
 ***************************************************************************************/

module zx50_cpld_core (
    (* LOC="P87" *) input  wire mclk,
    (* LOC="P89" *) input  wire reset_n,
    (* LOC="P88" *) input  wire boot_en_n,
    
    // --- Duplex/Control Bus (MSB to LSB: IORQ, MREQ, WR, RD) ---
    (* LOC="P40,P37,P35,P33" *) input  wire [3:0] duplex_in, 
    
    // --- Z80 Backplane ---
    (* LOC="P41" *) input  wire z80_m1_n,       
    (* LOC="P42" *) input  wire z80_iei,        
    (* LOC="P36" *) output wire z80_ieo,        
    (* LOC="P96" *) inout  wire z80_int_n,      
    (* LOC="P97" *) inout  wire z80_wait_n,     
    
    // Z80 Address Bus (A15 down to A0)
    (* LOC="P21,P20,P19,P17,P16,P14,P13,P12,P10,P9,P8,P7,P6,P5,P2,P1" *) 
    input  wire [15:0] z80_addr, 
    
    // --- Local Shared Bus (D7 down to D0) ---
    (* LOC="P32,P31,P30,P29,P28,P27,P25,P24" *) 
    inout  wire [7:0] l_data, 
    
    // --- Shadow Bus Controls (Bidirectional) ---
    (* LOC="P47" *) inout  wire sh_en_n, 
    (* LOC="P48" *) inout  wire sh_rw_n, 
    (* LOC="P46" *) inout  wire sh_inc_n, 
    (* LOC="P45" *) inout  wire sh_stb_n, 
    (* LOC="P49" *) inout  wire sh_done_n, 
    (* LOC="P50" *) inout  wire sh_busy_n, 
    
    // --- Transceiver Controls ---
    (* LOC="P44" *) output wire sh_c_dir,         
    (* LOC="P23" *) output wire z80_data_oe_n, 
    (* LOC="P52" *) output wire sh_data_oe_n,
    (* LOC="P22" *) output wire l_dir,
    
    // --- Local Memory & LUT Routing ---
    // Local Address Bus (A10 down to A0)
    (* LOC="P85,P84,P83,P81,P80,P79,P78,P77,P76,P75,P72" *) 
    output wire [10:0] l_addr,  
    
    // ATL Address Bus (A4 down to A0)
    (* LOC="P57,P56,P55,P54,P53" *) 
    output wire [4:0]  atl_addr, 
    
    // ATL Data Bus (D7 down to D0)
    (* LOC="P68,P67,P65,P64,P63,P61,P60,P58" *) 
    inout  wire [7:0]  atl_data, 
    
    (* LOC="P69" *) output wire atl_we_n, 
    (* LOC="P70" *) output wire atl_oe_n, 
    (* LOC="P71" *) output wire atl_ce_n,
    (* LOC="P90" *) output wire ram_ce0_n, 
    (* LOC="P92" *) output wire ram_ce1_n,
    (* LOC="P93" *) output wire ram_oe_n,
    (* LOC="P94" *) output wire ram_we_n           
);

    // ==========================================
    // 1. DUPLEX CONFIGURATION LATCH
    // ==========================================
    reg [3:0] latched_id;   
    wire z80_rd_n   = duplex_in[0]; 
    wire z80_wr_n   = duplex_in[1]; 
    wire z80_mreq_n = duplex_in[2]; 
    wire z80_iorq_n = duplex_in[3]; 

    // Synchronously latch the Card ID while the system is in reset.
    // Once reset_n goes high (normal operation), latched_id locks and holds its value.
    always @(posedge mclk) begin
        if (!reset_n) begin
            latched_id <= duplex_in; 
        end
    end

    // ==========================================
    // 2. INTERNAL SUBSYSTEM WIRES & HIT LOGIC
    // ==========================================
    wire internal_active, mmu_busy;
    wire mmu_cpu_updating, mmu_is_initializing;
    wire [3:0] mmu_init_ptr;
    
    wire active_bus_cycle = !z80_mreq_n || !z80_iorq_n;
    wire mmu_card_hit;
    wire qualified_mmu_hit = mmu_card_hit && active_bus_cycle;
    wire dma_card_hit = (!z80_iorq_n && (z80_addr[7:0] == (8'h40 | latched_id)));
    wire internal_z80_card_hit = qualified_mmu_hit | dma_card_hit;

    wire arbiter_sh_busy_n;
    wire arbiter_l_dir; 
    wire arbiter_z80_data_oe_n;
    wire arbiter_sh_data_oe_n; 
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

    wire safe_sh_en_n = dma_is_active ? sh_en_n : 1'b1;

    zx50_bus_arbiter arbiter_unit (
        .mclk(mclk), .reset_n(reset_n),
        .sh_en_n(safe_sh_en_n), 
        .z80_card_hit(arbiter_hit), 
        .z80_wait_n(arbiter_wait_n), .sh_busy_n(arbiter_sh_busy_n), 
        .z80_rd_n(arbiter_rd_n), .sh_rw_n(sh_rw_n),
        .z80_data_oe_n(arbiter_z80_data_oe_n), 
        .sh_data_oe_n(arbiter_sh_data_oe_n), 
        .l_dir(arbiter_l_dir)                  
    );

    wire safe_z80_iorq_n = dma_is_active ? 1'b1 : z80_iorq_n;

    zx50_mmu_sram mmu_unit (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(latched_id), 
        .z80_addr(z80_addr), .l_addr_hi(z80_addr[15:12]), 
        .l_data(l_data), .z80_iorq_n(safe_z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_mreq_n(z80_mreq_n), 
        .atl_addr(atl_addr), .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n),
        .active(internal_active),
        .cpu_updating(mmu_cpu_updating),
        .is_initializing(mmu_is_initializing),
        .init_ptr(mmu_init_ptr), 
        .z80_card_hit(mmu_card_hit), 
        .is_busy(mmu_busy) 
    );

    zx50_dma dma_unit (
        .mclk(mclk), .reset_n(reset_n), .card_id(latched_id),
        .z80_addr(z80_addr), .z80_data_in(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n),
        .dma_phys_addr(dma_phys_addr), .dma_data_out(), .dma_data_in(l_data), 
        .dma_local_we_n(dma_local_we_n), .dma_local_oe_n(dma_local_oe_n),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), 
        .sh_busy_n(sh_busy_n), 
        .dma_active(dma_is_active), .sh_c_dir(sh_c_dir), .dma_dir_to_bus(dma_dir_to_bus),
        .dma_is_master(dma_is_master), .int_pending(dma_int_pending), .intack_clear(intack_clear)
    );

    // ==========================================
    // 5. LOCAL MEMORY & LUT TAKEOVER MULTIPLEXING
    // ==========================================
        // Do not float the address lines, zero them if not being used
    assign l_addr = z80_grant ? z80_addr[10:0] : (dma_is_active ? dma_phys_addr[10:0] : 11'b0);

    assign atl_ce_n = dma_is_active ? 1'b1 : !(internal_z80_card_hit || mmu_busy); 
    assign atl_data = mmu_is_initializing ? {4'h0, mmu_init_ptr} :
                      mmu_cpu_updating    ? l_data :
                      dma_is_active       ? {3'b000, dma_phys_addr[19:15]} :
                      8'hzz;

    wire bank_select = dma_is_active ? dma_phys_addr[19] : atl_data[7];
    wire safe_to_access_ram = dma_is_active || (internal_z80_card_hit && atl_we_n && memory_cycle);
    
    assign ram_ce0_n = (safe_to_access_ram && bank_select == 1'b0) ? 1'b0 : 1'b1;
    assign ram_ce1_n = (safe_to_access_ram && bank_select == 1'b1) ? 1'b0 : 1'b1;

    assign ram_oe_n = dma_is_active ? dma_local_oe_n : ((z80_grant && memory_cycle) ? z80_rd_n : 1'b1);
    assign ram_we_n = dma_is_active ? dma_local_we_n : ((z80_grant && memory_cycle) ? z80_wr_n : 1'b1);

    wire [7:0] interrupt_vector = 8'h40 | latched_id;
    assign l_data = responding_to_intack ? interrupt_vector : 8'hzz;

    // ==========================================
    // 6. CYCLE STEALING: INTERCEPT & OVERRIDE LOGIC
    // ==========================================
    assign z80_wait_n = ((arbiter_hit && dma_is_active) || arbiter_wait_n == 1'b0) ? 1'b0 : 1'bz;
    
    // Transceiver Multiplexing
    assign sh_data_oe_n  = dma_is_active ? 1'b0 : arbiter_sh_data_oe_n; 
    assign z80_data_oe_n = dma_is_active ? 1'b1 : arbiter_z80_data_oe_n;
    
    assign sh_busy_n = (arbiter_hit && dma_is_active) ? 1'b0 : 1'bz;
    assign l_dir = dma_is_active ? dma_dir_to_bus : arbiter_l_dir;

endmodule