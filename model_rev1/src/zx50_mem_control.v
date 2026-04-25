`timescale 1ns/1ps

`ifdef HW_REV_A11_BUG
// ==========================================
// ATMEL FITTER PIN CONSTRAINTS (RevA Hardware - A11 Bug)
// TODO: Some of these names were changed need to update
// ==========================================
//PIN: 87 = mclk;
//PIN: 90 = zclk;
//PIN: 89 = reset_n;

//PIN: 40 = duplex_in[3];
//PIN: 37 = duplex_in[2];
//PIN: 35 = duplex_in[1];
//PIN: 33 = duplex_in[0];

//PIN: 41 = z80_m1_n;
//PIN: 42 = z80_iei;
//PIN: 36 = z80_ieo;
//PIN: 96 = z80_int_n;
//PIN: 97 = z80_wait_n;

//PIN: 21 = z80_addr[15];
//PIN: 20 = z80_addr[14];
//PIN: 19 = z80_addr[13];
//PIN: 17 = z80_addr[12];
//PIN: 16 = z80_addr[11];
//PIN: 14 = z80_addr[10];
//PIN: 13 = z80_addr[9];
//PIN: 12 = z80_addr[8];
//PIN: 10 = z80_addr[7];
//PIN: 9  = z80_addr[6];
//PIN: 8  = z80_addr[5];
//PIN: 7  = z80_addr[4];
//PIN: 6  = z80_addr[3];
//PIN: 5  = z80_addr[2];
//PIN: 2  = z80_addr[1];
//PIN: 1  = z80_addr[0];

//PIN: 32 = l_data[7];
//PIN: 31 = l_data[6];
//PIN: 30 = l_data[5];
//PIN: 29 = l_data[4];
//PIN: 28 = l_data[3];
//PIN: 27 = l_data[2];
//PIN: 25 = l_data[1];
//PIN: 24 = l_data[0];

//PIN: 47 = sh_en_n;
//PIN: 48 = sh_rw_n;
//PIN: 46 = sh_inc_n;
//PIN: 45 = sh_stb_n;
//PIN: 49 = sh_done_n;
//PIN: 50 = sh_busy_n;

//PIN: 44 = sh_c_dir;
//PIN: 23 = z80_data_oe_n;
//PIN: 52 = sh_data_oe_n;
//PIN: 22 = l_dir;

//PIN: 85 = l_addr[10];
//PIN: 84 = l_addr[9];
//PIN: 83 = l_addr[8];
//PIN: 81 = l_addr[7];
//PIN: 80 = l_addr[6];
//PIN: 79 = l_addr[5];
//PIN: 78 = l_addr[4];
//PIN: 77 = l_addr[3];
//PIN: 76 = l_addr[2];
//PIN: 75 = l_addr[1];
//PIN: 72 = l_addr[0];

//PIN: 56 = atl_addr[3];
//PIN: 55 = atl_addr[2];
//PIN: 54 = atl_addr[1];
//PIN: 53 = atl_addr[0];

//PIN: 68 = atl_data[7];
//PIN: 67 = atl_data[6];
//PIN: 65 = atl_data[5];
//PIN: 64 = atl_data[4];
//PIN: 63 = atl_data[3];
//PIN: 61 = atl_data[2];
//PIN: 60 = atl_data[1];
//PIN: 58 = atl_data[0];

//PIN: 69 = atl_we_n;
//PIN: 70 = atl_oe_n;
//PIN: 71 = atl_ce_n;

//PIN: 99 = ram_ce0_n;
//PIN: 92 = ram_ce1_n;
//PIN: 98 = rom_ce_n;
//PIN: 93 = mem_oe_n;
//PIN: 94 = ram_we_n;
`else
// ==========================================
// ATMEL FITTER PIN CONSTRAINTS (Clean Hardware)
// ==========================================
`endif

