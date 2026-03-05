`timescale 1ns/1ps

module zx50_mem_card (
    input wire mclk,            
    input wire reset_n,         
    input wire boot_en_n,       
    input wire [3:0] card_id_sw,

    // --- Z80 Backplane Interface ---
    input  wire [15:0] z80_addr,
    inout  wire [7:0]  z80_data,
    input  wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n,
    input  wire z80_m1_n, z80_iei, 
    output wire z80_wait_n, z80_ieo, z80_int_n,

    // --- Shadow DMA Backplane Interface ---
    inout  wire [15:0] shd_addr,
    inout  wire [7:0]  shd_data,
    inout  wire shd_en_n, shd_rw_n, shd_inc_n, shd_stb_n, shd_done_n, shd_busy_n
);

    // --- Internal Local Bus Wires ---
    wire [10:0] l_addr_low;     // CPLD Firewall Address
    wire [7:0]  l_data;         // The One True Shared Local Data Bus
    wire [3:0]  atl_addr;       
    wire [7:0]  atl_data;       
    
    // --- Transceiver Control Wires ---
    wire z80_data_oe_n, shd_data_oe_n, d_dir;
    wire atl_we_n, atl_oe_n, atl_ce_n, ce0_n, ce1_n, ram_oe_n, ram_we_n;
    wire shd_c_dir, shd_c_oe_n;

    // ==========================================
    // 1. DUPLEXED CONFIG/RUN-TIME BUS HANDOFF
    // ==========================================
    wire [3:0] duplex_bus;
    assign duplex_bus = (reset_n) ? {z80_iorq_n, z80_mreq_n, z80_wr_n, z80_rd_n} : card_id_sw;

    // ==========================================
    // 2. PHYSICAL TRANSCEIVER EMULATION
    // ==========================================
    
    // Z80 Data Transceiver (74ABT245)
    // DIR: 0 = Card to Bus (Read), 1 = Bus to Card (Write)
    assign l_data   = (!z80_data_oe_n && d_dir)  ? z80_data : 8'hzz;
    assign z80_data = (!z80_data_oe_n && !d_dir) ? l_data   : 8'hzz;

    // Shadow Data Transceiver (74ABT245)
    assign l_data   = (!shd_data_oe_n && d_dir)  ? shd_data : 8'hzz;
    assign shd_data = (!shd_data_oe_n && !d_dir) ? l_data   : 8'hzz;

    // Shadow Control Transceiver ('245)
    // dma_active causes CPLD to drive OUT (shd_c_dir=0)
    assign {shd_en_n, shd_rw_n, shd_inc_n, shd_stb_n, shd_done_n} = 
           (!shd_c_oe_n && !shd_c_dir) ? 5'bz : 5'bz; // Logic handled in Core

    // ==========================================
    // 3. EXTERNAL LUT SRAM (ISSI Emulation)
    // ==========================================
    reg [7:0] issi_ram [0:15];
    always @(negedge atl_we_n) begin
        if (!atl_ce_n) #5 issi_ram[atl_addr] <= atl_data;
    end
    assign #12 atl_data = (!atl_oe_n && atl_we_n && !atl_ce_n) ? issi_ram[atl_addr] : 8'hzz;

    // ==========================================
    // 4. CPLD CORE INSTANTIATION
    // ==========================================
    zx50_cpld_core core (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .duplex_in(duplex_bus),
        .z80_m1_n(z80_m1_n), .z80_iei(z80_iei), .z80_ieo(z80_ieo),
        .z80_int_n(z80_int_n), .z80_wait_n(z80_wait_n),
        .z80_addr(z80_addr), .l_data(l_data),
        
        .shadow_en_n(shd_en_n), .shd_rw_n(shd_rw_n), .shd_inc_n(shd_inc_n),
        .shd_stb_n(shd_stb_n), .shd_done_n(shd_done_n), .shd_busy_n(shd_busy_n),
        .shd_c_dir(shd_c_dir), .shd_c_oe_n(shd_c_oe_n),

        .l_addr(l_addr_low), .atl_addr(atl_addr), .atl_data(atl_data),
        .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n), .atl_ce_n(atl_ce_n),
        .ce0_n(ce0_n), .ce1_n(ce1_n), .ram_oe_n(ram_oe_n), .ram_we_n(ram_we_n),

        .z80_data_oe_n(z80_data_oe_n), .shd_data_oe_n(shd_data_oe_n), .d_dir(d_dir)
    );

    // ==========================================
    // 5. CYPRESS MAIN SRAM EMULATION
    // ==========================================
    
    // We combine 11 bits from CPLD and 8 bits from the LUT to get 19 bits.
    // atl_data[7] is STILL used for CE logic, but here we treat the LUT
    // as providing the full upper half of the 19-bit physical chip address.
    wire [18:0] physical_addr = {atl_data[7:0], l_addr_low};
    
zx50_mem main_ram (
        .addr(physical_addr), 
        .data(l_data),
        .ce0_n(ce0_n), 
        .ce1_n(ce1_n),
        .oe_n(ram_oe_n), 
        .we_n(ram_we_n)
    );

endmodule