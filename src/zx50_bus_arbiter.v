`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_bus_arbiter
 * DESCRIPTION:
 * A 4-state synchronous bus arbiter. Ensures absolute mutual exclusion between 
 * the Z80 Backplane and the Shadow DMA bus. Injects 1-clock "Dead States" during 
 * handoffs to guarantee transceivers never cross-conduct (preventing magic smoke).
 * Controls the shared l_dir pin for the unified local data bus.
 ***************************************************************************************/

module zx50_bus_arbiter (
    input wire mclk,            
    input wire reset_n,         

    // --- Bus Requests & Status ---
    input wire sh_en_n,         // Active-low request from the Shadow DMA Bus
    input wire z80_card_hit,    // High when the Z80 is targeting this specific card

    // --- Wait State Generators ---
    output wire z80_wait_n,     // Commands the Z80 to wait if the Shadow bus owns the card
    output wire sh_busy_n,      // Commands the Shadow bus to yield if Z80 owns the card

    // --- Backplane Command Inputs ---
    input wire z80_rd_n,        
    input wire sh_rw_n,         

    // --- Transceiver Controls ---
    output wire z80_data_oe_n,  // Z80 Data Buffer Enable
    output wire sh_data_oe_n,   // Shadow Data Buffer Enable
    output wire l_dir           // SHARED Direction Line (1 = In/Write, 0 = Out/Read)
);

    localparam BUS_Z80    = 2'b00;
    localparam BUS_DEAD_1 = 2'b01; 
    localparam BUS_SHADOW = 2'b10;
    localparam BUS_DEAD_2 = 2'b11; 

    reg [1:0] bus_state;

    // --- Clocked State Machine ---
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            bus_state <= BUS_Z80; // Default to Z80 ownership on boot
        end else begin
            case (bus_state)
                // Z80 OWNS THE BUS: Yield to Shadow ONLY if Z80 isn't actively hitting the card
                BUS_Z80: begin
                    if (!sh_en_n && !z80_card_hit) bus_state <= BUS_DEAD_1;
                end
                
                // DEAD STATE 1: Break-before-make buffer isolation
                BUS_DEAD_1: bus_state <= BUS_SHADOW;
                
                // SHADOW OWNS THE BUS: Yield back to Z80 as soon as Shadow drops its enable
                BUS_SHADOW: begin
                    if (sh_en_n) bus_state <= BUS_DEAD_2;
                end
                
                // DEAD STATE 2: Break-before-make buffer isolation
                BUS_DEAD_2: bus_state <= BUS_Z80;
            endcase
        end
    end

    // --- The Wait / Busy Generators ---
    // If Z80 targets the card but doesn't own the bus, assert WAIT
    assign z80_wait_n = (z80_card_hit && (bus_state != BUS_Z80)) ? 1'b0 : 1'b1;
    
    // If Shadow bus wants the card but doesn't own it, assert BUSY
    assign sh_busy_n = (!sh_en_n && (bus_state != BUS_SHADOW)) ? 1'b0 : 1'b1;

    // --- Transceiver Output Enables ---
    // Only open the specific transceiver if that bus is fully in the active state
    assign z80_data_oe_n = ~((bus_state == BUS_Z80) && z80_card_hit);
    assign sh_data_oe_n  = ~((bus_state == BUS_SHADOW) && !sh_en_n);

    // --- Direction Control ---
    // 1 = Master writing to Card, 0 = Card outputting to Master
    // For Z80: RD_n low (0) means Z80 wants to read (Card outputs: dir=0)
    // For Shadow: RW_n high (1) means Shadow wants to read (Card outputs: dir=0)
    assign l_dir = (bus_state == BUS_Z80)    ? z80_rd_n :
                   (bus_state == BUS_SHADOW) ? !sh_rw_n : 1'b1; // Default inward for safety

endmodule