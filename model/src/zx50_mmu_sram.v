`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_mmu_sram
 * DESCRIPTION:
 * The Memory Management Unit. Snoops the Z80 bus for I/O writes to its specific 
 * Hardware ID to update the Address Translation Lookaside (ATL) SRAM.
 * Translates the top 4 bits of the active master's address into an 8-bit physical page.
 * NOTE: atl_addr is 4 bits wide. The MSB is held to 0 by the MMU to target the LUT, 
 * leaving the upper half of the ATL SRAM available for scratchpad usage.
 ***************************************************************************************/

module zx50_mmu_sram (
    input wire mclk,              // 36-40MHz Master Clock
    input wire reset_n,           // System Reset
    input wire boot_en_n,         // Boot ROM override
    input wire [3:0] card_id_sw,  // Hardware DIP Switches

    // --- Backplane & Local Bus Inputs ---
    input wire [15:0] z80_addr,   // Private Z80 Address Bus (For snooping & hit detection)
    input wire [15:12] l_addr_hi, // Active Master's Top 4 Bits (Routed from Top-Level)
    input wire [7:0] l_data,      // Local Shared Data Bus 
    
    // --- Z80 Control Signals ---
    input wire z80_iorq_n, 
    input wire z80_wr_n, 
    input wire z80_mreq_n, 

    // --- Address Translation Table (ATL / ISSI SRAM) ---
    output wire [3:0] atl_addr,   // 4-bit address (Lower 16 = LUT, 5th bit removed to save space)
    output wire atl_we_n,
    output wire atl_oe_n,
    
    // --- Status & Arbiter Outputs ---
    output wire active,           // 1 = Z80 is actively reading/writing a mapped page
    output wire z80_card_hit,     // 1 = Card is targeted by Z80 (Mem Page OR I/O Update)
    output wire is_busy,          // 1 = MMU is currently writing to the ATL SRAM
    output wire cpu_updating,
    output reg is_initializing,
    output reg [3:0] init_ptr
);

    // ==========================================
    // MMU Parameters & Registers
    // ==========================================
    localparam MMU_FAMILY_ID = 8'h30; // Base I/O 0x30
    localparam MMU_MASK      = 8'hF0; // Mask to identify MMU family range

    // OPTIMIZATION: One-Hot Page Decoding
    // Instead of a massive 16-to-1 multiplexer that consumes routing resources, 
    // we decode the Z80 address directly into a one-hot wire.
    wire [15:0] decoded_page = (16'b1 << z80_addr[15:12]);
    
    // We store the 16-bit ownership map in a continuous state register
    reg [15:0] page_ownership;

    reg        reset_armed;
    reg        sync_we;            // Synchronized Write Enable for SRAM safety

    // ==========================================
    // Synchronous State Machine (Hardware Wipe & Snoop)
    // ==========================================
    always @(posedge mclk) begin
        if (!reset_n) begin
            if (!reset_armed) begin
                is_initializing <= 1'b1;
                init_ptr        <= 4'h0;
                reset_armed     <= 1'b1;
            
                // OPTIMIZATION: Always zero the map on reset. 
                // Firmware must configure the MMU via I/O before use.
                // page_ownership  <= 16'h0000;    

                // Boot override: If boot_en_n is low, claim top 8 pages automatically
                page_ownership  <= (!boot_en_n) ? 16'hFF00 : 16'h0000;

            end
            
            if (is_initializing) begin
                if (init_ptr == 4'hF) is_initializing <= 1'b0;
                else                  init_ptr <= init_ptr + 1'b1;
            end
            
            sync_we <= 1'b0; // Hold synchronous WE low during reset
            
        end else begin
            reset_armed     <= 1'b0;
            is_initializing <= 1'b0;

            // 1. Snoop Logic: Update ownership when ANY MMU card is programmed
            if (!z80_iorq_n && !z80_wr_n && ((z80_addr[7:0] & MMU_MASK) == MMU_FAMILY_ID)) begin
                // Claim the page if the sent ID matches our hardware switch ID
                if (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)) begin
                    page_ownership[z80_addr[11:8]] <= 1'b1;
                end else begin
                     page_ownership[z80_addr[11:8]] <= 1'b0;
                end
            end

            // 2. Synchronize the CPU write pulse for the external SRAM
            // This prevents backplane ringing from causing spurious SRAM writes
            sync_we <= (!is_initializing && !z80_iorq_n && !z80_wr_n && 
                       (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)));
        end
    end

    // ==========================================
    // ATL (ISSI SRAM) Interface Logic
    // ==========================================
    // Combinatorial flag for routing/muxing (does not rely on the clock edge)
    assign cpu_updating = (!is_initializing && !z80_iorq_n && !z80_wr_n && 
                        (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)));

    // ATL Address Multiplexer (MSB is forced to 0 to target the LUT half of the SRAM)
    // Init -> Use Counter | Z80 I/O -> Use Z80 A[11:8] | Run -> Use Active Master Top 4
    assign atl_addr = is_initializing ? {1'b0, init_ptr} : 
                      (cpu_updating   ? z80_addr[11:8] : l_addr_hi);

    // ATL Write Enable: High-speed clock pulse during init, or synchronized CPU pulse
    assign atl_we_n = is_initializing ? !mclk : !sync_we;

    // ATL Output Enable: 
    // Disable (High) when the CPLD is driving the bus to write.
    // Enable (Low) during normal run so the SRAM can drive p_addr_hi.
    assign atl_oe_n = (is_initializing || cpu_updating) ? 1'b1 : 1'b0;

    // ==========================================
    // Active & Hit Signal Logic (To Arbiter)
    // ==========================================
    
    // Check if the Z80's current memory address belongs to a page this card owns.
    // This simple bitwise AND completely eliminates the massive 16-to-1 multiplexer!
    wire current_page_owned = |(page_ownership & decoded_page);

    // 'active' strictly means a Memory Read/Write cycle targeting our SRAM
    assign active = (reset_n && !is_initializing && !z80_mreq_n && current_page_owned);

    // 'z80_card_hit' alerts the Arbiter if the Z80 is doing a Memory cycle OR an I/O update
    assign z80_card_hit = active || cpu_updating;

    assign is_busy = is_initializing || cpu_updating;

    // ==========================================
    // CPLD Power-On-Reset (POR) Emulation
    // ==========================================
    initial begin
        is_initializing = 1'b0;
        init_ptr        = 4'h0;
        reset_armed     = 1'b0;
        page_ownership  = 16'h0000;
        sync_we         = 1'b0;
    end
endmodule
