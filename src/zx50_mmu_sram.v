`timescale 1ns/1ps

module zx50_mmu_sram (
    input wire mclk,              // 24MHz/36MHz Master Clock
    input wire [15:0] z80_addr,   // Z80 Address Bus (For snooping MMU updates)
    input wire [15:12] l_addr_hi, // Local Address Bus (Driven by Arbiter/Transceivers)
    input wire [7:0] z80_data,    // Z80 Data Bus
    input wire z80_iorq_n, z80_wr_n, z80_mreq_n, reset_n,
    input wire boot_en_n,
    input wire [3:0] card_id_sw,

    // --- Address Translation Table (ATL) ---
    output wire [3:0] atl_addr, 
    inout  wire [7:0] atl_data,
    output wire atl_we_n,
    output wire atl_oe_n,
    
    output wire [7:0] p_addr_hi,
    output wire active,
    output wire z80_card_hit
);

    // MMU Parameters
    localparam MMU_FAMILY_ID = 8'h30;  // Base I/O 0x30
    localparam MMU_MASK      = 8'hF0;  // Mask to identify MMU family range

    reg [15:0] pal_bits;
    reg [3:0]  init_ptr;
    reg        is_initializing;
    reg        reset_armed;

    // --- Synchronous State Machine (Hardware Wipe) ---
    always @(posedge mclk) begin
        if (!reset_n) begin
            if (!reset_armed) begin
                is_initializing <= 1'b1;
                init_ptr        <= 4'h0;
                reset_armed     <= 1'b1;
                pal_bits <= (!boot_en_n) ? 16'hFF00 : 16'h0000;
            end
            
            if (is_initializing) begin
                if (init_ptr == 4'hF) is_initializing <= 1'b0;
                else                  init_ptr <= init_ptr + 1'b1;
            end
        end else begin
            reset_armed     <= 1'b0;
            is_initializing <= 1'b0;

            // Snoop Logic: Update ownership when ANY MMU card is programmed
            if (!z80_iorq_n && !z80_wr_n && ((z80_addr[7:0] & MMU_MASK) == MMU_FAMILY_ID)) begin
                pal_bits[z80_addr[11:8]] <= (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw));
            end
        end
    end

    // --- ATL Interface Logic ---
    wire cpu_updating = (!is_initializing && !z80_iorq_n && !z80_wr_n && 
                        (z80_addr[7:0] == (MMU_FAMILY_ID | card_id_sw)));
    
    // ATL Address Multiplexer:
    assign atl_addr = is_initializing ? init_ptr : 
                      (cpu_updating   ? z80_addr[11:8] : l_addr_hi);

    // ATL Write Enable: High-speed pulse during init or gated CPU pulse
    assign atl_we_n = is_initializing ? !mclk : !cpu_updating;

    // ATL Output Enable: 
    // Disable (1) only when the CPLD is driving the bus (is_initializing OR cpu_updating).
    // Enable (0) otherwise so the ATL can drive p_addr_hi for the backplane.
    assign atl_oe_n = (is_initializing || cpu_updating) ? 1'b1 : 1'b0;

    // ATL Data: Drive the bus ONLY when we are writing
    assign atl_data = is_initializing ? {4'h0, init_ptr} : 
                      (cpu_updating   ? z80_data : 8'hzz);

    // The physical address output is whatever is on the ATL data bus
    assign p_addr_hi = atl_data;

    // --- Active & Hit Signal Logic ---
    wire current_page_owned = pal_bits[z80_addr[15:12]];
    
    assign active = (reset_n && !is_initializing && !z80_mreq_n && current_page_owned) ? 1'b1 : 1'b0;
    assign z80_card_hit = active || cpu_updating;

endmodule