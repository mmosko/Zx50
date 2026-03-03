`timescale 1ns/1ps

module zx50_bus_arbiter (
    input wire mclk,            // High-speed Master Clock
    input wire reset_n,         // System Reset

    // --- Bus Requests & Status ---
    input wire shadow_en_n,     // 0 = Shadow Bus requests control of this card
    input wire z80_card_hit,    // 1 = Z80 is currently hitting THIS card

    // --- Wait State Generators ---
    output wire z80_wait_n,     // Drives Z80 backplane ~WAIT pin (Open Collector)
    output wire shd_busy_n,     // Drives Shadow backplane ~S_BUSY pin

    // --- Backplane Command Inputs ---
    input wire z80_rd_n,        // Z80 Read signal
    input wire shd_rw_n,        // Shadow Read/Write (0 = Write to Card, 1 = Read from Card)

    // --- Z80 Transceiver Controls (Set A) ---
    output wire z80_addr_oe_n,  // 74ABT244 ~OE
    output wire z80_data_oe_n,  // 74ABT245 ~OE
    output wire z80_data_dir,   // 74ABT245 DIR

    // --- Shadow Transceiver Controls (Set B) ---
    output wire shd_addr_oe_n,  // 74ABT244 ~OE
    output wire shd_data_oe_n,  // 74ABT245 ~OE
    output wire shd_data_dir    // 74ABT245 DIR
);

    localparam BUS_Z80     = 2'b00;
    localparam BUS_DEAD_1  = 2'b01; 
    localparam BUS_SHADOW  = 2'b10;
    localparam BUS_DEAD_2  = 2'b11; 

    reg [1:0] bus_state;

    // --- Clocked State Machine ---
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            bus_state <= BUS_Z80;
        end else begin
            case (bus_state)
                BUS_Z80: begin
                    // ONLY transition if the Z80 is NOT in the middle of a local cycle!
                    if (!shadow_en_n && !z80_card_hit) bus_state <= BUS_DEAD_1;
                end
                BUS_DEAD_1: begin
                    bus_state <= BUS_SHADOW;
                end
                BUS_SHADOW: begin
                    if (shadow_en_n) bus_state <= BUS_DEAD_2;
                end
                BUS_DEAD_2: begin
                    bus_state <= BUS_Z80;
                end
            endcase
        end
    end

    // --- The Wait / Busy Generators ---
    assign z80_wait_n = (z80_card_hit && (bus_state != BUS_Z80)) ? 1'b0 : 1'b1;
    assign shd_busy_n = (!shadow_en_n && (bus_state != BUS_SHADOW)) ? 1'b0 : 1'b1;

    // --- Transceiver Output Enables (Active Low) ---
    assign z80_addr_oe_n = (bus_state == BUS_Z80)    ? 1'b0 : 1'b1;
    assign z80_data_oe_n = (bus_state == BUS_Z80)    ? 1'b0 : 1'b1;

    assign shd_addr_oe_n = (bus_state == BUS_SHADOW) ? 1'b0 : 1'b1;
    assign shd_data_oe_n = (bus_state == BUS_SHADOW) ? 1'b0 : 1'b1;

    // --- Transceiver Direction Controls ---
    assign z80_data_dir = (!z80_rd_n) ? 1'b0 : 1'b1; 
    assign shd_data_dir = (shd_rw_n)  ? 1'b0 : 1'b1;

endmodule