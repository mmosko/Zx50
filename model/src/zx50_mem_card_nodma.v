`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_mem_card_nodma
 * DESCRIPTION:
 * [REVISION: "No-DMA" Digital Twin. Matches the physical incoming PCB but with 
 * the Shadow Bus and DMA components explicitly disabled/unpopulated.]
 * * The absolute top-level integration module. This is a 1-to-1 "Digital Twin" of the 
 * physical PCB schematic[cite: 708].
 ***************************************************************************************/

module zx50_mem_card_nodma (
    input wire mclk,            
    input wire reset_n,               
    input wire [3:0] card_id_sw,

    // --- Z80 Backplane Interface ---
    input  wire [15:0] z80_addr,
    inout  wire [7:0]  z80_data,
    input  wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n,
    input  wire z80_m1_n, z80_iei, 
    output wire z80_wait_n, z80_ieo, z80_int_n
    
    // [REVISION: Shadow DMA Backplane Interface (sh_addr, sh_data, etc.) omitted from 
    // the NoDMA card emulation entirely to prevent testbench confusion.]
);

    // --- Internal Local Bus Wires (The copper traces on the PCB) ---
    wire [10:0] l_addr_low;
    wire [7:0]  l_data;         
    wire [3:0]  atl_addr;       // 4 bits for 16 pages   
    wire [7:0]  atl_data;
    
    // --- Transceiver & Memory Control Wires ---
    wire z80_data_oe_n, l_dir;
    wire atl_we_n, atl_oe_n, atl_ce_n;
    wire ram_ce0_n, ram_ce1_n, ram_oe_n, ram_we_n;

    // ==========================================
    // 1. DUPLEXED CONFIG/RUN-TIME BUS HANDOFF
    // ==========================================
    // Simulates the physical hardware multiplexing of the config switches 
    // and the Z80 control lines sharing the same CPLD input pins[cite: 715].
    wire [3:0] duplex_bus = (reset_n) ? {z80_iorq_n, z80_mreq_n, z80_wr_n, z80_rd_n} : card_id_sw;

    // ==========================================
    // 2. PHYSICAL TRANSCEIVER EMULATION
    // ==========================================
    
    // Z80 Data Transceiver (74ABT245)
    // l_dir=1 (A to B / Z80 to L_Data), l_dir=0 (B to A / L_Data to Z80)
    ic_74abt245 z80_data_xcvr (
        .a(z80_data), .b(l_data), 
        .dir(l_dir), .oe_n(z80_data_oe_n)
    );

    // [REVISION: Shadow Data and Control Transceivers unpopulated/removed for NoDMA]

    // ==========================================
    // 3. EXTERNAL LUT SRAM (ISSI Emulation)
    // ==========================================
    
    // The CPLD traces driving the data bus to the LUT during programming
    assign atl_data = (!atl_we_n) ? l_data : 8'hzz;

    // The IS61C256AL chip itself (Requires 15-bit address, so we pad the 4-bit bus)
    wire [14:0] issi_addr = {11'b0, atl_addr};
    is61c256al lut_sram (
        .addr(issi_addr),
        .data(atl_data),
        .ce_n(atl_ce_n),
        .oe_n(atl_oe_n),
        .we_n(atl_we_n)
    );

    // ==========================================
    // 4. CPLD CORE INSTANTIATION
    // ==========================================
    // [REVISION: Pointing to the new zx50_cpld_nodma module]
    zx50_cpld_nodma core (
        .mclk(mclk), .reset_n(reset_n), .duplex_in(duplex_bus),
        .z80_m1_n(z80_m1_n), .z80_iei(z80_iei), .z80_ieo(z80_ieo),
        .z80_int_n(z80_int_n), .z80_wait_n(z80_wait_n),
        .z80_addr(z80_addr), .l_data(l_data),
        
        .l_addr(l_addr_low), .atl_addr(atl_addr), .atl_data(atl_data),
        .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n), .atl_ce_n(atl_ce_n),
        .ram_ce0_n(ram_ce0_n), .ram_ce1_n(ram_ce1_n), .ram_oe_n(ram_oe_n), .ram_we_n(ram_we_n),

        .z80_data_oe_n(z80_data_oe_n), .l_dir(l_dir)
    );

    // ==========================================
    // 5. CYPRESS MAIN SRAM EMULATION
    // ==========================================
    
    wire [18:0] physical_addr = {atl_data[7:0], l_addr_low};
    
    // Bank 0 (Lower 512KB)
    cy7c1049 bank0 (
        .addr(physical_addr), 
        .data(l_data),
        .ce_n(ram_ce0_n), 
        .oe_n(ram_oe_n), 
        .we_n(ram_we_n)
    );

    // Bank 1 (Upper 512KB)
    cy7c1049 bank1 (
        .addr(physical_addr), 
        .data(l_data),
        .ce_n(ram_ce1_n), 
        .oe_n(ram_oe_n), 
        .we_n(ram_we_n)
    );

endmodule