`timescale 1ns/1ps

// The ATF1508AS CPLD Core Logic
module zx50_fpu (
    input  wire        mclk,        // 20MHz/40MHz Coprocessor Clock
    input  wire        zclk,        // 5MHz/10MHz Host Z80 Clock
    input  wire        reset_n,
    
    // Z80 Host Bus Interface
    input  wire [15:0] z80_a,
    inout  wire [7:0]  z80_d,
    input  wire        z80_mreq_n,
    input  wire        z80_iorq_n,
    input  wire        z80_rd_n,
    input  wire        z80_wr_n,
    input  wire        z80_m1_n,

    output wire        wait_n,
    output wire        int_n,

    // Private Memory Bus Interface (CA[13:0] & CD[7:0])
    output wire [13:0] ca,
    inout  wire [7:0]  cd,

    // Local SRAM (U12) Controls
    output wire        m_ce_n,
    output wire        m_oe_n,
    output wire        m_we_n,
    
    // Local Flash (U13) Controls
    output wire        f_ce_n,
    output wire        f_oe_n,
    output wire        f_we_n
);

    // Initial stub default assignments
    assign wait_n = 1'b1;
    assign int_n  = 1'b1;

    assign ca     = 14'h0000;
    assign cd     = 8'hzz;

    assign m_ce_n = 1'b1;
    assign m_oe_n = 1'b1;
    assign m_we_n = 1'b1;

    assign f_ce_n = 1'b1;
    assign f_oe_n = 1'b1;
    assign f_we_n = 1'b1;

endmodule
