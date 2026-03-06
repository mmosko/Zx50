`timescale 1ns/1ps

module zx50_bus_arbiter (
    input wire mclk,            
    input wire reset_n,         

    // --- Bus Requests & Status ---
    input wire shadow_en_n,     
    input wire z80_card_hit,    

    // --- Wait State Generators ---
    output wire z80_wait_n,     
    output wire shd_busy_n,     

    // --- Backplane Command Inputs ---
    input wire z80_rd_n,        
    input wire shd_rw_n,        

    // --- Transceiver Controls ---
    output wire z80_data_oe_n,  // Data Buffer Enable
    output wire shd_data_oe_n,  // Shadow Data Buffer Enable
    output wire d_dir           // SHARED Direction Line
);

    localparam BUS_Z80    = 2'b00;
    localparam BUS_DEAD_1 = 2'b01; 
    localparam BUS_SHADOW = 2'b10;
    localparam BUS_DEAD_2 = 2'b11; 

    reg [1:0] bus_state;

    // --- Clocked State Machine ---
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            bus_state <= BUS_Z80;
        end else begin
            case (bus_state)
                BUS_Z80: begin
                    if (!shadow_en_n && !z80_card_hit) bus_state <= BUS_DEAD_1;
                end
                BUS_DEAD_1: bus_state <= BUS_SHADOW;
                BUS_SHADOW: begin
                    if (shadow_en_n) bus_state <= BUS_DEAD_2;
                end
                BUS_DEAD_2: bus_state <= BUS_Z80;
            endcase
        end
    end

    // --- The Wait / Busy Generators ---
    assign z80_wait_n = (z80_card_hit && (bus_state != BUS_Z80)) ? 1'b0 : 1'b1;
    assign shd_busy_n = (!shadow_en_n && (bus_state != BUS_SHADOW)) ? 1'b0 : 1'b1;

    // --- Transceiver Output Enables ---
    assign z80_data_oe_n = ~((bus_state == BUS_Z80) && z80_card_hit);
    assign shd_data_oe_n = ~((bus_state == BUS_SHADOW) && !shadow_en_n);

    // --- Direction Control ---
    // 1 = Master to Card (Write), 0 = Card to Master (Read)
    assign d_dir = (bus_state == BUS_Z80)    ? z80_rd_n :
                   (bus_state == BUS_SHADOW) ? !shd_rw_n : 1'b1;

endmodule