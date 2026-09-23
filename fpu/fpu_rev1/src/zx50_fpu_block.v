`timescale 1ns/1ps

// The FPU subsystem wrapper, containing the CPLD, private Flash, and private SRAM
module zx50_fpu_block (
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

    output wire        wait_n,
    output wire        int_n
);

    // ==========================================
    // Private PCB Traces (CA[13:0] & CD[7:0])
    // ==========================================
    wire [13:0] ca;        // Private Address Bus (16KB active)
    wire [7:0]  cd;        // Private Data Bus
    
    // Private Memory Controls
    wire        m_ce_n, m_oe_n, m_we_n; // SRAM
    wire        f_ce_n, f_oe_n, f_we_n; // Flash

    // ==========================================
    // U11: ATF1508AS CPLD Core Controller
    // ==========================================
    zx50_fpu cpld (
        .mclk(mclk), 
        .zclk(zclk),
        .reset_n(reset_n),
        
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
        .m_oe_n(m_oe_n),
        .m_we_n(m_we_n),
        .f_ce_n(f_ce_n),
        .f_oe_n(f_oe_n),
        .f_we_n(f_we_n)
    );

    // ==========================================
    // U12: IS61C5128AS 16KB Active Private SRAM
    // ==========================================
    // Address lines A14-A18 are tied to GND on PCB (pad with 5'b00000)
    is61c5128as fpu_sram (
        .addr({5'b00000, ca}),
        .data(cd),
        .ce_n(m_ce_n),
        .oe_n(m_oe_n),
        .we_n(m_we_n)
    );  

    // ==========================================
    // U13: SST39SF040 16KB Active Private Flash
    // ==========================================
    // Address lines A14-A18 are tied to GND on PCB (pad with 5'b00000)
    sst39sf040 #(
        .MEM_INIT_FILE("fpu_rom.hex")
    ) fpu_flash (
        .addr({5'b00000, ca}),
        .data(cd),
        .ce_n(f_ce_n),
        .oe_n(f_oe_n),
        .we_n(f_we_n)
    );

endmodule
