module zx50_mmu_sram (
    input wire mclk,             // 24MHz Master Clock
    input wire [15:0] addr,      // Z80 Address Bus
    input wire [7:0] d_bus,      // Z80 Data Bus
    input wire iorq_n, wr_n, mreq_n, reset_n,
    input wire boot_en_n,
    input wire [3:0] card_id_sw,

    output wire [3:0] sram_a,
    inout  wire [7:0] sram_d,
    output wire sram_we_n,
    output wire sram_oe_n,
    
    output wire [7:0] p_addr_hi,
    output wire active
);

    // MMU Parameters
    localparam MMU_FAMILY_ID = 8'h30;  // Base I/O 0x30
    localparam MMU_MASK      = 8'hF0;  // Mask to identify MMU family range

    reg [15:0] pal_bits;
    reg [3:0]  init_ptr;
    reg        is_initializing;
    reg        reset_armed;

    // --- Synchronous State Machine (24MHz Hardware Wipe) ---
    always @(posedge mclk) begin
        if (!reset_n) begin
            if (!reset_armed) begin
                is_initializing <= 1'b1;
                init_ptr        <= 4'h0;
                reset_armed     <= 1'b1;
                // Primary card owns top 32KB on boot
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
            if (!iorq_n && !wr_n && ((addr[7:0] & MMU_MASK) == MMU_FAMILY_ID)) begin
                // The Z80 places the 'B' register on A15-A8 during OUT (C), r.
                // We use A11-A8 to select the page to update.
                pal_bits[addr[11:8]] <= (addr[7:0] == (MMU_FAMILY_ID | card_id_sw));
            end
        end
    end

    // --- SRAM Interface Logic ---
    wire cpu_updating = (!is_initializing && !iorq_n && !wr_n && 
                        (addr[7:0] == (MMU_FAMILY_ID | card_id_sw)));
    
    // SRAM Address Multiplexer:
    // - During init: use init_ptr
    // - During I/O update: use addr[11:8] (Z80 places target page here)
    // - Normal operation: use addr[15:12] (Z80 memory page)
    assign sram_a = is_initializing ? init_ptr : 
                    (cpu_updating   ? addr[11:8] : addr[15:12]);

    // SRAM Write Enable: High-speed pulse during init or gated CPU pulse
    assign sram_we_n = is_initializing ? !mclk : !cpu_updating;

    // SRAM Output Enable: 
    // Disable (1) only when the CPLD is driving the bus (is_initializing OR cpu_updating).
    // Enable (0) otherwise so the SRAM can drive p_addr_hi for the backplane.
    assign sram_oe_n = (is_initializing || cpu_updating) ? 1'b1 : 1'b0;

    // SRAM Data: Drive the bus ONLY when we are writing
    assign sram_d = is_initializing ? {4'h0, init_ptr} : 
                    (cpu_updating   ? d_bus : 8'hzz);

    // The physical address output is whatever is on the SRAM data bus
    assign p_addr_hi = sram_d;

    // --- Active Signal Logic ---
    wire current_page_owned = pal_bits[addr[15:12]];
    
    // Explicitly drive 0 or 1. If we own the page and it's a memory request, we are active.
    assign active = (reset_n && !is_initializing && !mreq_n && current_page_owned) ? 1'b1 : 1'b0;

endmodule