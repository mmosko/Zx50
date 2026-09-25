`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_alu
 * FILE: src/zx50_fpu_alu.v
 * DESCRIPTION:
 * Top-Level Byte-Serial Arithmetic Core Manager for Zx50 FPU Coprocessor (CPLD Rev C2).
 *
 * DELEGATION ARCHITECTURE:
 * - Instantiates zx50_fpu_alu_addsub for ADD (0x0), SUB (0x1), and CHS (0x5).
 * - Instantiates zx50_fpu_alu_mul for Quarter-Square Multiplication MUL (0x2).
 * - Routes memory control requests and output status flags based on the active op.
 ***************************************************************************************/

module zx50_fpu_alu (
    input  wire        mclk,            // Coprocessor High-Speed Clock (20MHz / 40MHz)
    input  wire        reset_n,         // Global System Reset (Active LOW)

    // --- Control Interface (from zx50_fpu_dispatch) ---
    input  wire        start_p,         // 1-tick trigger pulse to begin calculation
    input  wire [3:0]  fmt,             // Opcode format field (0x0 = i16, 0x1 = i32, etc.)
    input  wire [3:0]  op,              // Opcode operation field (0x0 = ADD, 0x1 = SUB, etc.)
    input  wire [7:0]  sp_in,           // Current Stack Pointer (points to top of stack)

    output wire        done_p,          // 1-tick execution complete pulse
    output wire        err_flag,        // Set on arithmetic error / divide-by-zero
    output wire [4:0]  status_flags,    // [ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW]

    // --- Private Memory Master Interface (to zx50_fpu_mem) ---
    output wire        alu_mem_we_req,  // SRAM write enable request
    output wire        alu_mem_oe_req,  // SRAM / Flash read enable request
    output wire        alu_sel_flash,   // 1 = Flash ROM (LUTs), 0 = SRAM
    output wire [14:0] alu_mem_addr,    // 15-bit target private address (32KB window)
    output wire [7:0]  alu_mem_wdata,   // Write payload to private memory
    input  wire [7:0]  mem_rdata,       // Data read back from private memory bus
    input  wire        mem_ready        // 1 = Memory read valid or write complete
);

    localparam OP_MUL = 4'h2;

    // Register active unit selection across multi-cycle operation
    reg active_is_mul;

    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            active_is_mul <= 1'b0;
        end else if (start_p) begin
            active_is_mul <= (op == OP_MUL);
        end
    end

    // Trigger pulses routed to specific submodules
    wire addsub_start_p = start_p && (op != OP_MUL);
    wire mul_start_p    = start_p && (op == OP_MUL);

    // --- Submodule Outputs ---
    wire        addsub_done_p,     mul_done_p;
    wire        addsub_err_flag,   mul_err_flag;
    wire [4:0]  addsub_status,     mul_status;
    wire        addsub_we_req,     mul_we_req;
    wire        addsub_oe_req,     mul_oe_req;
    wire        addsub_sel_flash,  mul_sel_flash;
    wire [14:0] addsub_addr,       mul_addr;
    wire [7:0]  addsub_wdata,      mul_wdata;

    // =========================================================================
    // 1. Submodule Instantiations
    // =========================================================================

    // Adder / Subtractor / Negator Core
    zx50_fpu_alu_addsub u_addsub (
        .mclk(mclk),
        .reset_n(reset_n),
        .start_p(addsub_start_p),
        .fmt(fmt),
        .op(op),
        .sp_in(sp_in),
        .done_p(addsub_done_p),
        .err_flag(addsub_err_flag),
        .status_flags(addsub_status),
        .mem_we_req(addsub_we_req),
        .mem_oe_req(addsub_oe_req),
        .sel_flash(addsub_sel_flash),
        .mem_addr(addsub_addr),
        .mem_wdata(addsub_wdata),
        .mem_rdata(mem_rdata),
        .mem_ready(mem_ready)
    );

    // Quarter-Square Hardware Multiplier Core
    zx50_fpu_alu_mul u_mul (
        .mclk(mclk),
        .reset_n(reset_n),
        .start_p(mul_start_p),
        .fmt(fmt),
        .sp_in(sp_in),
        .done_p(mul_done_p),
        .err_flag(mul_err_flag),
        .status_flags(mul_status),
        .mem_we_req(mul_we_req),
        .mem_oe_req(mul_oe_req),
        .sel_flash(mul_sel_flash),
        .mem_addr(mul_addr),
        .mem_wdata(mul_wdata),
        .mem_rdata(mem_rdata),
        .mem_ready(mem_ready)
    );

    // =========================================================================
    // 2. Bus Multiplexing Logic
    // =========================================================================
    assign alu_mem_we_req = active_is_mul ? mul_we_req    : addsub_we_req;
    assign alu_mem_oe_req = active_is_mul ? mul_oe_req    : addsub_oe_req;
    assign alu_sel_flash  = active_is_mul ? mul_sel_flash : addsub_sel_flash;
    assign alu_mem_addr   = active_is_mul ? mul_addr      : addsub_addr;
    assign alu_mem_wdata  = active_is_mul ? mul_wdata     : addsub_wdata;

    assign done_p         = active_is_mul ? mul_done_p    : addsub_done_p;
    assign err_flag       = active_is_mul ? mul_err_flag  : addsub_err_flag;
    assign status_flags   = active_is_mul ? mul_status    : addsub_status;

endmodule