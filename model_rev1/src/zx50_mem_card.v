`timescale 1ns/1ps

module zx50_mem_card #(
    parameter [3:0] CARD_ID = 4'h0,
    parameter       BOOT_EN = 1'b1
)(
    input  wire        mclk,
    input  wire        zclk,
    input  wire        reset_n,
    
    // Z80 Backplane
    input  wire [15:0] z80_a,
    inout  wire [7:0]  z80_d,
    input  wire        z80_mreq_n,
    input  wire        z80_iorq_n,
    input  wire        z80_rd_n,
    input  wire        z80_wr_n,
    input  wire        z80_m1_n,

    output wire        wait_n,
    output wire        int_n
);

    // ==========================================
    // Local PCB Traces
    // ==========================================
    wire [7:0]  l_d;        // Local Data Bus
    wire [10:0] l_a;        // Local Address Bus (Lower 11 bits bypass ATL)
    
    wire [7:0]  atl_d;      // ATL Data Output (Physical Page)
    wire [3:0]  atl_a;      // ATL Address Input (Logical Page)
    
    wire z80_d_oe_n, d_dir;
    wire oe_n, we_n;
    wire atl_ce_n, atl_oe_n, atl_we_n;
    wire ram_ce0_n, ram_ce1_n, rom_ce2_n;
    
    wire b_z80_mreq_n = (!reset_n) ? CARD_ID[3] : z80_mreq_n;
    wire b_z80_iorq_n = (!reset_n) ? CARD_ID[2] : z80_iorq_n;
    wire b_z80_rd_n   = (!reset_n) ? CARD_ID[1] : z80_rd_n;
    wire b_z80_wr_n   = (!reset_n) ? CARD_ID[0] : z80_wr_n;
    wire b_z80_m1_n   = (!reset_n) ? 1'bz : z80_m1_n;


    // ==========================================
    // U1: 74ABT245 Data Bus Transceiver
    // ==========================================
    ic_74abt245 transceiver (
        .a(z80_d), 
        .b(l_d), 
        .dir(d_dir),        // 1 = Z80 to Card, 0 = Card to Z80
        .oe_n(z80_d_oe_n)
    );

    // ==========================================
    // U2: CPLD (Memory Controller)
    // ==========================================
    zx50_mem_control cpld (
        .mclk(mclk), .zclk(zclk),
        .reset_n(reset_n), .boot_en_n(BOOT_EN),
        
        .z80_a(z80_a),
        .b_z80_mreq_n(b_z80_mreq_n), .b_z80_iorq_n(b_z80_iorq_n),
        .b_z80_rd_n(b_z80_rd_n), .b_z80_wr_n(b_z80_wr_n), .b_z80_m1_n(b_z80_m1_n),
        .wait_n(wait_n), .int_n(int_n),
        
        .z80_d_oe_n(z80_d_oe_n), .d_dir(d_dir),
        .l_d(l_d), .l_a(l_a),
        
        .oe_n(oe_n), .we_n(we_n),
        .ram_ce0_n(ram_ce0_n), .ram_ce1_n(ram_ce1_n), .rom_ce2_n(rom_ce2_n),
        
        .atl_d(atl_d), .atl_a(atl_a),
        .atl_ce_n(atl_ce_n), .atl_oe_n(atl_oe_n), .atl_we_n(atl_we_n)
    );

    // ==========================================
    // U3: IS61C256AL (Address Translation SRAM)
    // ==========================================
    // 32K chip, but we only use the bottom 16 bytes. Ground the upper 11 address lines.
    wire [14:0] atl_phys_a = {11'b0, atl_a};
    
    is61c256al atl_sram (
        .addr(atl_phys_a), .data(atl_d),
        .ce_n(atl_ce_n), .oe_n(atl_oe_n), .we_n(atl_we_n)
    );

    // ==========================================
    // U4, U5, U6: Primary Memory Chips
    // ==========================================
    // HW REV A11 BUG: 19-bit physical address is formed by appending Local A0-A10 to ATL D0-D7.
    wire [18:0] phys_addr = {atl_d, l_a};

    cy7c1049 ram0 (
        .addr(phys_addr), .data(l_d),
        .ce_n(ram_ce0_n), .oe_n(oe_n), .we_n(we_n)
    );

    cy7c1049 ram1 (
        .addr(phys_addr), .data(l_d),
        .ce_n(ram_ce1_n), .oe_n(oe_n), .we_n(we_n)
    );

    sst39sf040 rom (
        .addr(phys_addr), .data(l_d),
        .ce_n(rom_ce2_n), .oe_n(oe_n), 
        .we_n(1'b1) // Memory card ROM is read-only
    );

endmodule