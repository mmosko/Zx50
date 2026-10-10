`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu
 * FILE: src/zx50_fpu.v
 * DESCRIPTION:
 * Top-Level CPLD Logic for Microchip ATF1508AS CPLD (U11) on Zx50 CPU Card (Rev C2).
 *
 * ARCHITECTURAL CLOCK DOMAINS:
 * 1. ZCLK Domain (Host Z80 Clock - 5MHz or 10MHz):
 *    - Synchronously decodes host Z80 I/O accesses for Port 0x70 (Stack) and 0x71 (CMD/Status).
 *    - Manages the 8-bit Stack Pointer (sp) for PUSH, POP, and management updates.
 *    - Drives wired-OR open-drain handshake outputs (wait_n, int_n) to stall/interrupt host.
 *
 * 2. MCLK Domain (Coprocessor High-Speed Clock - 20MHz or 40MHz):
 *    - Instantiates zx50_fpu_mem to manage private SRAM/Flash timing and arbitration.
 *    - Instantiates zx50_fpu_dispatch to execute commands and process management opcodes.
 *    - Performs 4-phase CDC level handshaking across clock domains.
 ***************************************************************************************/

module zx50_fpu (
    input  wire        mclk,        // 20MHz or 40MHz High-Speed Coprocessor Clock
    input  wire        zclk,        // 5MHz or 10MHz Host Z80 CPU Clock
    input  wire        reset_n,     // Global System Reset (Active LOW)
    input  wire        clk_spd,     // Speed Select Jumper (1=40MHz Fast, 0=20MHz Slow)

    // --- Host Z80 Backplane Bus Interface ---
    input  wire [15:0] z80_a,       // 16-bit Host Address Bus (Port 0x70/0x71 decoding)
    inout  wire [7:0]  z80_d,       // 8-bit Bidirectional Host Data Bus
    input  wire        z80_mreq_n,  // Memory Request (~MREQ)
    input  wire        z80_iorq_n,  // I/O Request (~IORQ)
    input  wire        z80_rd_n,    // Read Strobe (~RD)
    input  wire        z80_wr_n,    // Write Strobe (~WR)
    input  wire        z80_m1_n,    // Machine Cycle 1 (~M1, used to mask INTACK cycles)

    // --- Shared Backplane Handshake Lines (Wired-OR Open-Drain) ---
    inout  wire        wait_n,      // Active-LOW CPU Wait Request (0 = Stall Z80, Z = Release)
    inout  wire        int_n,       // Active-LOW CPU Interrupt Request (0 = Assert INT, Z = Release)

    // --- Private Coprocessor Memory Bus (Decoupled from Backplane) ---

    // Local SRAM (IS61WV1288EE-10 - U12) 
    output wire [16:0] ca,          // 128KB address range
    inout  wire [7:0]  cd,          // 8-bit SRAM data bus
    output wire        m_ce_n,      // Private SRAM Chip Enable (~CE)
    output wire        m_oe_n,      // Common private ~OE (SRAM/Flash Output Enable)
    output wire        m_we_n,      // Common private ~WE (SRAM/Flash Write Enable)

    // Local Flash ROM (IS25LP128F - U13)
    output wire        f_ce_n       // Private Flash Chip Enable (~CE)
    // TODO: wire up QSPI flash
);

    // =========================================================================
    // 1. Internal Registers & Signals
    // =========================================================================

    
    // Open-Drain Driver Controls (1 = Drive 0, 0 = High-Z)
    reg       c_wait_req;   // Controls wait_n driver
    reg       c_int_req;    // Controls int_n driver

    // State-locking flags to ensure 1 event per Z80 I/O strobe
    reg       io_wr_busy;   // Locks write handling while ~WR & ~IORQ remain LOW
    reg       io_rd_busy;   // Locks read auto-decrement while ~RD & ~IORQ remain LOW


    // CDC Synchronizer: Synchronize done_ack from MCLK domain into ZCLK domain
    reg [1:0] ack_sync;
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) ack_sync <= 2'b00;
        else          ack_sync <= {ack_sync[0], dispatch_done_ack};
    end
    wire dispatch_done_sync = ack_sync[1];


    wire [7:0] sp;
    wire [7:0] status_bus

    // =========================================================================
    // Clock Generation: MCLK x4 PLL -> FCLK
    // =========================================================================
    wire fclk;
    wire fpu_reset_n; // Use this gated reset for all FPU core registers & modules

    fpu_clock clk_gen (
        .mclk        (mclk),
        .reset_n     (reset_n),
        .fclk        (fclk),
        .pll_lock    (),            // Unused or routed to status_reg
        .fpu_reset_n (fpu_reset_n)
    );

    // =========================================================================
    // 2. Submodule Instantiations
    // =========================================================================
    
    zx50_fpu_code_block code_rom (
        .fclk(fclk),
        .addr(eng_mem_addr[9:0]),
        .dout(mem_rdata)
    );

    zx50_fpu_data_block data_ram (
        .fclk(fclk),
        .addr(eng_mem_addr[9:0]),
        .din(eng_mem_wdata),
        .we(eng_mem_we_req),
        .dout(mem_rdata)
    );

    fpu_reg regfile (
        .fclk(fclk),
        .reset_n(fpu_reset_n),
        .instr_in(instr_in),
        .instr_we(instr_we),
        .instr_out(instr_out),
        .imm_out(imm_out),
        .ha_sel_bus(ha_sel_bus),
        .ha_bus(ha_bus),
        .hb_sel_bus(hb_sel_bus),
        .hb_bus(hb_bus),
        .res_bus(res_bus),
        .res_sel_bus(res_sel_bus),
        .we(we),
        .sp(sp),
        .sp_in(sp_in),
        .sp_we(sp_we),
        .pc(pc),
        .pc_in(pc_in),
        .pc_we(pc_we)
    );

    fpu_status_reg status_reg (
        .fclk(fclk),
        .fpu_reset_n(fpu_reset_n),
        .status_in(status_flags),
        .write_mask(status_wr_sel),
        .we(status_we),
        .status_out(status_bus)
    );

    // --- Command Execution Dispatcher ---
    zx50_fpu_dispatch dispatcher (
        .mclk(mclk),
        .reset_n(reset_n),
        .exec_req(exec_req),
        .opcode(opcode_reg),
        .sp_in(sp),
        .done_ack(dispatch_done_ack),
        .err_flag(dispatch_err),
        .status_flags(dispatch_flags),
        .new_sp(dispatch_new_sp),
        .sp_write_en(dispatch_sp_write),
        .disp_sram_we_req(eng_mem_we_req),
        .disp_sram_oe_req(eng_mem_oe_req),
        .disp_sram_wdata(eng_mem_wdata),
        .disp_sram_addr(eng_mem_addr[7:0])
    );

    fpu_host host (
        .fclk(fclk),
        .fpu_reset_n(fpu_reset_n),
        .z80_a(z80_a[7:0]),
        .z80_d(z80_d),
        .z80_iorq_n(z80_iorq_n),
        .z80_rd_n(z80_rd_n),
        .z80_wr_n(z80_wr_n),
        .z80_m1_n(z80_m1_n),
        .wait_n(wait_n),
        .int_n(int_n),
        .host_in(host_in),
        .host_out(host_out),
        .opcode_out(opcode_out),
        .exec_start(exec_start),
        .dispatch_done(dispatch_done),
        .status_in(status_bus)
    );

endmodule