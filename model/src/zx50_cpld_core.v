`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_cpld_core (Rev 1.0 - Clean Hardware)
 * =====================================================================================
 * DESCRIPTION:
 * The top-level CPLD routing matrix. It securely integrates the MMU, Z80 Arbiter, 
 * and DMA modules, enforcing strict multiplexing of the physical IC pins so that 
 * the Z80, the shared memory chips, and the backplane transceivers never collide.
 *
 * MEMORY ARCHITECTURE (CLEAN 4K PAGING):
 * - Local Address (`l_addr[11:0]`): Provides the 4KB physical page offset.
 * - Translation Data (`atl_data[7:0]`): Provides physical address bits [19:12].
 * - Bank Select: `atl_data[7]` is used as the chip select to toggle between the 
 * two 512KB SRAM ICs (`ram_ce0_n` and `ram_ce1_n`).
 *
 * ROM BYPASS LOGIC:
 * To boot, Card 0 must bypass the ATL SRAM and force the local address bus to target 
 * the Boot ROM. If `effective_use_rom` is triggered, the CPLD disables the ATL SRAM's 
 * output, takes over the `atl_data` pins to drive zeroes, forces the RAM chip selects 
 * High, and pulls `rom_ce_n` Low.
 ***************************************************************************************/

// ==========================================
// ATMEL FITTER PIN CONSTRAINTS
// ==========================================
//PIN: 87 = mclk;
//PIN: 89 = reset_n;

//PIN: 40 = duplex_in[3];
//PIN: 37 = duplex_in[2];
//PIN: 35 = duplex_in[1];
//PIN: 33 = duplex_in[0];

//PIN: 41 = z80_m1_n;
//PIN: 42 = z80_iei;
//PIN: 96 = z80_int_n;
//PIN: 97 = z80_wait_n;

//PIN: 21 = z80_addr[15];
// ... [Remaining Z80 Address pins omitted for brevity] ...
//PIN: 1  = z80_addr[0];

//PIN: 32 = l_data[7];
// ... [Remaining Local Data pins omitted for brevity] ...
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

// NOTE: l_addr[11] requires a new physical pin assignment!
//PIN: 85 = l_addr[10];
// ... [Remaining Local Address pins omitted for brevity] ...
//PIN: 72 = l_addr[0];

//PIN: 56 = atl_addr[3];
// ...
//PIN: 53 = atl_addr[0];

//PIN: 68 = atl_data[7];
// ...
//PIN: 58 = atl_data[0];

//PIN: 69 = atl_we_n;
//PIN: 70 = atl_oe_n;
//PIN: 71 = atl_ce_n;
//PIN: 90 = ram_ce0_n;
//PIN: 92 = ram_ce1_n;
//PIN: 91 = rom_ce_n;
//PIN: 93 = ram_oe_n;
//PIN: 94 = ram_we_n;

module zx50_cpld_core (
    input  wire mclk,
    input  wire reset_n,
    
    input  wire [3:0] duplex_in, 
    input  wire z80_m1_n,       
    input  wire z80_iei,        
    output wire z80_ieo,        
    inout wire z80_int_n,    
    inout wire z80_wait_n,   
    input  wire [15:0] z80_addr, 

    inout  wire [7:0] l_data, 
    
    inout  wire sh_en_n, 
    inout  wire sh_rw_n, 
    inout  wire sh_inc_n, 
    inout  wire sh_stb_n, 
    inout  wire sh_done_n, 
    inout  wire sh_busy_n, 
    
    output wire sh_c_dir,         
    output wire z80_data_oe_n, 
    output wire sh_data_oe_n,
    output wire l_dir,
 
    output wire [11:0] l_addr,  // EXPANDED TO FULL 12 BITS (4K)
    output wire [3:0]  atl_addr, 
    inout  wire [7:0]  atl_data, 
    
    output wire atl_we_n, 
    output wire atl_oe_n, 
    output wire atl_ce_n,
    output wire ram_ce0_n, 
    output wire ram_ce1_n,
    output wire rom_ce_n,      
    output wire ram_oe_n,
    output wire ram_we_n        
);

    // ==========================================
    // 1. DUPLEX CONFIGURATION LATCH
    // ==========================================
    reg [3:0] latched_id;
    wire z80_rd_n   = duplex_in[0]; 
    wire z80_wr_n   = duplex_in[1]; 
    wire z80_mreq_n = duplex_in[2]; 
    wire z80_iorq_n = duplex_in[3];

    // Combinatorial bypass so sub-modules instantly see the DIP switches during reset
    wire [3:0] current_id = (!reset_n) ? duplex_in : latched_id;

    always @(posedge mclk) begin
        if (!reset_n) latched_id <= duplex_in;
    end

    // ==========================================
    // 2. INTERNAL SUBSYSTEM WIRES & HIT LOGIC
    // ==========================================
    wire internal_active, mmu_busy;
    wire mmu_cpu_updating, mmu_is_initializing;
    wire [3:0] mmu_init_ptr;
    
    wire active_bus_cycle = !z80_mreq_n || !z80_iorq_n;
    wire mmu_card_hit;
    wire qualified_mmu_hit = mmu_card_hit && active_bus_cycle;
    wire dma_card_hit = (!z80_iorq_n && (z80_addr[7:0] == (8'h40 | current_id)));
    wire internal_z80_card_hit = qualified_mmu_hit | dma_card_hit;

    wire arbiter_sh_busy_n;
    wire arbiter_l_dir;
    wire arbiter_z80_data_oe_n;
    wire arbiter_sh_data_oe_n; 
    wire arbiter_wait_n;
    
    wire [19:0] dma_phys_addr;
    wire dma_local_we_n, dma_local_oe_n, dma_dir_to_bus;
    wire dma_is_active, dma_int_pending, dma_is_master;

    wire memory_cycle = !z80_mreq_n;

    // --- INTERNAL TRANSCEIVER WIRES ---
    wire internal_z80_data_oe_n = dma_is_active ? 1'b1 : arbiter_z80_data_oe_n;
    wire internal_l_dir         = arbiter_l_dir; // Z80 Data Transceiver strictly follows the Z80 Arbiter
    wire z80_grant = !internal_z80_data_oe_n;

    // ==========================================
    // 3. INTERRUPT & INTACK LOGIC
    // ==========================================
    wire intack_cycle = !z80_m1_n && !z80_iorq_n;
    wire responding_to_intack = intack_cycle && z80_iei && dma_int_pending;

    reg [1:0] iorq_sync;
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) iorq_sync <= 2'b11;
        else iorq_sync <= {iorq_sync[0], z80_iorq_n};
    end
    
    wire iorq_rising = (iorq_sync == 2'b01);
    wire intack_clear = iorq_rising && z80_iei && dma_int_pending;

    assign z80_int_n = dma_int_pending ? 1'b0 : 1'bz;
    assign z80_ieo = z80_iei && !dma_int_pending; 

    // ==========================================
    // 4. CORE SUB-MODULE INSTANTIATIONS
    // ==========================================
    wire arbiter_hit  = internal_z80_card_hit || responding_to_intack;
    wire arbiter_rd_n = responding_to_intack ? 1'b0 : z80_rd_n;
    wire safe_sh_en_n = dma_is_active ? sh_en_n : 1'b1;

    zx50_bus_arbiter arbiter_unit (
        .mclk(mclk), .reset_n(reset_n),
        .sh_en_n(safe_sh_en_n), 
        .z80_card_hit(arbiter_hit), 
        .z80_wait_n(arbiter_wait_n), .sh_busy_n(arbiter_sh_busy_n), 
        .z80_rd_n(arbiter_rd_n), .sh_rw_n(sh_rw_n),
        .z80_data_oe_n(arbiter_z80_data_oe_n), 
        .sh_data_oe_n(arbiter_sh_data_oe_n), 
        .l_dir(arbiter_l_dir)                  
    );

    wire safe_z80_iorq_n = dma_is_active ? 1'b1 : z80_iorq_n;

    wire mmu_atl_oe_n;
    wire mmu_is_rom_enabled;

    zx50_mmu_sram mmu_unit (
        .mclk(mclk), .reset_n(reset_n), 
        .boot_en_n(current_id != 4'h0), 
        .card_id_sw(current_id), 
        .z80_addr(z80_addr),  
        .l_data(l_data), .z80_iorq_n(safe_z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_mreq_n(z80_mreq_n), 
        .atl_addr(atl_addr), .atl_we_n(atl_we_n), 
        .atl_oe_n(mmu_atl_oe_n), 
        .active(internal_active),
        .cpu_updating(mmu_cpu_updating),
        .is_initializing(mmu_is_initializing),
        .init_ptr(mmu_init_ptr), 
        .z80_card_hit(mmu_card_hit), 
        .is_busy(mmu_busy),
        .is_rom_enabled(mmu_is_rom_enabled)
    );

    wire dma_internal_sh_c_dir; 

    zx50_dma dma_unit (
        .mclk(mclk), .reset_n(reset_n), .card_id(current_id),
        .z80_addr(z80_addr), .z80_data_in(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n),
        .dma_phys_addr(dma_phys_addr), .dma_data_out(), .dma_data_in(l_data), 
        .dma_local_we_n(dma_local_we_n), .dma_local_oe_n(dma_local_oe_n),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), 
        .sh_busy_n(sh_busy_n), 
        .dma_active(dma_is_active), .sh_c_dir(dma_internal_sh_c_dir), .dma_dir_to_bus(dma_dir_to_bus),
        .dma_is_master(dma_is_master), .int_pending(dma_int_pending), .intack_clear(intack_clear)
    );

    // ==========================================
    // 5. LOCAL MEMORY & LUT TAKEOVER MULTIPLEXING
    // ==========================================

    // CLEAN HARDWARE: The local offset is a pure 12-bit (4KB) slice
    assign l_addr = dma_is_active ? dma_phys_addr[11:0] : z80_addr[11:0];
    
    // ATL Chip Select
    assign atl_ce_n = dma_is_active ? 1'b1 : !(internal_z80_card_hit || mmu_busy);

    // --- UNIVERSAL ROM BYPASS LOGIC ---
    wire dma_hitting_rom = (dma_phys_addr[19:15] == 5'b00000);
    wire z80_hitting_rom = (z80_addr[15] == 1'b0);
    wire target_is_rom_space = dma_is_active ? dma_hitting_rom : z80_hitting_rom;
    
    // Trigger ROM logic if Card 0, Kill-Switch hasn't been flipped, and accessing < 32K
    wire effective_use_rom = (current_id == 4'h0) && mmu_is_rom_enabled && target_is_rom_space;

    // Force SRAM Output Enable High (Off) if DMA is driving or the ROM bypass is active
    assign atl_oe_n = (dma_is_active || effective_use_rom) ? 1'b1 : mmu_atl_oe_n;

    // --- TRI-STATE LOGIC (ATL DATA BUS) ---
    wire atl_drive_en = dma_is_active | mmu_is_initializing | mmu_cpu_updating | effective_use_rom;

    reg [7:0] atl_data_out;
    always @(*) begin
        // CLEAN HARDWARE: During DMA, route the pure 8-bit upper physical address
        if (dma_is_active)            atl_data_out = dma_phys_addr[19:12]; 
        else if (mmu_is_initializing) atl_data_out = {4'h0, mmu_init_ptr};
        else if (mmu_cpu_updating)    atl_data_out = l_data;
        // ROM Bypass: Force upper physical bits to 0x00
        else                          atl_data_out = {4'b0000, z80_addr[15:12]}; 
    end

    assign atl_data = atl_drive_en ? atl_data_out : 8'hzz;

    // --- CHIP SELECT LOGIC ---
    // CLEAN HARDWARE: Bank select toggles between RAM CE0 and CE1 based strictly on Physical A[19]
    wire bank_select = atl_data[7]; 
    wire safe_to_access_ram = dma_is_active || (internal_z80_card_hit && !mmu_cpu_updating && memory_cycle);
    wire active_write = dma_is_active ? !dma_local_we_n : (z80_grant && !z80_wr_n);

    assign ram_ce0_n = (safe_to_access_ram && !effective_use_rom && bank_select == 1'b0) ? 1'b0 : 1'b1;
    assign ram_ce1_n = (safe_to_access_ram && !effective_use_rom && bank_select == 1'b1) ? 1'b0 : 1'b1;
    assign rom_ce_n  = (safe_to_access_ram && effective_use_rom && !active_write) ? 1'b0 : 1'b1;

    assign ram_oe_n = dma_is_active ? dma_local_oe_n : (z80_grant ? z80_rd_n : 1'b1);
    assign ram_we_n = effective_use_rom ? 1'b1 : (dma_is_active ? dma_local_we_n : (z80_grant ? z80_wr_n : 1'b1));

    wire [7:0] interrupt_vector = 8'h40 | current_id;
    assign l_data = responding_to_intack ? interrupt_vector : 8'hzz;

    // ==========================================
    // 6. CYCLE STEALING: INTERCEPT & OVERRIDE LOGIC
    // ==========================================
    assign z80_wait_n = ((arbiter_hit && dma_is_active) || arbiter_wait_n == 1'b0) ? 1'b0 : 1'bz;
    
    // Guarantee no internal DMA polarity bugs can cause bus collisions
    assign sh_c_dir = dma_is_active ? (!dma_local_oe_n) : dma_internal_sh_c_dir;

    assign sh_data_oe_n  = dma_is_active ? 1'b0 : arbiter_sh_data_oe_n;
    assign z80_data_oe_n = internal_z80_data_oe_n;
    
    assign sh_busy_n = (arbiter_hit && dma_is_active) ? 1'b0 : 1'bz;
    assign l_dir = internal_l_dir;

endmodule