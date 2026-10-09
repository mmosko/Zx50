`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_reg
 * DESCRIPTION:
 * Register file for zx50_fpu (CPLD Rev C2).

 * There are two output mux HA_BUS and HB_BUS, which correspond to the A and B operands.
 ***************************************************************************************/

module zx50_fpu_reg (
    input  wire        fclk,
    input  wire        reset_n,

    input wire [2:0]  ha_sel_bus,
    input wire [4:0]  hb_sel_bus,

    input  wire [31:0] res_bus,
    output wire [31:0] ha_bus,
    output wire [31:0] hb_bus,

    output wire        sp,
    output wire        pc
);

    reg [31:0] ah_reg;
    reg [31:0] al_reg;
    reg [31:0] bh_reg;
    reg [31:0] bl_reg;
    reg [31:0] dh_reg;
    reg [31:0] dl_reg;
    reg [31:0] fh_reg;
    reg [31:0] fl_reg;

    reg [31:0] ea_reg;
    reg [31:0] eb_reg;

    reg [7:0] c_reg;

    reg [7:0] sp_reg;
    reg [7:0] osp_reg;
    reg [9:0] pc_reg;

        always @(posedge fclk or negedge reset_n) begin
        if (!reset_n) begin
            sp_reg  <= 8'h00;
            osp_reg <= 8'h00;
            pc_reg  <= 10'h000;
        end else begin

            

        end

        sp <= sp_reg;
        pc <= pc_reg;   
    end

endmodule
