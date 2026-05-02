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
    inout wire z80_reset_n,
    inout wire z80_iei,
    inout wire z80_ieo,
    
    // --- Shadow Bus Backplane ---
    inout wire [15:0] sh_addr,
    inout wire [7:0]  sh_data,
    inout wire sh_en_n,
    inout wire sh_rw_n,
    inout wire sh_inc_n,
    inout wire sh_stb_n,
    inout wire sh_done_n,
    inout wire sh_busy_n
);

    // --- Z80 Control Line Pull-ups ---
    pullup(z80_mreq_n);
    pullup(z80_iorq_n);
    pullup(z80_rd_n);
    pullup(z80_wr_n);
    pullup(z80_m1_n);
    pullup(z80_wait_n);
    pullup(z80_int_n);
    pullup(z80_reset_n);

    // --- Shadow Bus Control Line Pull-ups ---
    pullup(sh_en_n);
    pullup(sh_rw_n);
    pullup(sh_inc_n);
    pullup(sh_stb_n);
    pullup(sh_done_n);
    pullup(sh_busy_n);

    // --- Address and Data Bus Pull-ups ---
    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : pu_z80_addr
            pullup(z80_addr[i]);
        end
        for (i = 0; i < 8; i = i + 1) begin : pu_z80_data
            pullup(z80_data[i]);
        end
        for (i = 0; i < 16; i = i + 1) begin : pu_sh_addr
            pullup(sh_addr[i]);
        end
        for (i = 0; i < 8; i = i + 1) begin : pu_sh_data
            pullup(sh_data[i]);
        end
    endgenerate

endmodule