`timescale 1ns/1ps

module zx50_mem_control (
    input  wire mclk,
    input  wire zclk,
    input  wire reset_n,
    input  wire boot_en_n,

    // Z80 Backplane
    input  wire [15:0] z80_a,
    input  wire b_z80_mreq_n,
    input  wire b_z80_iorq_n,
    input  wire b_z80_rd_n,
    input  wire b_z80_wr_n,
    input  wire b_z80_m1_n,
    
    output reg  wait_n,
    output reg  int_n,

    // Transceiver & Local Bus
    output reg  z80_d_oe_n,
    output reg  d_dir,
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
    output reg  atl_oe_n,
    output reg  atl_we_n
);

    // --- Internal State ---
    reg [3:0]  card_addr;
    reg        has_boot_rom;
    reg        rom_enabled;
    reg [15:0] page_ownership;

    // --- Continuous Assignments ---
    assign l_a = z80_a[10:0];
    
    // --- Hit Detection ---
    // Snoop: IORQ=0, WR=0, Port matches 0x3X
    wire mmu_snoop_wr  = (!b_z80_iorq_n && !b_z80_wr_n && (z80_a[7:4] == 4'h3));
    wire mmu_direct_wr = mmu_snoop_wr && (z80_a[3:0] == card_addr);

    // ROM is active if it's Card 0, ROM is enabled, accessing the lower 32K, during a memory cycle
    wire effective_use_rom = (card_addr == 4'h0) && rom_enabled && (z80_a[15] == 1'b0) && !b_z80_mreq_n;
    
    // RAM is active if it's a memory cycle, we own the logical page (A15-A12), and the ROM isn't overriding it
    wire ram_hit = !b_z80_mreq_n && page_ownership[z80_a[15:12]] && !effective_use_rom;

    // --- Drive ATL Data Bus ---
    // 1. If MMU Write -> Bridge Local Data into the ATL SRAM
    // 2. If ROM Read  -> CPLD drives the linear physical address (restoring the missing A11)
    // 3. Otherwise    -> Float the bus so the ATL SRAM can drive it during RAM reads
    assign atl_d = mmu_direct_wr ? l_d : 
                   (effective_use_rom ? {3'b000, z80_a[15:11]} : 8'hZZ);
    
    // CPLD does not drive local data itself
    assign l_d = 8'hZZ;

    // --- Combinatorial Pin Routing ---
    always @(*) begin
        // 1. Safe Defaults (Idle State)
        z80_d_oe_n = 1'b1;
        d_dir      = 1'b0;
        oe_n       = 1'b1;
        we_n       = 1'b1;
        ram_ce0_n  = 1'b1;
        ram_ce1_n  = 1'b1;
        rom_ce2_n  = 1'b1;
        atl_ce_n   = 1'b1;
        atl_oe_n   = 1'b1;
        atl_we_n   = 1'b1;
        atl_a      = 4'h0;

        if (mmu_direct_wr) begin
            // ----------------------------------------------------------------
            // MMU WRITE ROUTING
            // ----------------------------------------------------------------
            z80_d_oe_n = 1'b0;
            d_dir      = 1'b1;           // 1 = Z80 -> Card
            atl_a      = z80_a[11:8];
            atl_ce_n   = 1'b0;
            atl_oe_n   = 1'b1;
            atl_we_n   = b_z80_wr_n;
            
        end else if (effective_use_rom) begin
            // ----------------------------------------------------------------
            // ROM READ ROUTING (ATL Bypass)
            // ----------------------------------------------------------------
            atl_ce_n  = 1'b1;
            atl_oe_n  = 1'b1;
            atl_we_n  = 1'b1;
            
            rom_ce2_n = 1'b0;
            oe_n      = b_z80_rd_n;
            we_n      = 1'b1; 
            
            if (!b_z80_rd_n) begin
                z80_d_oe_n = 1'b0;
                d_dir      = 1'b0;       // 0 = Card -> Z80
            end
            
        end else if (ram_hit) begin
            // ----------------------------------------------------------------
            // NORMAL RAM ROUTING (Via ATL)
            // ----------------------------------------------------------------
            atl_a     = z80_a[15:12];
            atl_ce_n  = 1'b0;
            atl_oe_n  = 1'b0;            // Output Enable the ATL SRAM to get the phys page
            atl_we_n  = 1'b1;
            
            // Toggle RAM chips based directly on the A11 bit
            if (z80_a[11] == 1'b0) ram_ce0_n = 1'b0;
            else                   ram_ce1_n = 1'b0;
            
            oe_n = b_z80_rd_n;
            we_n = b_z80_wr_n;
            
            if (!b_z80_rd_n) begin
                z80_d_oe_n = 1'b0;
                d_dir      = 1'b0;       // 0 = Card -> Z80
            end else if (!b_z80_wr_n) begin
                z80_d_oe_n = 1'b0;
                d_dir      = 1'b1;       // 1 = Z80 -> Card
            end
        end
    end

    // --- Synchronous Logic ---
    always @(posedge mclk) begin
        if (!reset_n) begin
            wait_n <= 1'b1; 
            int_n  <= 1'b1;
            card_addr      <= {b_z80_mreq_n, b_z80_iorq_n, b_z80_rd_n, b_z80_wr_n};
            has_boot_rom   <= ~boot_en_n;
            rom_enabled    <= ~boot_en_n;
            page_ownership <= (~boot_en_n) ? 16'h00FF : 16'h0000;
            
        end else begin
            
            // Distributed MMU Snooping
            if (mmu_snoop_wr) begin
                if (mmu_direct_wr) begin
                    // Claim the page
                    page_ownership[z80_a[11:8]] <= 1'b1;
                    
                    // ROM KILL-SWITCH
                    // If the CPU maps a page into the lower 32K (Logical Pages 0-7), 
                    // disable the boot ROM forever so the new RAM page can show through!
                    if (z80_a[11] == 1'b0) rom_enabled <= 1'b0; 
                    
                end else begin
                    // Another card claimed it! Drop ownership.
                    page_ownership[z80_a[11:8]] <= 1'b0;
                end
            end
            
        end
    end

endmodule