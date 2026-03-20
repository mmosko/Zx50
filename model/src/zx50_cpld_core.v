`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_cpld_core
 * DESCRIPTION:
 * The top-level CPLD logic that integrates the MMU, Z80 Arbiter, and DMA.
 * It is responsible for extremely strict multiplexing of the physical IC pins, 
 * ensuring that the Z80, the SRAM chips, and the Backplane transceivers never 
 * contend with each other. 
 * * NOTE: The Shadow Bus and Z80 backplane share a single data transceiver direction pin, 
 * controlled by l_dir.
 ***************************************************************************************/

// ==========================================
// ATMEL FITTER PIN CONSTRAINTS
// The run_fitter.sh script greps these lines to build the .pin file.
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
//PIN: 90 = ram_ce0_n;
//PIN: 92 = ram_ce1_n;
//PIN: 93 = ram_oe_n;
//PIN: 94 = ram_we_n;

module zx50_cpld_core (
    input  wire mclk,
    input  wire reset_n,
    
    // --- Duplex/Control Bus (MSB to LSB: IORQ, MREQ, WR, RD) ---
    input  wire [3:0] duplex_in, 
    
    // --- Z80 Backplane ---
    input  wire z80_m1_n,       
    input  wire z80_iei,        
    output wire z80_ieo,        
    
    inout wire z80_int_n,    // Technicaly tristate, we want open drain
    inout wire z80_wait_n,   //Technicaly tristate, we want open drain

    // Z80 Address Bus (A15 down to A0)
    
    input  wire [15:0] z80_addr, 
    
    // --- Local Shared Bus (D7 down to D0) ---
    
    inout  wire [7:0] l_data, 
    
    // --- Shadow Bus Controls (Bidirectional) ---
    inout  wire sh_en_n, 
    inout  wire sh_rw_n, 
    inout  wire sh_inc_n, 
    inout  wire sh_stb_n, 
    inout  wire sh_done_n, 
    inout  wire sh_busy_n, 
    
    // --- Transceiver Controls ---
    output wire sh_c_dir,         
    output wire z80_data_oe_n, 
    output wire sh_data_oe_n,
    output wire l_dir,
    
    // --- Local Memory & LUT Routing ---
    // Local Address Bus (A10 down to A0)
    
    output wire [10:0] l_addr,  
    
    // ATL Address Bus (A4 down to A0)
    // Reduced to 4 bits to save space and free P57
    
    output wire [3:0]  atl_addr, 
    
    // ATL Data Bus (D7 down to D0)
    
    inout  wire [7:0]  atl_data, 
    
    output wire atl_we_n, 
    output wire atl_oe_n, 
    output wire atl_ce_n,
    output wire ram_ce0_n, 
    output wire ram_ce1_n,
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

    // Synchronously latch the Card ID while the system is in reset.
    // Once reset_n goes high (normal operation), latched_id locks and holds its value.
    always @(posedge mclk) begin
        if (!reset_n) begin
            latched_id <= duplex_in; 
        end
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
    wire dma_card_hit = (!z80_iorq_n && (z80_addr[7:0] == (8'h40 | latched_id)));
    wire internal_z80_card_hit = qualified_mmu_hit | dma_card_hit;

    wire arbiter_sh_busy_n;
    wire arbiter_l_dir; 
    wire arbiter_z80_data_oe_n;
    wire arbiter_sh_data_oe_n; 
    wire arbiter_wait_n;
    
    wire z80_grant = !z80_data_oe_n;
    
    wire [19:0] dma_phys_addr;
    wire dma_local_we_n, dma_local_oe_n, dma_dir_to_bus;
    wire dma_is_active, dma_int_pending, dma_is_master;

    wire memory_cycle = !z80_mreq_n;

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

    zx50_mmu_sram mmu_unit (
        .mclk(mclk), .reset_n(reset_n), 
        // card 0 is considered the boot card with eeprom enabled
        // .boot_en_n(latched_id != 4'h0), 
        .card_id_sw(latched_id), 
        .z80_addr(z80_addr), .l_addr_hi(z80_addr[15:12]), 
        .l_data(l_data), .z80_iorq_n(safe_z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_mreq_n(z80_mreq_n), 
        .atl_addr(atl_addr), .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n),
        .active(internal_active),
        .cpu_updating(mmu_cpu_updating),
        .is_initializing(mmu_is_initializing),
        .init_ptr(mmu_init_ptr), 
        .z80_card_hit(mmu_card_hit), 
        .is_busy(mmu_busy) 
    );

    zx50_dma dma_unit (
        .mclk(mclk), .reset_n(reset_n), .card_id(latched_id),
        .z80_addr(z80_addr), .z80_data_in(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n),
        .dma_phys_addr(dma_phys_addr), .dma_data_out(), .dma_data_in(l_data), 
        .dma_local_we_n(dma_local_we_n), .dma_local_oe_n(dma_local_oe_n),
        .sh_en_n(sh_en_n), .sh_rw_n(sh_rw_n), .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n), .sh_done_n(sh_done_n), 
        .sh_busy_n(sh_busy_n), 
        .dma_active(dma_is_active), .sh_c_dir(sh_c_dir), .dma_dir_to_bus(dma_dir_to_bus),
        .dma_is_master(dma_is_master), .int_pending(dma_int_pending), .intack_clear(intack_clear)
    );

    // ==========================================
    // 5. LOCAL MEMORY & LUT TAKEOVER MULTIPLEXING
    // ==========================================

    // OPTIMIZATION 1: Do not force l_addr to 0. Mux directly between the two masters.
    // This instantly frees 11 macrocells and drops massive routing overhead!
    assign l_addr = dma_is_active ? dma_phys_addr[10:0] : z80_addr[10:0];
    
    assign atl_ce_n = dma_is_active ? 1'b1 : !(internal_z80_card_hit || mmu_busy);

    // OPTIMIZATION 2: Break the 'atl_we_n' routing feedback loop.
    // Use internal flags to determine when the CPLD must drive the LUT data bus.
    wire atl_data_oe = dma_is_active || mmu_is_initializing || mmu_cpu_updating;
    
    // Split the tri-state logic so Yosys can map it to a physical Atmel bibuf
    wire [7:0] atl_data_out = dma_is_active ? {3'b000, dma_phys_addr[19:15]} : l_data;
    assign atl_data = atl_data_oe ? atl_data_out : 8'hzz;

    // Due to hardware mis-wire, we use z80_addr[11] as the chip select, not atl_data[7]
    // STRIPED RAM FIX: Use A11 to interleave CE0 and CE1 in 2KB blocks.
    // This frees atl_data[7] to act as the 8th bit of the physical page address!
    wire bank_select = dma_is_active ? dma_phys_addr[19] : z80_addr[11];
    
    // OPTIMIZATION 3: Break the second routing loop to the RAM Chip Enables
    wire safe_to_access_ram = dma_is_active || (internal_z80_card_hit && !mmu_cpu_updating && memory_cycle);

    assign ram_ce0_n = (safe_to_access_ram && bank_select == 1'b0) ? 1'b0 : 1'b1;
    assign ram_ce1_n = (safe_to_access_ram && bank_select == 1'b1) ? 1'b0 : 1'b1;

    // OPTIMIZATION 4: Simplify the OE/WE muxing
    assign ram_oe_n = dma_is_active ? dma_local_oe_n : (z80_grant ? z80_rd_n : 1'b1);
    assign ram_we_n = dma_is_active ? dma_local_we_n : (z80_grant ? z80_wr_n : 1'b1);

    wire [7:0] interrupt_vector = 8'h40 | latched_id;
    assign l_data = responding_to_intack ? interrupt_vector : 8'hzz;

    // ==========================================
    // 6. CYCLE STEALING: INTERCEPT & OVERRIDE LOGIC
    // ==========================================
    assign z80_wait_n = ((arbiter_hit && dma_is_active) || arbiter_wait_n == 1'b0) ? 1'b0 : 1'bz;
    
    // Transceiver Multiplexing
    assign sh_data_oe_n  = dma_is_active ? 1'b0 : arbiter_sh_data_oe_n;
    assign z80_data_oe_n = dma_is_active ? 1'b1 : arbiter_z80_data_oe_n;
    
    assign sh_busy_n = (arbiter_hit && dma_is_active) ? 1'b0 : 1'bz;
    assign l_dir = dma_is_active ? dma_dir_to_bus : arbiter_l_dir;

endmodule
