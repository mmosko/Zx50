`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_backplane
 * DESCRIPTION:
 * A purely passive module representing the physical backplane PCB. It contains no 
 * active logic, only weak resistive pull-ups (pullup primitives) for all shared 
 * Z80 and Shadow Bus traces. This prevents floating 'Z' states from becoming 'X' 
 * (unknown) states during bus handoffs, while allowing any active card to safely 
 * pull the lines low without causing a short circuit.
 *
 * NOTE: Clocks (MCLK/ZCLK) and Daisy-Chain lines (IEI/IEO) are excluded as they 
 * are point-to-point or actively driven at all times.
 ***************************************************************************************/

module zx50_backplane (
    // --- Z80 Backplane Buses ---
    inout wire [15:0] z80_addr,
    inout wire [7:0]  z80_data,
    inout wire z80_mreq_n,
    inout wire z80_iorq_n,
    inout wire z80_rd_n,
    inout wire z80_wr_n,
    inout wire z80_m1_n,
    inout wire z80_wait_n,
    inout wire z80_int_n,

    // --- Shadow Bus Backplane ---
    inout wire [15:0] shd_addr,
    inout wire [7:0]  shd_data,
    inout wire shd_en_n,
    inout wire shd_rw_n,
    inout wire shd_inc_n,
    inout wire shd_stb_n,
    inout wire shd_done_n,
    inout wire shd_busy_n
);

    // --- Z80 Control Line Pull-ups ---
    pullup(z80_mreq_n);
    pullup(z80_iorq_n);
    pullup(z80_rd_n);
    pullup(z80_wr_n);
    pullup(z80_m1_n);
    pullup(z80_wait_n);
    pullup(z80_int_n);

    // --- Shadow Bus Control Line Pull-ups ---
    pullup(shd_en_n);
    pullup(shd_rw_n);
    pullup(shd_inc_n);
    pullup(shd_stb_n);
    pullup(shd_done_n);
    pullup(shd_busy_n);

    // --- Address and Data Bus Pull-ups (Using generate blocks for arrays) ---
    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : pu_z80_addr
            pullup(z80_addr[i]);
        end
        for (i = 0; i < 8; i = i + 1) begin : pu_z80_data
            pullup(z80_data[i]);
        end
        for (i = 0; i < 16; i = i + 1) begin : pu_shd_addr
            pullup(shd_addr[i]);
        end
        for (i = 0; i < 8; i = i + 1) begin : pu_shd_data
            pullup(shd_data[i]);
        end
    endgenerate

endmodule