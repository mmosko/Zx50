`timescale 1ns/1ps

module zx50_cpld_core (
    // --- System & Config ---
    input wire mclk, reset_n, boot_en_n,
    input wire [3:0] card_id_sw,

    // --- Backplane Snoop Inputs ---
    input wire [15:0] z80_addr,
    input wire [7:0]  z80_data,
    input wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n,
    input wire shadow_en_n, shd_rw_n,
    
    // --- Wait/Busy Generators (To Backplane) ---
    output wire z80_wait_n,
    output wire shd_busy_n,

    // --- Local Hardware Bus ---
    input  wire [15:0] l_addr,      // Local address bus (driven by transceivers)
    
    // --- Address Translation Table (ATL) Controls ---
    output wire [3:0] atl_addr,     // To ISSI SRAM
    inout  wire [7:0] atl_data,     // To ISSI SRAM (Data / Physical Address)
    output wire atl_we_n, atl_oe_n,
    
    // --- Main Memory Controls ---
    output wire ce0_n, ce1_n,       // To Cypress SRAMs

    // --- Transceiver Controls ---
    output wire z80_addr_oe_n, z80_data_oe_n, z80_data_dir,
    output wire shd_addr_oe_n, shd_data_oe_n, shd_data_dir
);

    wire internal_z80_card_hit;
    wire internal_active;

    // ==========================================
    // 1. Instantiate the MMU & ATL Controller
    // ==========================================
    zx50_mmu_sram mmu_unit (
        .mclk(mclk), 
        .z80_addr(z80_addr), 
        .l_addr(l_addr), 
        .z80_data(z80_data), 
        .z80_iorq_n(z80_iorq_n), 
        .z80_wr_n(z80_wr_n), 
        .z80_mreq_n(z80_mreq_n), 
        .reset_n(reset_n), 
        .boot_en_n(boot_en_n),
        .card_id_sw(card_id_sw),

        // ATL Outputs
        .atl_addr(atl_addr), 
        .atl_data(atl_data), 
        .atl_we_n(atl_we_n), 
        .atl_oe_n(atl_oe_n),
        .p_addr_hi(), // Floated. atl_data physically provides this to the board!
        .active(internal_active),
        .z80_card_hit(internal_z80_card_hit)
    );

    // ==========================================
    // 2. Instantiate the Bus Arbiter
    // ==========================================
    zx50_bus_arbiter arbiter_unit (
        .mclk(mclk), 
        .reset_n(reset_n),
        .shadow_en_n(shadow_en_n), 
        .z80_card_hit(internal_z80_card_hit), 
        .z80_rd_n(z80_rd_n), 
        .shd_rw_n(shd_rw_n),
        
        .z80_wait_n(z80_wait_n), 
        .shd_busy_n(shd_busy_n),
        .z80_addr_oe_n(z80_addr_oe_n), 
        .z80_data_oe_n(z80_data_oe_n), 
        .z80_data_dir(z80_data_dir),
        .shd_addr_oe_n(shd_addr_oe_n), 
        .shd_data_oe_n(shd_data_oe_n), 
        .shd_data_dir(shd_data_dir)
    );

    // ==========================================
    // 3. Cypress Chip Enables (ce0_n, ce1_n)
    // ==========================================
    wire local_bus_active = ((!z80_addr_oe_n && internal_active) || !shd_addr_oe_n);

    // Safety interlock: Don't wake Cypress chips while CPLD is writing to the ATL LUT!
    wire safe_to_read = local_bus_active && atl_we_n;

    // atl_data[7] acts as our physical address bit A19.
    assign ce0_n = (safe_to_read && atl_data[7] === 1'b0) ? 1'b0 : 1'b1;
    assign ce1_n = (safe_to_read && atl_data[7] === 1'b1) ? 1'b0 : 1'b1;

endmodule