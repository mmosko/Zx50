`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_mmu_sram
 * =====================================================================================
 * DESCRIPTION:
 * The Memory Management Unit (MMU) acts as a passive, snoop-based paging controller.
 * It maps the Z80's limited 64KB logical address space into a much larger 1MB 
 * physical address space using 4KB pages.
 *
 * ARCHITECTURAL RULES & MECHANICS:
 * 1. SNOOP PROTOCOL: The MMU passively monitors the Z80 bus for I/O writes. It 
 * specifically listens for `OUT (C), A` instructions where the base port is 
 * 0x30 (the MMU Family ID).
 * 2. DISTRIBUTED OWNERSHIP: Instead of a single central MMU, every memory card 
 * has its own MMU. When an I/O write occurs, the MMU checks if the target 
 * matches its specific `card_id_sw`. If it matches, it claims the page in its 
 * `page_ownership` mask. If it doesn't match, it actively drops ownership. 
 * This guarantees zero bus contention across multiple cards.
 * 3. HARDWARE WIPE: On power-up/reset, the MMU autonomously steps through a 
 * 16-clock-cycle sequence to safely zero out the external Address Translation 
 * Lookaside (ATL) SRAM before allowing the Z80 to boot.
 * 4. ROM KILL-SWITCH: Card 0 starts with `is_rom_enabled` High, instructing the 
 * CPLD routing matrix to bypass the ATL SRAM and boot from the physical ROM. 
 * If the Z80 maps ANY RAM page into the lower 32KB (Logical Pages 0-7), the MMU 
 * permanently flips this kill-switch Low, hiding the ROM and exposing the RAM.
 ***************************************************************************************/

module zx50_mmu_sram (
    input wire mclk,              
    input wire reset_n,           
    input wire boot_en_n,         // Hardware flag: 0 = Boot ROM Card, 1 = Normal RAM Card
    input wire [3:0] card_id_sw,  

    // --- Backplane & Local Bus Inputs ---
    input wire [15:0] z80_addr,   
    input wire [7:0] l_data,      
    
    // --- Z80 Control Signals ---
    input wire z80_iorq_n, 
    input wire z80_wr_n, 
    input wire z80_mreq_n, 

    // --- Address Translation Table (ATL / ISSI SRAM) ---
    output wire [3:0] atl_addr,   // 4-bit address to access the 16 logical page slots
    output wire atl_we_n,         // Write Enable for the ATL SRAM
    output wire atl_oe_n,         // Output Enable for the ATL SRAM
    
    // --- Status & Arbiter Outputs ---
    output wire active,           // High when the Z80 targets a memory page owned by this card
    output wire z80_card_hit,     // High when the Z80 targets this card for Memory OR I/O
    output wire is_busy,          // High during the 16-cycle Hardware Wipe or an I/O update
    output wire cpu_updating,     // High when the Z80 is actively reprogramming a page
    output reg is_initializing,   // High during the 16-cycle Hardware Wipe
    output reg [3:0] init_ptr,    // Counter used to iterate through the 16 ATL slots during wipe

    // --- ROM Bypass Flags (To Top-Level Routing) ---
    output wire is_rom_enabled    // The raw kill-switch state (1 = ROM active, 0 = RAM active)
);

    // I/O Address Space configuration for the MMU family
    localparam MMU_FAMILY_ID = 8'h30;
    localparam MMU_MASK      = 8'hF0;

    // Decodes the top 4 bits of the Z80 address into a 1-hot 16-bit mask for fast ownership checking
    wire [15:0] decoded_page = (16'b1 << z80_addr[15:12]);
    
    reg [15:0] page_ownership;    // Bitmask: 1 = Card owns this logical page, 0 = Ignored
    reg        reset_armed;
    reg        sync_we;           // Synchronized write enable strobe for the external ATL SRAM
    reg        rom_enabled;       // Internal kill-switch flip-flop

    assign is_rom_enabled = rom_enabled;

    // ==========================================
    // Synchronous State Machine
    // ==========================================
    always @(posedge mclk) begin
        if (!reset_n) begin
            // --- ASYNCHRONOUS RESET LOGIC ---
            if (!reset_armed) begin
                is_initializing <= 1'b1;
                init_ptr        <= 4'h0;
                reset_armed     <= 1'b1;
                
                // If this is the Boot Card (Card 0), enable the ROM bypass and preemptively 
                // claim the bottom 32KB of the logical map (Pages 0-7, mask 0x00FF).
                rom_enabled     <= !boot_en_n;
                page_ownership  <= (!boot_en_n) ? 16'h00FF : 16'h0000;    
            end
            
            // --- 16-CYCLE HARDWARE WIPE ---
            // Iterates through init_ptr 0x0 to 0xF, writing zeroes to the ATL SRAM.
            if (is_initializing) begin
                if (init_ptr == 4'hF) is_initializing <= 1'b0;
                else                  init_ptr <= init_ptr + 1'b1;
            end
            
            sync_we <= 1'b0;
        end else begin
            reset_armed     <= 1'b0;
            is_initializing <= 1'b0;

            // --- SNOOP LOGIC: MMU FAMILY I/O WRITE ---
            // Triggers if the Z80 executes an I/O write targeting the 0x3X port range.
            if (!z80_iorq_n && !z80_wr_n && ((z80_addr[7:0] & MMU_MASK) == MMU_FAMILY_ID)) begin
                
                // Does the exact port match this specific card's ID? (e.g., 0x30 for Card 0, 0x31 for Card 1)
                if (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)) begin
                    
                    // Claim the logical page (Z80 B register / A[11:8] holds the logical page number)
                    page_ownership[z80_addr[11:8]] <= 1'b1;
                    
                    // KILL SWITCH: If the CPU maps ANY physical page into the lower 32K 
                    // of the logical space (Pages 0-7, where A[11] is 0), permanently disable the Boot ROM.
                    if (z80_addr[11] == 1'b0) begin
                        rom_enabled <= 1'b0;
                    end
                end else begin
                    // Another memory card on the backplane claimed this logical page. 
                    // Drop ownership to prevent physical bus contention.
                    page_ownership[z80_addr[11:8]] <= 1'b0;
                end
            end

            // Generate a 1-clock pulse to write the physical page target into the ATL SRAM
            sync_we <= (!is_initializing && !z80_iorq_n && !z80_wr_n && 
                       (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)));
        end
    end

    // ==========================================
    // ATL (ISSI SRAM) Interface Logic
    // ==========================================
    // Combinatorial flag: True when the Z80 is writing to THIS card's MMU port
    wire l_cpu_updating = (!is_initializing && !z80_iorq_n && !z80_wr_n && 
                          (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)));

    assign cpu_updating = l_cpu_updating;

    // Clean Hardware Routing: The MMU handles its own upper address slicing.
    // 1. During wipe: Use the internal counter (init_ptr).
    // 2. During update: Use the Z80's B register (A[11:8]) as the target slot.
    // 3. During normal memory access: Use the Z80's active logical page (A[15:12]).
    assign atl_addr = is_initializing ? {1'b0, init_ptr} : 
                      (l_cpu_updating   ? z80_addr[11:8] : z80_addr[15:12]);

    // Write Enable is held low continuously during the 16-cycle wipe, or pulsed by sync_we.
    assign atl_we_n = is_initializing ? !mclk : !sync_we;

    // Turn off the ATL SRAM output buffer if we are writing to it. 
    // Note: The top-level CPLD routing matrix will forcefully override this if the ROM bypass is active.
    assign atl_oe_n = (is_initializing || l_cpu_updating) ? 1'b1 : 1'b0;

    // ==========================================
    // Active & Hit Signal Logic
    // ==========================================
    // Uses the 1-hot decoded page mask to instantly check if the `page_ownership` register has a '1' in the target slot.
    wire current_page_owned = |(page_ownership & decoded_page);
    
    // Asserts active only if it's a valid memory cycle, the hardware wipe is done, and we own the page.
    assign active = (reset_n && !is_initializing && !z80_mreq_n && current_page_owned);

    // Arbiter flag: The card is being targeted for either memory retrieval or an I/O update.
    assign z80_card_hit = active || l_cpu_updating;
    
    // Arbiter flag: The MMU is mutating state and cannot safely handle memory requests.
    assign is_busy = is_initializing || l_cpu_updating;

    initial begin
        is_initializing = 1'b0;
        init_ptr        = 4'h0;
        reset_armed     = 1'b0;
        page_ownership  = 16'h0000;
        rom_enabled     = 1'b0;
        sync_we         = 1'b0;
    end
endmodule