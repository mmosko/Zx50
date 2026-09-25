`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_block
 * DESCRIPTION:
 * Top-level wrapper for the isolated math coprocessor cluster.
 * Connects CPLD (U11), private SRAM (U12), and private Flash ROM (U13).
 * Accepts optional hex file paths for SRAM and Flash pre-loading in simulation.
 ***************************************************************************************/

module zx50_fpu_block #(
    parameter RAM_INIT_FILE = "",
    parameter ROM_INIT_FILE = ""
)(
    input  wire        mclk,
    input  wire        zclk,
    input  wire        reset_n,
    input  wire        clk_spd,     // 1=Fast (40MHz), 0=Slow (20MHz)

    // Z80 Backplane Host Bus
    input  wire [15:0] z80_a,
    inout  wire [7:0]  z80_d,
    input  wire        z80_mreq_n,
    input  wire        z80_iorq_n,
    input  wire        z80_rd_n,
    input  wire        z80_wr_n,
    input  wire        z80_m1_n,

    inout  wire        wait_n,
    inout  wire        int_n
);

    // ==========================================
    // Private PCB Traces (CA[14:0] & CD[7:0])
    // ==========================================
    wire [14:0] ca;        // Private Address Bus (32KB active)
    wire [7:0]  cd;        // Private Data Bus
    
    // Private Memory Controls
    wire        c_oe_n, c_we_n; // Common OE/WE
    wire        m_ce_n;         // SRAM Chip Enable
    wire        f_ce_n;         // Flash Chip Enable

    // ==========================================
    // U11: ATF1508AS CPLD Core Controller
    // ==========================================
    zx50_fpu cpld (
        .mclk(mclk), 
        .zclk(zclk),
        .reset_n(reset_n),
        .clk_spd(clk_spd),

        // Host Z80 Connections
        .z80_a(z80_a),
        .z80_d(z80_d),
        .z80_mreq_n(z80_mreq_n), 
        .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n), 
        .z80_wr_n(z80_wr_n), 
        .z80_m1_n(z80_m1_n),
        .wait_n(wait_n), 
        .int_n(int_n),

        // Private Memory Connections
        .ca(ca),
        .cd(cd),
        .m_ce_n(m_ce_n),
        .c_oe_n(c_oe_n),
        .c_we_n(c_we_n),
        .f_ce_n(f_ce_n)
    );

    // ==========================================
    // U12: IS61C256AL 32KB Active Private SRAM
    // ==========================================
    is61c256al #(
        .MEM_INIT_FILE(RAM_INIT_FILE)
    ) fpu_sram (
        .addr(ca),
        .data(cd),
        .ce_n(m_ce_n),
        .oe_n(c_oe_n),
        .we_n(c_we_n)
    );  

    // ==========================================
    // U13: SST39SF040 32KB Active Private Flash ROM
    // ==========================================
    sst39sf040 #(
        .MEM_INIT_FILE(ROM_INIT_FILE)
    ) fpu_flash (
        .addr({4'b0000, ca}), // Upper address pins A15-A18 tied to GND
        .data(cd),
        .ce_n(f_ce_n),
        .oe_n(c_oe_n),
        .we_n(c_we_n)
    );

endmodule
