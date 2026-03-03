`timescale 1ns/1ps

module zx50_bus_arbiter (
    input wire mclk,            // High-speed Master Clock (e.g., 36MHz)
    input wire reset_n,         // System Reset

    // --- Backplane Command Inputs ---
    input wire shadow_en_n,     // 0 = Shadow Bus requests control of this card
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

    // State Machine Definitions
    localparam BUS_Z80     = 2'b00;
    localparam BUS_DEAD_1  = 2'b01; // Break-before-make transition to Shadow
    localparam BUS_SHADOW  = 2'b10;
    localparam BUS_DEAD_2  = 2'b11; // Break-before-make transition to Z80

    reg [1:0] bus_state;

    // --- Clocked State Machine ---
    // Enforces a strict 1-clock-cycle dead zone during any bus handover
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            bus_state <= BUS_Z80;
        end else begin
            case (bus_state)
                BUS_Z80: begin
                    // If Shadow Bus is enabled, disconnect Z80 and enter Dead Zone 1
                    if (!shadow_en_n) bus_state <= BUS_DEAD_1;
                end
                BUS_DEAD_1: begin
                    // Dead Zone complete. Hand over to Shadow Bus.
                    bus_state <= BUS_SHADOW;
                end
                BUS_SHADOW: begin
                    // If Shadow Bus releases, disconnect Shadow and enter Dead Zone 2
                    if (shadow_en_n)  bus_state <= BUS_DEAD_2;
                end
                BUS_DEAD_2: begin
                    // Dead Zone complete. Hand over back to Z80.
                    bus_state <= BUS_Z80;
                end
            endcase
        end
    end

    // --- Transceiver Output Enables (Active Low) ---
    // Safely enable buffers ONLY when the state machine is fully settled
    assign z80_addr_oe_n = (bus_state == BUS_Z80)    ? 1'b0 : 1'b1;
    assign z80_data_oe_n = (bus_state == BUS_Z80)    ? 1'b0 : 1'b1;

    assign shd_addr_oe_n = (bus_state == BUS_SHADOW) ? 1'b0 : 1'b1;
    assign shd_data_oe_n = (bus_state == BUS_SHADOW) ? 1'b0 : 1'b1;

    // --- Transceiver Direction Controls ---
    // Assumption: Transceiver Side A = Backplane, Side B = Local Card
    // DIR = 1 (A to B): Backplane writes TO Local Card
    // DIR = 0 (B to A): Local Card drives data OUT to Backplane
    
    // If Z80 is reading (rd_n = 0), card drives bus (0). Otherwise, Z80 drives card (1).
    assign z80_data_dir = (!z80_rd_n) ? 1'b0 : 1'b1; 
    
    // If Shadow is reading (shd_rw_n = 1), card drives bus (0). If writing (0), DMA drives card (1).
    assign shd_data_dir = (shd_rw_n)  ? 1'b0 : 1'b1;

endmodule
