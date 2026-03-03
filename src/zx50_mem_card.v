`timescale 1ns/1ps

module zx50_mem_card (
    // --- System Backplane ---
    input wire mclk, reset_n, boot_en_n,
    input wire [3:0] card_id_sw, // Local DIP switch

    // --- Z80 Backplane Bus ---
    input  wire [15:0] z80_addr,
    inout  wire [7:0]  z80_data,
    input  wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n,
    output wire z80_wait_n,

    // --- Shadow DMA Backplane Bus ---
    input  wire [15:0] shd_addr,
    inout  wire [7:0]  shd_data,
    input  wire shd_en_n, shd_rw_n,
    output wire shd_busy_n
);

    // ==========================================
    // INTERNAL PCB TRACES (The Local Bus)
    // ==========================================
    wire [15:0] l_addr;
    wire [7:0]  l_data;
    wire l_mreq_n, l_wr_n, l_rd_n;
    
    // CPLD Controls
    wire z80_addr_oe_n, z80_data_oe_n, z80_data_dir;
    wire shd_addr_oe_n, shd_data_oe_n, shd_data_dir;
    wire atl_we_n, atl_oe_n, ce0_n, ce1_n;
    wire [3:0] atl_addr;
    wire [7:0] atl_data; // Physical Address from ATL LUT

    // ==========================================
    // 1. HARDWARE TRANSCEIVERS (74ABT244 / 245)
    // ==========================================
    
    // Z80 Data Transceiver (DIR = 1: Z80 -> Local, DIR = 0: Local -> Z80)
    assign l_data   = (!z80_data_oe_n && z80_data_dir)  ? z80_data : 8'hzz;
    assign z80_data = (!z80_data_oe_n && !z80_data_dir) ? l_data   : 8'hzz;

    // Z80 Address & Control Transceiver (One-Way: Z80 -> Local)
    assign l_addr   = (!z80_addr_oe_n) ? z80_addr   : 16'hzzzz;
    assign l_mreq_n = (!z80_addr_oe_n) ? z80_mreq_n : 1'bz;
    assign l_wr_n   = (!z80_addr_oe_n) ? z80_wr_n   : 1'bz;
    assign l_rd_n   = (!z80_addr_oe_n) ? z80_rd_n   : 1'bz;

    // Shadow Data Transceiver
    assign l_data   = (!shd_data_oe_n && shd_data_dir)  ? shd_data : 8'hzz;
    assign shd_data = (!shd_data_oe_n && !shd_data_dir) ? l_data   : 8'hzz;

    // Shadow Address & Control Transceiver (One-Way: Shadow -> Local)
    assign l_addr   = (!shd_addr_oe_n) ? shd_addr : 16'hzzzz;
    
    // Note: DMA usually implies memory access, so we fake local MREQ low when shadow is enabled
    assign l_mreq_n = (!shd_addr_oe_n) ? 1'b0     : 1'bz; 
    assign l_wr_n   = (!shd_addr_oe_n) ? shd_rw_n : 1'bz; // shd_rw_n = 0 is Write
    assign l_rd_n   = (!shd_addr_oe_n) ? !shd_rw_n: 1'bz; // shd_rw_n = 1 is Read


    // ==========================================
    // 2. THE CPLD (ATF1508)
    // ==========================================
    zx50_cpld_core cpld (
        .mclk(mclk), .reset_n(reset_n), .boot_en_n(boot_en_n), .card_id_sw(card_id_sw),
        .z80_addr(z80_addr), .z80_data(z80_data), .z80_mreq_n(z80_mreq_n), 
        .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_rd_n(z80_rd_n),
        .shadow_en_n(shd_en_n), .shd_rw_n(shd_rw_n),
        .z80_wait_n(z80_wait_n), .shd_busy_n(shd_busy_n),
        
        // Local Bus Interactions
        .l_addr(l_addr),
        .atl_addr(atl_addr), .atl_data(atl_data), .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n),
        .ce0_n(ce0_n), .ce1_n(ce1_n),
        
        // Transceiver Controls
        .z80_addr_oe_n(z80_addr_oe_n), .z80_data_oe_n(z80_data_oe_n), .z80_data_dir(z80_data_dir),
        .shd_addr_oe_n(shd_addr_oe_n), .shd_data_oe_n(shd_data_oe_n), .shd_data_dir(shd_data_dir)
    );

    // ==========================================
    // 3. ISSI SRAM (The ATL Lookup Table)
    // ==========================================
    reg [7:0] issi_ram [0:15];
    
    // Write cycle: latch data shortly after WE goes low
    always @(negedge atl_we_n) begin
        #5 issi_ram[atl_addr] <= atl_data; // Mock 10ns delay for write
    end
    
    // Read cycle: ISSI drives physical address onto local atl_data traces
    assign #12 atl_data = (!atl_oe_n && atl_we_n) ? issi_ram[atl_addr] : 8'hzz;


    // ==========================================
    // 4. CYPRESS SRAMs (The Main Memory)
    // ==========================================
    // Assemble the 19-bit physical address from the local bus and ATL output
    wire [18:0] physical_addr = {atl_data[6:0], l_addr[11:0]};

    zx50_mem main_ram (
        .addr(physical_addr),
        .data(l_data),       // Local data bus (post-transceivers)
        .ce0_n(ce0_n),       // Driven directly by CPLD
        .ce1_n(ce1_n),       // Driven directly by CPLD
        .oe_n(l_rd_n),       // Local Read strobe (from Z80 or Shadow)
        .we_n(l_wr_n)        // Local Write strobe (from Z80 or Shadow)
    );

endmodule