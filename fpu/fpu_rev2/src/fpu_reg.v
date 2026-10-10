`timescale 1ns/1ps

/***************************************************************************************
* MODULE: fpu_reg
* DESCRIPTION:
* Register file and operand multiplexers for zx50_fpu Rev 2.
*
* - Latches 32-bit micro-instructions (instr_in) when instr_we is asserted.
* - Multiplexes HA_BUS (Operand A) and HB_BUS (Operand B) using a factored
*   2-stage MUX architecture to minimize MachXO2 LUT usage.
* - Handles synchronous writeback from RES_BUS to destination registers.
* - Dedicated inputs and write enables for SP and PC registers.
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

    // The HA mux selects one of {AL, AH, BL, BH, CL, CH, DL, DH, FL, FH, EA, EB, C, IMM}
    input  wire [3:0]  ha_sel_bus,
    output reg  [31:0] ha_bus,

    // The HB mux selects one of {AL, AH, BL, BH, CL, CH, DL, DH, FL, FH, EA, EB, C, IMM}
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

    // Program counter output, input, and write enable
    output wire [9:0]  pc,
    input  wire [9:0]  pc_in,
    input  wire        pc_we
);

    // -------------------------------------------------------------------------
    // Register Definitions
    // -------------------------------------------------------------------------
    
    // General-purpose 32-bit registers
    reg [31:0] al_reg;
    reg [31:0] ah_reg;
    reg [31:0] bl_reg;
    reg [31:0] bh_reg;
    reg [31:0] cl_reg;
    reg [31:0] ch_reg;
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
    reg [21:0] instr_reg;
    reg [9:0]  imm_reg;

    // Continuous assignment outputs
    assign sp        = sp_reg;
    assign pc        = pc_reg;
    assign instr_out = instr_reg;
    assign imm_out   = imm_reg;

    // -------------------------------------------------------------------------
    // Factored Operand Bus Multiplexer Function
    // -------------------------------------------------------------------------
    function [31:0] mux_operand_bus;
        input [3:0]  sel;
        input [31:0] al, ah, bl, bh, cl, ch, dl, dh, fl, fh;
        input [11:0] ea, eb;
        input [7:0]  c;
        input [9:0]  imm;
        
        reg [31:0] gpr_val;
        reg [11:0] narrow_val;
        reg        is_narrow;
        begin
            // 1. 10-to-1 MUX for 32-bit General Purpose Registers (codes 0x0..0x9)
            case (sel)
                4'b0000: gpr_val = al;
                4'b0001: gpr_val = ah;
                4'b0010: gpr_val = bl;
                4'b0011: gpr_val = bh;
                4'b0100: gpr_val = cl;
                4'b0101: gpr_val = ch;
                4'b0110: gpr_val = dl;
                4'b0111: gpr_val = dh;
                4'b1000: gpr_val = fl;
                4'b1001: gpr_val = fh;
                default: gpr_val = 32'h0000_0000;
            endcase

            // 2. 4-to-1 MUX for sub-12-bit registers (codes 0xA..0xD)
            case (sel[1:0])
                2'b00: narrow_val = {4'h0, c};           // 4'b1100 (C)
                2'b01: narrow_val = {2'b00, imm};        // 4'b1101 (IMM)
                2'b10: narrow_val = ea;                  // 4'b1010 (EA)
                2'b11: narrow_val = eb;                  // 4'b1011 (EB)
            endcase

            // 3. Detect narrow register selection: sel >= 10 (4'b1010 through 4'b1111)
            is_narrow = sel[3] && (sel[2] || sel[1]);

            // 4. Combine: Bits [31:12] are forced to zero when reading narrow registers
            mux_operand_bus[31:12] = is_narrow ? 20'h00000   : gpr_val[31:12];
            mux_operand_bus[11:0]  = is_narrow ? narrow_val  : gpr_val[11:0];
        end
    endfunction

    // -------------------------------------------------------------------------
    // Combinational Bus Assignments
    // -------------------------------------------------------------------------
    always @(*) begin
        ha_bus = mux_operand_bus(
            ha_sel_bus, 
            al_reg, ah_reg, bl_reg, bh_reg, cl_reg, ch_reg, dl_reg, dh_reg, fl_reg, fh_reg, 
            ea_reg, eb_reg, c_reg, imm_reg
        );
        hb_bus = mux_operand_bus(
            hb_sel_bus, 
            al_reg, ah_reg, bl_reg, bh_reg, cl_reg, ch_reg, dl_reg, dh_reg, fl_reg, fh_reg, 
            ea_reg, eb_reg, c_reg, imm_reg
        );
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
            cl_reg    <= 32'h0000_0000;
            ch_reg    <= 32'h0000_0000;
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

            // Hardware Program Counter Update
            if (pc_we) begin
                pc_reg <= pc_in;
            end

            // Result Bus Writeback Logic
            if (we) begin
                case (res_sel_bus)
                    4'b0000: al_reg <= res_bus;
                    4'b0001: ah_reg <= res_bus;
                    4'b0010: bl_reg <= res_bus;
                    4'b0011: bh_reg <= res_bus;
                    4'b0100: cl_reg <= res_bus;
                    4'b0101: ch_reg <= res_bus;
                    4'b0110: dl_reg <= res_bus;
                    4'b0111: dh_reg <= res_bus;
                    4'b1000: fl_reg <= res_bus;
                    4'b1001: fh_reg <= res_bus;
                    4'b1010: ea_reg <= res_bus[11:0];
                    4'b1011: eb_reg <= res_bus[11:0];
                    4'b1100: c_reg  <= res_bus[7:0];
                    default: ; // 4'b1111 (NONE) or reserved: no write
                endcase
            end
        end
    end

endmodule