module zx50_mem_control (
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
    
    output wire wait_n, // Driven by Arbiter
    output wire int_n,  // Driven by DMA (Interrupt Pending)

    // Transceiver & Local Bus
    output wire z80_d_oe_n, // Driven by Arbiter/DMA
    output wire d_dir,      // Driven by Arbiter/DMA
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
    output wire  atl_oe_n,
    output reg  atl_we_n,
    
    // Shadow Bus Arbiter Pins
    inout  wire sh_en_n,      // Changed to inout for multidrop
    inout  wire sh_rw_n,      // Changed to inout for multidrop
    inout  wire sh_busy_n,    // Changed to inout for multidrop
    output wire sh_data_oe_n,
    
    // --- NEW: Shadow Bus DMA Pins ---
    inout  wire sh_inc_n,
    inout  wire sh_stb_n,
    inout  wire sh_done_n,
    output wire sh_c_dir
);

    // --- Internal State ---
    reg [3:0]  card_addr;
    reg        has_boot_rom;
    reg        rom_enabled;
    reg [15:0] page_ownership;

    // --- Hit Detection ---
    // Snoop: IORQ=0, WR=0, Port matches 0x3X
    wire mmu_snoop_wr  = (!b_z80_iorq_n && !b_z80_wr_n && (z80_a[7:4] == 4'h3));
    wire mmu_direct_wr = mmu_snoop_wr && (z80_a[3:0] == card_addr);
    
    // DMA IO Decoding (Port 0x4X)
    wire dma_io_write  = (!b_z80_iorq_n && !b_z80_wr_n && (z80_a[7:0] == (8'h40 | card_addr)));

    // ROM is active if it's Card 0, ROM is enabled, accessing the lower 32K, during a memory cycle
    wire effective_use_rom = (card_addr == 4'h0) && rom_enabled && (z80_a[15] == 1'b0) && !b_z80_mreq_n;

    // RAM is active if it's a memory cycle, we own the logical page (A15-A12), and the ROM isn't overriding it
    wire ram_hit = !b_z80_mreq_n && page_ownership[z80_a[15:12]] && !effective_use_rom;

    // --- DMA Wires & INTACK ---
    wire dma_is_active, dma_is_master, dma_dir_to_bus, dma_int_pending;
    wire [19:0] dma_phys_addr;
    wire dma_local_we_n, dma_local_oe_n;

    wire intack_cycle = !b_z80_m1_n && !b_z80_iorq_n;
    wire responding_to_intack = intack_cycle && dma_int_pending;

    // --- Global Z80 Card Hit ---
    wire active_bus_cycle = !b_z80_mreq_n || !b_z80_iorq_n;
    wire z80_card_hit = ((ram_hit || effective_use_rom || mmu_direct_wr) && active_bus_cycle) || dma_io_write || responding_to_intack;

    // --- Bus Arbiter Instantiation ---
    wire arbiter_z80_data_oe_n, arbiter_l_dir;
    
    zx50_bus_arbiter arbiter (
        .mclk(mclk), 
        .reset_n(reset_n),
        .sh_en_n(sh_en_n), 
        .z80_card_hit(z80_card_hit),
        .z80_wait_n(wait_n), 
        .sh_busy_n(sh_busy_n),
        .z80_rd_n(b_z80_rd_n), 
        .sh_rw_n(sh_rw_n),
        .z80_data_oe_n(arbiter_z80_data_oe_n), 
        .sh_data_oe_n(sh_data_oe_n),
        .l_dir(arbiter_l_dir)
    );

    // 1-stage edge detector for INTACK clear
    reg iorq_sync;
    always @(posedge zclk or negedge reset_n) begin // FIX: Use zclk for Z80 synchronization
        if (!reset_n) iorq_sync <= 1'b1;
        else iorq_sync <= b_z80_iorq_n;
    end
    wire iorq_rising = (!iorq_sync && b_z80_iorq_n);
    wire intack_clear = iorq_rising && dma_int_pending;

    zx50_dma dma (
        .mclk(mclk), .reset_n(reset_n),
        .z80_addr_hi(z80_a[15:8]), .z80_data_in(l_d),
        .z80_iorq_n(b_z80_iorq_n), .dma_io_write(dma_io_write),
        .dma_phys_addr(dma_phys_addr),
        .dma_local_we_n(dma_local_we_n), .dma_local_oe_n(dma_local_oe_n),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), .sh_busy_n(sh_busy_n),
        .dma_active(dma_is_active), .sh_c_dir(sh_c_dir), .dma_dir_to_bus(dma_dir_to_bus),
        .dma_is_master(dma_is_master), .int_pending(dma_int_pending), .intack_clear(intack_clear)
    );

    assign int_n = dma_int_pending ? 1'b0 : 1'bz;

    // --- Dynamic Routing (Cycle Stealing) ---
    // If DMA is active, force Z80 transceiver closed. Otherwise let Arbiter decide.
    assign z80_d_oe_n = dma_is_active ? 1'b1 : arbiter_z80_data_oe_n;
    
    // Force direction outward (Card -> Z80) during INTACK, since RD_n is high.
    assign d_dir = (dma_is_active && dma_dir_to_bus) ? 1'b0 : 
                   (responding_to_intack) ? 1'b0 : 
                   arbiter_l_dir;

    assign l_a = dma_is_active ? dma_phys_addr[10:0] : z80_a[10:0];
    wire active_a11 = dma_is_active ? dma_phys_addr[11] : z80_a[11];

    // Drive ATL Data Bus (Or route DMA Address High bits)
    wire cpld_driving_atl = mmu_direct_wr || (effective_use_rom && !dma_is_active) || dma_is_active;
    
    assign atl_d = cpld_driving_atl ? 
                   (mmu_direct_wr ? l_d : 
                   (effective_use_rom && !dma_is_active ? {3'b000, z80_a[15:11]} : 
                   dma_phys_addr[19:12])) : 8'hZZ;

    // The external ATL SRAM is ONLY allowed to output data when the CPLD is NOT driving the bus.
    // AND we must be doing a standard RAM read (ram_hit)
    assign atl_oe_n = !(ram_hit && !cpld_driving_atl);

    // CPLD generally does not drive local data, UNLESS answering an Interrupt!
    wire [7:0] interrupt_vector = 8'h40 | card_addr;
    assign l_d = responding_to_intack ? interrupt_vector : 8'hZZ;

    // --- Combinatorial Pin Routing ---
    always @(*) begin
        // 1. Safe Defaults (Idle State)
        oe_n       = 1'b1;
        we_n       = 1'b1;
        ram_ce0_n  = 1'b1;
        ram_ce1_n  = 1'b1;
        rom_ce2_n  = 1'b1;
        atl_ce_n   = 1'b1;
        // atl_oe_n   = 1'b1;
        atl_we_n   = 1'b1;
        atl_a      = 4'h0;

        if (dma_is_active) begin
            // ----------------------------------------------------------------
            // DMA CYCLE STEALING OVERRIDE
            // ----------------------------------------------------------------
            atl_ce_n = 1'b1; // Bypass ATL, DMA provides full physical address
            // atl_oe_n = 1'b1;
            
            // Physical DMA should ALWAYS be able to hit the Boot ROM, regardless
            // of whether the Z80 has logically unmapped it (rom_enabled)!
            if (card_addr == 4'h0 && has_boot_rom && dma_phys_addr[19:15] == 5'h00) begin
                rom_ce2_n = 1'b0;
                oe_n = dma_local_oe_n;
                we_n = 1'b1; // ROM is strictly read-only
            end else begin
                // Toggle RAM chips based on DMA's physical address
                if (active_a11 == 1'b0) ram_ce0_n = 1'b0;
                else                    ram_ce1_n = 1'b0;
                
                oe_n = dma_local_oe_n;
                we_n = dma_local_we_n;
            end

        end else if (mmu_direct_wr) begin
            // ----------------------------------------------------------------
            // MMU WRITE ROUTING
            // ----------------------------------------------------------------
            atl_a      = z80_a[11:8];
            atl_ce_n   = 1'b0;
            // atl_oe_n   = 1'b1;
            atl_we_n   = b_z80_wr_n;
            
        end else if (effective_use_rom) begin
            // ----------------------------------------------------------------
            // ROM READ ROUTING (ATL Bypass)
            // ----------------------------------------------------------------
            atl_ce_n  = 1'b1;
            // atl_oe_n  = 1'b1;
            atl_we_n  = 1'b1;
            
            rom_ce2_n = 1'b0;
            oe_n      = b_z80_rd_n;
            we_n      = 1'b1; 
            
        end else if (ram_hit) begin
            // ----------------------------------------------------------------
            // NORMAL RAM ROUTING (Via ATL)
            // ----------------------------------------------------------------
        
            atl_a     = z80_a[15:12];
            atl_ce_n  = 1'b0;
            // atl_oe_n  = 1'b0;
            // Output Enable the ATL SRAM to get the phys page
            atl_we_n  = 1'b1;
            
            // Toggle RAM chips based directly on the A11 bit
            if (z80_a[11] == 1'b0) ram_ce0_n = 1'b0;
            else                   ram_ce1_n = 1'b0;
            
            oe_n = b_z80_rd_n;
            we_n = b_z80_wr_n;
        end
    end

    // --- Synchronous Logic ---
// --- Synchronous Logic ---
    always @(posedge zclk) begin
        if (!reset_n) begin
            card_addr      <= {b_z80_mreq_n, b_z80_iorq_n, b_z80_rd_n, b_z80_wr_n};
            
            // DYNAMIC BOOT INFERENCE: If the DIP switches read ID 0, enable the ROM.
            has_boot_rom   <= ({b_z80_mreq_n, b_z80_iorq_n, b_z80_rd_n, b_z80_wr_n} == 4'h0);
            rom_enabled    <= ({b_z80_mreq_n, b_z80_iorq_n, b_z80_rd_n, b_z80_wr_n} == 4'h0);
            page_ownership <= ({b_z80_mreq_n, b_z80_iorq_n, b_z80_rd_n, b_z80_wr_n} == 4'h0) ? 16'h00FF : 16'h0000;
            
        end else begin
            
            // Distributed MMU Snooping
            if (mmu_snoop_wr) begin
                
                // ROM KILL-SWITCH FIX: If ANY card maps a page into the lower 32K 
                // (Logical Pages 0-7), disable the boot ROM forever!
                if (z80_a[11] == 1'b0) rom_enabled <= 1'b0; 
                
                if (mmu_direct_wr) begin
                    // Claim the page
                    page_ownership[z80_a[11:8]] <= 1'b1;
                end else begin
                    // Another card claimed it! Drop ownership.
                    page_ownership[z80_a[11:8]] <= 1'b0;
                end
            end
            
        end
    end

endmodule