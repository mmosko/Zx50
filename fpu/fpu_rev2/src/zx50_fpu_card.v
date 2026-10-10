`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_card
 * DESCRIPTION:
 * Top-level wrapper for the isolated math coprocessor cluster.
 * Connects FPGA (U11), private SRAM (U12), and private Flash ROM (U13).
 * Accepts optional hex file paths for SRAM and Flash pre-loading in simulation.
 ***************************************************************************************/

module zx50_fpu_card #(
    parameter RAM_INIT_FILE = "",
    parameter ROM_INIT_FILE = ""
)(
    input  wire        mclk,
    input  wire        zclk,
    input  wire        reset_n,

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
    
    // SRAM control
    wire        m_oe_n, m_we_n; // Common OE/WE
    wire        m_ce_n;         // SRAM Chip Enable

    // Flash control (IS25LP080D-JNLE-TR)
    // TODO

    // ==========================================
    // U11: MachXO2-2000 FPGA
    // ==========================================
    zx50_fpu zx50_fpu (
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

        // Private 128KB SRAM Connections
        .ca(ca),
        .cd(cd),
        .m_ce_n(m_ce_n),
        .m_oe_n(m_oe_n),
        .m_we_n(m_we_n),
    );

    // ==========================================
    // U12: IS61WV1288EE-10 128KB Active Private SRAM
    // ==========================================
 

    is61wv1288ee_10 #(
        .MEM_INIT_FILE(RAM_INIT_FILE)
    ) fpu_sram (
        .addr(ca),
        .data(cd),
        .me_n(m_ce_n),
        .oe_n(m_oe_n),
        .we_n(m_we_n)
    );  

    // ==========================================
    // U13: IS25LP080D-JNLE-TR QSPI Flash ROM (32MB)
    // ==========================================
    // TODO

endmodule
