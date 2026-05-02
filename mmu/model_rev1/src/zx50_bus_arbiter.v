`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_bus_arbiter
 * =====================================================================================
 * DESCRIPTION:
 * A 4-state synchronous bus arbiter. It ensures absolute mutual exclusion between 
 * the Z80 Backplane transceivers and the Shadow DMA transceivers on a single card.
 *
 * ARCHITECTURAL RULES & GOTCHAS:
 * 1. The Z80 is the default bus master. It owns the local bus upon reset.
 * 2. The Shadow DMA can only cycle-steal if the Z80 is NOT currently targeting 
 * this specific card (z80_card_hit == 0).
 * 3. BREAK-BEFORE-MAKE: Hardware transceivers take a few nanoseconds to turn off. 
 * If we flip bus ownership instantly, both transceivers will drive the bus 
 * simultaneously, causing a massive current spike (magic smoke). This module 
 * injects mandatory 1-clock "DEAD" states during handoffs to let the lines settle.
 * 4. STALLING: If a master tries to access the card while it doesn't have ownership, 
 * the arbiter immediately pulls that master's WAIT/BUSY line low to stall it 
 * until ownership can be safely handed over.
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
    // State Definitions
    localparam BUS_Z80    = 2'b00;
    localparam BUS_DEAD_1 = 2'b01; 
    localparam BUS_SHADOW = 2'b10;
    localparam BUS_DEAD_2 = 2'b11;
    
    reg [1:0] bus_state;

    // ==========================================
    // 1. Clocked Arbitration State Machine
    // ==========================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            bus_state <= BUS_Z80; // Z80 is the primary master on boot
        end else begin
            case (bus_state)
                // Z80 OWNS THE BUS: 
                // Yield to the Shadow Bus ONLY if the Z80 isn't actively hitting this card.
                BUS_Z80: begin
                    if (!sh_en_n && !z80_card_hit) bus_state <= BUS_DEAD_1;
                end
                
                // DEAD STATE 1: Break-before-make buffer isolation
                // Guarantees Z80 transceivers are fully off before Shadow transceivers turn on.
                BUS_DEAD_1: bus_state <= BUS_SHADOW;
                
                // SHADOW OWNS THE BUS: 
                // Yield back to Z80 as soon as the Shadow DMA drops its request.
                BUS_SHADOW: begin
                    if (sh_en_n) bus_state <= BUS_DEAD_2;
                end
                
                // DEAD STATE 2: Break-before-make buffer isolation
                BUS_DEAD_2: bus_state <= BUS_Z80;
            endcase
        end
    end

    // ==========================================
    // 2. The Wait / Busy Generators
    // ==========================================
    // GOTCHA: These are combinatorial. They must assert instantly to catch the CPU/DMA.
    
    // If Z80 targets the card but doesn't own the bus, assert WAIT instantly.
    assign z80_wait_n = (z80_card_hit && (bus_state != BUS_Z80)) ? 1'b0 : 1'b1;
    
    // If Shadow bus wants the card but doesn't own it, assert BUSY instantly.
    assign sh_busy_n = (!sh_en_n && (bus_state != BUS_SHADOW)) ? 1'b0 : 1'b1;

    // ==========================================
    // 3. Transceiver Output Enables
    // ==========================================
    // Only open the specific transceiver if that bus is fully in the active state.
    // They are forced High (closed) during DEAD_1 and DEAD_2.
    assign z80_data_oe_n = ~((bus_state == BUS_Z80) && z80_card_hit);
    assign sh_data_oe_n  = ~((bus_state == BUS_SHADOW) && !sh_en_n);

    // ==========================================
    // 4. Shared Direction Control (l_dir)
    // ==========================================
    // Hardware Rule: 1 = Master writing to Card, 0 = Card outputting to Master
    // GOTCHA - Polarity Inversion: 
    //   - For Z80: RD_n is Active-LOW (0 means Z80 wants to read).
    //   - For DMA: RW_n is Active-HIGH (1 means Shadow wants to read).
    // This multiplexer safely unifies them into a single l_dir pin.
    assign l_dir = (bus_state == BUS_Z80)    ? z80_rd_n :
                   (bus_state == BUS_SHADOW) ? !sh_rw_n : 
                                               1'b1; // Default inward (Write) for safety during dead states
endmodule