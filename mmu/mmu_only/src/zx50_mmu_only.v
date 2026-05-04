`timescale 1ns/1ps

module zx50_mmu_only (
    input  wire mclk,
    input  wire zclk,
    input  wire reset_n,

    // Z80 Backplane
    input  wire [15:0] z80_a,
    input  wire b_z80_mreq_n,
    input  wire b_z80_iorq_n,
    input  wire b_z80_rd_n,
    input  wire b_z80_wr_n,
    input  wire b_z80_m1_n,
    
    output wire wait_n, 
    output wire int_n,  

    // Transceiver & Local Bus
    output wire z80_d_oe_n, 
    output wire d_dir,      
    inout  wire [7:0] l_d,
    output wire [10:0] l_a,
    
    output reg  oe_n,
    output reg  we_n,
    output reg  ram_ce0_n,
    output reg  ram_ce1_n,
    output reg  rom_ce2_n,

    // ATL 
    inout  wire [7:0] atl_d,
    output reg  [3:0] atl_a,
    output reg  atl_ce_n,
    output wire atl_oe_n,
    output reg  atl_we_n,
    
    // Shadow Bus Pins
    inout  wire sh_en_n,      
    inout  wire sh_rw_n,      
    inout  wire sh_busy_n,    
    output wire sh_data_oe_n,
    inout  wire sh_inc_n,
    inout  wire sh_stb_n,
    inout  wire sh_done_n,
    output wire sh_c_dir,

    // Diagnostic Heartbeat (Pin 100)
    output wire hb_led_n
);

    // ==========================================
    // 1. LOGIC ANCHOR & HEARTBEAT (Contention Fix)
    // ==========================================
    wire logic_anchor = ^z80_a ^ b_z80_mreq_n ^ b_z80_iorq_n ^ b_z80_rd_n ^ b_z80_wr_n ^ b_z80_m1_n;
    
    reg [21:0] hb_counter;
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) hb_counter <= 22'd0;
        else hb_counter <= hb_counter + 1'b1;
    end
    assign hb_led_n = hb_counter[21] ^ logic_anchor;

    // ==========================================
    // 2. INTERNAL STATE & DECODING
    // ==========================================
    reg [1:0]  card_addr; 
    reg        has_boot_rom;
    reg        rom_enabled;
    reg [15:0] page_ownership;
    reg        init_done;

    wire [3:0] logical_index = z80_a[15:12];

    wire is_card_0     = (card_addr == 2'h0);
    wire card_addr_hit = (z80_a[3:2] == 2'b00) && (z80_a[1:0] == card_addr);
    
    wire is_mmu_port   = z80_a[7:4] == 4'h3;
    wire iorq_wr_hit   = (!b_z80_iorq_n && !b_z80_wr_n);
    wire mmu_snoop_wr  = (iorq_wr_hit && is_mmu_port);
    wire mmu_direct_wr = mmu_snoop_wr && card_addr_hit;

    wire effective_use_rom = is_card_0 && rom_enabled && (z80_a[15] == 1'b0) && !b_z80_mreq_n;
    wire ram_hit           = !b_z80_mreq_n && page_ownership[logical_index] && !effective_use_rom;

    wire z80_card_hit      = ram_hit || effective_use_rom || mmu_direct_wr;

    // ==========================================
    // 3. TRANSCEIVER & BUS ROUTING
    // ==========================================
    // Disable Z80 transceiver unless this card is explicitly addressed
    assign z80_d_oe_n = !z80_card_hit;
    
    // Direction: 0 = Outward to Z80 (Read), 1 = Inward from Z80 (Write)
    assign d_dir = (!b_z80_rd_n) ? 1'b0 : 1'b1; 
    
    assign l_a   = z80_a[10:0];

    // --- ACTIVE PARKING (Shoot-Through Protection) ---
    // If the Z80 isn't accessing the card, park the buses at 0V
    wire bus_idle = !z80_card_hit;
    assign l_d    = bus_idle ? 8'h00 : 8'hZZ; 

    // ATL Bus Routing
    wire cpld_driving_atl = mmu_direct_wr || effective_use_rom;
    wire local_atl_oe_n   = !(ram_hit && !cpld_driving_atl);
    
    // During a ROM hit, the CPLD mimics the ATL SRAM by driving the physical address A[19:12]
    wire [7:0] local_atl_d = mmu_direct_wr ? l_d : 
                             (effective_use_rom ? {3'b000, z80_a[15:11]} : 8'h00);
                             
    assign atl_d    = cpld_driving_atl ? local_atl_d : (local_atl_oe_n ? 8'h00 : 8'hZZ);
    assign atl_oe_n = local_atl_oe_n;

    // ==========================================
    // 4. SHADOW BUS & DMA ISOLATION
    // ==========================================
    // Hard-wire all Shadow and DMA features to safe idle states
    assign wait_n       = 1'b1;
    assign int_n        = 1'bz;
    assign sh_en_n      = 1'bz;      
    assign sh_rw_n      = 1'bz;      
    assign sh_busy_n    = 1'bz;    
    assign sh_data_oe_n = 1'b1;
    assign sh_inc_n     = 1'bz;
    assign sh_stb_n     = 1'bz;
    assign sh_done_n    = 1'bz;
    assign sh_c_dir     = 1'b1;

    // ==========================================
    // 5. COMBINATORIAL MEMORY CONTROL
    // ==========================================
    always @(*) begin
        // Safe Defaults
        oe_n       = 1'b1;
        we_n       = 1'b1;
        ram_ce0_n  = 1'b1;
        ram_ce1_n  = 1'b1;
        rom_ce2_n  = 1'b1;
        atl_ce_n   = 1'b1;
        atl_we_n   = 1'b1;
        atl_a      = logical_index; // Always output logical page to ATL SRAM

        if (mmu_direct_wr) begin
            atl_ce_n = 1'b0;
            atl_we_n = b_z80_wr_n;

        end else if (effective_use_rom) begin
            rom_ce2_n = 1'b0;
            oe_n      = b_z80_rd_n;
            we_n      = 1'b1; // ROM is read-only
            
        end else if (ram_hit) begin
            atl_ce_n = 1'b0;
            atl_we_n = 1'b1; 
            
            if (z80_a[11] == 1'b0) ram_ce0_n = 1'b0;
            else                   ram_ce1_n = 1'b0;
            
            oe_n = b_z80_rd_n;
            we_n = b_z80_wr_n;
        end
    end

    // ==========================================
    // 6. SYNCHRONOUS LOGIC (MMU & RESET)
    // ==========================================
    always @(posedge zclk) begin
        if (!reset_n) begin
            card_addr      <= {b_z80_rd_n, b_z80_wr_n};
            has_boot_rom   <= ({b_z80_rd_n, b_z80_wr_n} == 2'h0);
            rom_enabled    <= ({b_z80_rd_n, b_z80_wr_n} == 2'h0);
            page_ownership <= 16'h0000;
            init_done      <= 1'b0;
        end else begin
            if (!init_done) begin
                init_done <= 1'b1;
                if (has_boot_rom) page_ownership[7:0] <= 8'hFF; 
            end

            if (mmu_snoop_wr) begin
                if (logical_index[3] == 1'b0) rom_enabled <= 1'b0;
                page_ownership[logical_index] <= mmu_direct_wr;
            end
        end
    end

endmodule

