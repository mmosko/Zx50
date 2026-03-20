`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_mmu_sram
 * DESCRIPTION:
 * The Memory Management Unit.
 * Snoops the Z80 bus for I/O writes to its specific Hardware ID.
 * Exposes a raw kill-switch state (is_rom_enabled) to the top-level routing 
 * matrix to allow for linear ROM booting until the Z80 programs a RAM page in the lower 32K.
 ***************************************************************************************/

module zx50_mmu_sram (
    input wire mclk,              
    input wire reset_n,           
    input wire boot_en_n,         // 0 = Boot ROM Card, 1 = Normal RAM Card
    input wire [3:0] card_id_sw,  

    // --- Backplane & Local Bus Inputs ---
    input wire [15:0] z80_addr,   
    input wire [15:11] l_addr_hi, // Active Master's Top 5 Bits (Includes A[11])
    input wire [7:0] l_data,      
    
    // --- Z80 Control Signals ---
    input wire z80_iorq_n, 
    input wire z80_wr_n, 
    input wire z80_mreq_n, 

    // --- Address Translation Table (ATL / ISSI SRAM) ---
    output wire [3:0] atl_addr,   
    output wire atl_we_n,
    output wire atl_oe_n,
    
    // --- Status & Arbiter Outputs ---
    output wire active,           
    output wire z80_card_hit,     
    output wire is_busy,          
    output wire cpu_updating,
    output reg is_initializing,
    output reg [3:0] init_ptr,

    // --- ROM Bypass Flags (To Top-Level Routing) ---
    output wire is_rom_enabled
);

    localparam MMU_FAMILY_ID = 8'h30;
    localparam MMU_MASK      = 8'hF0;

    wire [15:0] decoded_page = (16'b1 << z80_addr[15:12]);
    
    reg [15:0] page_ownership;
    reg        reset_armed;
    reg        sync_we;
    reg        rom_enabled; // Flip-flop: 1 = ROM bypass active

    assign is_rom_enabled = rom_enabled;

    // ==========================================
    // Synchronous State Machine
    // ==========================================
    always @(posedge mclk) begin
        if (!reset_n) begin
            if (!reset_armed) begin
                is_initializing <= 1'b1;
                init_ptr        <= 4'h0;
                reset_armed     <= 1'b1;
                // If Boot Card, enable ROM and claim Pages 0-7 (0x0000 - 0x7FFF)
                rom_enabled     <= !boot_en_n;
                page_ownership  <= (!boot_en_n) ? 16'h00FF : 16'h0000;    
            end
            
            if (is_initializing) begin
                if (init_ptr == 4'hF) is_initializing <= 1'b0;
                else                  init_ptr <= init_ptr + 1'b1;
            end
            
            sync_we <= 1'b0;
        end else begin
            reset_armed     <= 1'b0;
            is_initializing <= 1'b0;

            // Snoop Logic: MMU Family I/O Write
            if (!z80_iorq_n && !z80_wr_n && ((z80_addr[7:0] & MMU_MASK) == MMU_FAMILY_ID)) begin
                if (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)) begin
                    // Claim the page
                    page_ownership[z80_addr[11:8]] <= 1'b1;
                    // KILL SWITCH: If the CPU programs ANY page in the lower 32K 
                    // (Logical Pages 0-7, where A[11] of the port data is 0), disable the ROM forever.
                    if (z80_addr[11] == 1'b0) begin
                        rom_enabled <= 1'b0;
                    end
                end else begin
                    // Another card claimed this page. Drop ownership.
                    page_ownership[z80_addr[11:8]] <= 1'b0;
                end
            end

            sync_we <= (!is_initializing && !z80_iorq_n && !z80_wr_n && 
                       (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)));
        end
    end

    // ==========================================
    // ATL (ISSI SRAM) Interface Logic
    // ==========================================
    wire l_cpu_updating = (!is_initializing && !z80_iorq_n && !z80_wr_n && 
                          (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)));

    assign cpu_updating = l_cpu_updating;

    assign atl_addr = is_initializing ? {1'b0, init_ptr} : 
                      (l_cpu_updating   ? z80_addr[11:8] : l_addr_hi[15:12]);

    assign atl_we_n = is_initializing ? !mclk : !sync_we;

    // Normal internal MMU logic. Top-level will override this if ROM is active.
    assign atl_oe_n = (is_initializing || l_cpu_updating) ? 1'b1 : 1'b0;

    // ==========================================
    // Active & Hit Signal Logic
    // ==========================================
    wire current_page_owned = |(page_ownership & decoded_page);
    assign active = (reset_n && !is_initializing && !z80_mreq_n && current_page_owned);

    assign z80_card_hit = active || l_cpu_updating;
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