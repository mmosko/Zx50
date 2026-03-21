`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_mem_card (Rev 1.0 - Clean Hardware)
 * =====================================================================================
 * DESCRIPTION:
 * The absolute top-level integration module. This is a 1-to-1 "Digital Twin" of the 
 * physical PCB schematic. It instantiates the CPLD logic core, the SRAM chips, 
 * the Flash ROM, and the physical bus transceivers, wiring them all together to 
 * simulate the complete hardware card.
 *
 * MEMORY ARCHITECTURE (CLEAN 4K PAGING):
 * - Local Address (`l_addr[11:0]`): Provides the 4KB physical page offset directly 
 * to the memory ICs.
 * - Translation Data (`atl_data[7:0]`): The lower 7 bits provide physical address 
 * bits [18:12]. Bit [7] acts as the logical bank select to toggle between `ram0` 
 * and `ram1` inside the CPLD.
 * - The physical address passed to the memory ICs is formed by concatenating 
 * `atl_data[6:0]` with `l_addr[11:0]`, creating a linear 19-bit (512KB) space.
 ***************************************************************************************/

module zx50_mem_card (
    input  wire mclk,
    input  wire reset_n,
    input  wire [3:0] card_id_sw, // Hardware DIP switches

    // --- Z80 Backplane ---
    input  wire [15:0] z80_addr,
    inout  wire [7:0]  z80_data,
    input  wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n,
    input  wire z80_iei,
    output wire z80_ieo,
    inout  wire z80_wait_n, z80_int_n,

    // --- Shadow Bus ---
    inout  wire [15:0] sh_addr,
    inout  wire [7:0]  sh_data,
    inout  wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n
);

    // ==========================================
    // Internal Card Wires (PCB Traces)
    // ==========================================
    wire [11:0] l_addr;       // Lower 12 bits (4K offset)
    wire [7:0]  l_data;       // Local shared data bus
    
    wire [3:0]  atl_addr;     // ATL SRAM Address
    wire [7:0]  atl_data;     // ATL SRAM Data (Also acts as upper 8 bits of physical address)
    
    // Control lines
    wire atl_we_n, atl_oe_n, atl_ce_n;
    wire ram_ce0_n, ram_ce1_n, rom_ce_n;
    wire ram_oe_n, ram_we_n;
    
    wire z80_data_oe_n, sh_data_oe_n, l_dir, sh_c_dir;

    // The physical 19-bit address bus for the RAM and ROM chips (512KB max per IC)
    // atl_data[7] is consumed by the CPLD as a chip select, so only [6:0] are passed to the ICs
    wire [18:0] phys_addr = {atl_data[6:0], l_addr[11:0]};

    // ==========================================
    // CPLD Core
    // ==========================================
    // Note: The Duplex bus multiplexes the control signals with the DIP switches during reset.
    wire [3:0] duplex_bus = (!reset_n) ? card_id_sw : {z80_iorq_n, z80_mreq_n, z80_wr_n, z80_rd_n};

    zx50_cpld_core cpld (
        .mclk(mclk), .reset_n(reset_n),
        .duplex_in(duplex_bus),
        .z80_m1_n(z80_m1_n), .z80_iei(z80_iei), .z80_ieo(z80_ieo),
        .z80_int_n(z80_int_n), .z80_wait_n(z80_wait_n),
        
        .z80_addr(z80_addr), .l_data(l_data),
        
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n),
        
        .sh_c_dir(sh_c_dir), .z80_data_oe_n(z80_data_oe_n), .sh_data_oe_n(sh_data_oe_n), .l_dir(l_dir),
        
        .l_addr(l_addr), .atl_addr(atl_addr), .atl_data(atl_data),
        
        .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n), .atl_ce_n(atl_ce_n),
        .ram_ce0_n(ram_ce0_n), .ram_ce1_n(ram_ce1_n), .rom_ce_n(rom_ce_n),
        .ram_oe_n(ram_oe_n), .ram_we_n(ram_we_n)
    );

    // ==========================================
    // Physical Memory ICs
    // ==========================================
    
    // 1. Address Translation Lookaside (ATL) SRAM - IS61C256AL (32KB)
    is61c256al lut_sram (
        .addr({11'b0, atl_addr}), // Padded to fit 15-bit address
        .data(atl_data),
        .ce_n(atl_ce_n), .oe_n(atl_oe_n), .we_n(atl_we_n)
    );

    // 2. Main RAM 0 - CY7C1049 (512KB)
    cy7c1049 ram0 (
        .addr(phys_addr), .data(l_data),
        .ce_n(ram_ce0_n), .oe_n(ram_oe_n), .we_n(ram_we_n)
    );

    // 3. Main RAM 1 - CY7C1049 (512KB)
    cy7c1049 ram1 (
        .addr(phys_addr), .data(l_data),
        .ce_n(ram_ce1_n), .oe_n(ram_oe_n), .we_n(ram_we_n)
    );

    // 4. Boot ROM - SST39SF040 (512KB)
    sst39sf040 rom (
        .addr(phys_addr), .data(l_data),
        .ce_n(rom_ce_n), .oe_n(ram_oe_n), .we_n(ram_we_n)
    );

    // ==========================================
    // Transceiver Emulation (74ABT245 / 74LVC245)
    // ==========================================
    
    // Z80 Data Bus Transceiver (Controlled by l_dir)
    // l_dir = 1: Z80 -> Local Bus (Write)
    // l_dir = 0: Local Bus -> Z80 (Read)
    assign l_data   = (!z80_data_oe_n && l_dir == 1'b1) ? z80_data : 8'hzz;
    assign z80_data = (!z80_data_oe_n && l_dir == 1'b0) ? l_data   : 8'hzz;

    // Shadow Data Bus Transceiver (Controlled by sh_c_dir)
    // sh_c_dir = 1: Local Bus -> Shadow Bus (Master driving)
    // sh_c_dir = 0: Shadow Bus -> Local Bus (Slave listening)
    assign sh_data  = (!sh_data_oe_n && sh_c_dir == 1'b1) ? l_data  : 8'hzz;
    assign l_data   = (!sh_data_oe_n && sh_c_dir == 1'b0) ? sh_data : 8'hzz;

endmodule