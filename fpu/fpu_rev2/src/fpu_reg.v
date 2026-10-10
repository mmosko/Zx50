`timescale 1ns/1ps

/***************************************************************************************
* MODULE: fpu_reg
* DESCRIPTION:
* Register file and operand multiplexers for zx50_fpu Rev 2.
*
* - Latches 32-bit micro-instructions (instr_in) when instr_we is asserted:
*     * instr_reg [21:0] <= instr_in[31:10] (Control, Opcodes, Mux Selects)
*     * imm_reg   [9:0]  <= instr_in[9:0]   (Immediate / Address Field)
* - Multiplexes HA_BUS (Operand A) and HB_BUS (Operand B).
* - Handles synchronous writeback from RES_BUS to destination registers.
* - the SP and PC have dedicated inputs and write enables.
* - The SP is updated by the memory module PUSH and POP instructions.
* - The PC is updated by the sequencer as part of the instruction fetch cycle or as
    the result of a jump/branch instruction.
***************************************************************************************/

module fpu_reg (
    input  wire        fclk,
    input  wire        reset_n,

    // 32-bit Micro-instruction fetched from CODE_ROM
    input  wire [31:0] instr_in,
    input  wire        instr_we, // Write enable to latch new instruction/immediate

    // Expose decoded instruction and immediate registers to control logic
    output wire [21:0] instr_out,
    output wire [9:0]  imm_out,

    // The HA mux selects one of {AL, AH, EA, EB, IMM, C, BL, BH}
    input  wire [2:0]  ha_sel_bus,
    output reg  [31:0] ha_bus,

    // The HB mux selects one of {AL, AH, EA, EB, IMM, C, BL, BH, DL, DH, FL, FH}
    input  wire [3:0]  hb_sel_bus,
    output reg  [31:0] hb_bus,

    // The result bus is the writeback value for general registers
    input  wire [31:0] res_bus,

    // 4-bit register select for writeback
    input  wire [3:0]  res_sel_bus,

    // Write enable for register writeback on clock edge
    input  wire        we,

    // Stack pointer output, input, and write enable
    output wire [7:0]  sp,
    input  wire [7:0]  sp_in,
    input  wire        sp_we,

    // Program counter output
    output wire [9:0]  pc,
    input wire [9:0] pc_in,
    input wire pc_we
);

    // -------------------------------------------------------------------------
    // Register Definitions
    // -------------------------------------------------------------------------
    
    // General-purpose 32-bit registers
    reg [31:0] al_reg;
    reg [31:0] ah_reg;
    reg [31:0] bl_reg;
    reg [31:0] bh_reg;
    reg [31:0] dl_reg;
    reg [31:0] dh_reg;
    reg [31:0] fl_reg;
    reg [31:0] fh_reg;

    // 12-bit exponent registers
    reg [11:0] ea_reg;
    reg [11:0] eb_reg;

    // 8-bit loop/shift counter
    reg [7:0]  c_reg;

    // Control registers
    reg [7:0]  sp_reg;
    reg [7:0]  osp_reg;
    reg [9:0]  pc_reg;

    // Instruction Pipeline Registers
    reg [21:0] instr_reg; // INSTR[21:0] <= instr_in[31:10]
    reg [9:0]  imm_reg;   // IMM[9:0]   <= instr_in[9:0]

    // Continuous assignment outputs
    assign sp        = sp_reg;
    assign pc        = pc_reg;
    assign instr_out = instr_reg;
    assign imm_out   = imm_reg;

    // -------------------------------------------------------------------------
    // HA_BUS Multiplexer (Primary Operand A - 8 Inputs)
    // -------------------------------------------------------------------------
    always @(*) begin
        case (ha_sel_bus)
            3'b000: ha_bus = al_reg;
            3'b001: ha_bus = ah_reg;
            3'b010: ha_bus = {20'h00000, ea_reg};  // Zero-extend 12-bit EA
            3'b011: ha_bus = {20'h00000, eb_reg};  // Zero-extend 12-bit EB
            3'b100: ha_bus = {22'h000000, imm_reg};// Zero-extend 10-bit IMM
            3'b101: ha_bus = {24'h000000, c_reg};  // Zero-extend 8-bit C
            3'b110: ha_bus = bl_reg;
            3'b111: ha_bus = bh_reg;
            default: ha_bus = 32'h0000_0000;
        endcase
    end

    // -------------------------------------------------------------------------
    // HB_BUS Multiplexer (Secondary Operand B - 12 Inputs)
    // -------------------------------------------------------------------------
    always @(*) begin
        case (hb_sel_bus)
            4'b0000: hb_bus = al_reg;
            4'b0001: hb_bus = ah_reg;
            4'b0010: hb_bus = {20'h00000, ea_reg};
            4'b0011: hb_bus = {20'h00000, eb_reg};
            4'b0100: hb_bus = {22'h000000, imm_reg}; // Zero-extend 10-bit IMM
            4'b0101: hb_bus = {24'h000000, c_reg};
            4'b0110: hb_bus = bl_reg;
            4'b0111: hb_bus = bh_reg;
            4'b1000: hb_bus = dl_reg;
            4'b1001: hb_bus = dh_reg;
            4'b1010: hb_bus = fl_reg;
            4'b1011: hb_bus = fh_reg;
            default: hb_bus = 32'h0000_0000;
        endcase
    end

    // -------------------------------------------------------------------------
    // Synchronous Register Writeback, Instruction Latching & Reset Logic
    // -------------------------------------------------------------------------
    always @(posedge fclk or negedge reset_n) begin
        if (!reset_n) begin
            al_reg    <= 32'h0000_0000;
            ah_reg    <= 32'h0000_0000;
            bl_reg    <= 32'h0000_0000;
            bh_reg    <= 32'h0000_0000;
            dl_reg    <= 32'h0000_0000;
            dh_reg    <= 32'h0000_0000;
            fl_reg    <= 32'h0000_0000;
            fh_reg    <= 32'h0000_0000;
            ea_reg    <= 12'h000;
            eb_reg    <= 12'h000;
            c_reg     <= 8'h00;
            sp_reg    <= 8'h00;
            osp_reg   <= 8'h00;
            pc_reg    <= 10'h000;
            instr_reg <= 22'h00_0000;
            imm_reg   <= 10'h000;
        end else begin
            // Latch micro-instruction split when enabled by sequencer
            if (instr_we) begin
                instr_reg <= instr_in[31:10];
                imm_reg   <= instr_in[9:0];
            end

            // Hardware Stack Pointer Update
            if (sp_we) begin
                sp_reg <= sp_in;
            end

            // Hardware PC  Update
            if (pc_we) begin
                pc_reg <= pc_in;
            end

            // Result Bus Writeback Logic
            if (we) begin
                case (res_sel_bus)
                    4'b0000: al_reg <= res_bus;
                    4'b0001: ah_reg <= res_bus;
                    4'b0010: ea_reg <= res_bus[11:0];
                    4'b0011: eb_reg <= res_bus[11:0];
                    4'b0101: c_reg  <= res_bus[7:0];
                    4'b0110: bl_reg <= res_bus;
                    4'b0111: bh_reg <= res_bus;
                    4'b1000: dl_reg <= res_bus;
                    4'b1001: dh_reg <= res_bus;
                    4'b1010: fl_reg <= res_bus;
                    4'b1011: fh_reg <= res_bus;
                    default: ; // 4'b1111 (NONE) or reserved: no write
                endcase
            end
        end
    end

endmodule