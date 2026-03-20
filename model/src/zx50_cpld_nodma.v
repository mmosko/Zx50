`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_cpld_nodma
 * DESCRIPTION:
 * [REVISION: "No-DMA" Fallback Variant. The DMA and Arbiter modules have been completely 
 * removed to guarantee synthesis into the ATF1508AS 128-macrocell footprint. Shadow bus 
 * pins are physically present on the PCB but left disconnected/high-Z internally.]
 * * The top-level CPLD logic that integrates the MMU.
 * It is responsible for extremely strict multiplexing of the physical IC pins, 
 * ensuring that the Z80, the SRAM chips, and the Backplane transceivers never 
 * contend with each other[cite: 650]. 
 ***************************************************************************************/

module zx50_cpld_nodma (
    (* LOC="P87" *) input  wire mclk,
    (* LOC="P89" *) input  wire reset_n,
    
    // --- Duplex/Control Bus (MSB to LSB: IORQ, MREQ, WR, RD) ---
    (* LOC="P40,P37,P35,P33" *) input  wire [3:0] duplex_in, 
    
    // --- Z80 Backplane ---
    (* LOC="P41" *) input  wire z80_m1_n,       
    (* LOC="P42" *) input  wire z80_iei,        
    (* LOC="P36" *) output wire z80_ieo,        
    
    // [REVISION: Kept to maintain PCB pinout, but driven inactive]
    (* LOC="P96" *) inout wire z80_int_n,    
    (* LOC="P97" *) inout wire z80_wait_n,   

    // Z80 Address Bus (A15 down to A0)
    (* LOC="P21,P20,P19,P17,P16,P14,P13,P12,P10,P9,P8,P7,P6,P5,P2,P1" *) 
    input  wire [15:0] z80_addr, 
    
    // --- Local Shared Bus (D7 down to D0) ---
    (* LOC="P32,P31,P30,P29,P28,P27,P25,P24" *) 
    inout  wire [7:0] l_data, 
    
    // [REVISION: Shadow Bus inouts and Transceiver controls (sh_en_n, sh_c_dir, etc.) 
    // have been entirely removed from the port list to free up routing resources.]
    
    // --- Transceiver Controls ---
    (* LOC="P23" *) output wire z80_data_oe_n, 
    (* LOC="P22" *) output wire l_dir,
    
    // --- Local Memory & LUT Routing ---
    // Local Address Bus (A10 down to A0)
    (* LOC="P85,P84,P83,P81,P80,P79,P78,P77,P76,P75,P72" *) 
    output wire [10:0] l_addr,  
    
    // ATL Address Bus (A3 down to A0)
    // [REVISION: Reduced to 4 bits to save space and free P57]
    (* LOC="P56,P55,P54,P53" *) 
    output wire [3:0]  atl_addr, 
    
    // ATL Data Bus (D7 down to D0)
    (* LOC="P68,P67,P65,P64,P63,P61,P60,P58" *) 
    inout  wire [7:0]  atl_data, 
    
    (* LOC="P69" *) output wire atl_we_n, 
    (* LOC="P70" *) output wire atl_oe_n, 
    (* LOC="P71" *) output wire atl_ce_n,
    (* LOC="P90" *) output wire ram_ce0_n, 
    (* LOC="P92" *) output wire ram_ce1_n,
    (* LOC="P93" *) output wire ram_oe_n,
    (* LOC="P94" *) output wire ram_we_n           
);

    // ==========================================
    // ATMEL FITTER PIN CONSTRAINTS
    // The run_fitter.sh script greps these lines to build the .pin file.
    // [REVISION: Maintained all physical PIN constraints for the Atmel Fitter] [cite: 652]
    // ==========================================
    //PIN: 87 = mclk;
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
    //PIN: 23 = z80_data_oe_n;
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

    // ==========================================
    // 1. DUPLEX CONFIGURATION LATCH
    // ==========================================
    reg [3:0] latched_id;
    wire z80_rd_n   = duplex_in[0]; 
    wire z80_wr_n   = duplex_in[1]; 
    wire z80_mreq_n = duplex_in[2]; 
    wire z80_iorq_n = duplex_in[3];


    // === tie off unused pins
    // ==========================================
    // DEFEATING YOSYS OPTIMIZATION FOR ATMEL EDIF
    // ==========================================
    // The Atmel Fitter crashes if any bidirectional buffer has a 'z' or 'x'
    // on its internal data input port.
    // We must drive the data ports with real external signals to keep them alive.
    // To ensure the physical pins remain High-Z inputs, we drive the Enable (OE) 
    // port with a mathematically impossible condition that Yosys cannot optimize away.
    // Condition: (z80_rd_n == 0) AND (z80_wr_n == 0). The Z80 can never read and write simultaneously.

    wire impossible_enable = !z80_rd_n && !z80_wr_n;

    // z80_iei is an input, we pass it down the chain.
    assign z80_ieo = z80_iei; 


    // Drive unused lines with real external signals (that aren't global clocks), 
    // but keep OE disabled via the impossible condition.
    assign z80_int_n  = impossible_enable ? z80_addr[0] : 1'bz;
    assign z80_wait_n = impossible_enable ? z80_addr[1] : 1'bz;
    
    // Drive l_data with z80_addr to prevent EDIF 'x' crash
    assign l_data = impossible_enable ? z80_addr[7:0] : 8'hzz;
    
    // atl_data is written ONLY when atl_we_n is low.
    // When reading, we provide a dummy external signal instead of 'z'
    //assign atl_data = (!atl_we_n) ? l_data : (impossible_enable ? z80_addr[15:8] : 8'hzz);

    // =====
 
    // Synchronously latch the Card ID while the system is in reset.
    // Once reset_n goes high (normal operation), latched_id locks and holds its value. [cite: 676, 677]
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
    wire mmu_card_hit;
    
    wire active_bus_cycle = !z80_mreq_n || !z80_iorq_n;
    
    // [REVISION: dma_card_hit removed. internal_z80_card_hit solely relies on the MMU.]
    wire internal_z80_card_hit = mmu_card_hit && active_bus_cycle;

    // [REVISION: Without an arbiter, Z80 has permanent grant]
    wire z80_grant = 1'b1;
    wire memory_cycle = !z80_mreq_n;

    // ==========================================
    // 3. CORE SUB-MODULE INSTANTIATIONS
    // ==========================================
    
    // [REVISION: Arbiter and DMA instantiations completely removed]

    zx50_mmu_sram mmu_unit (
        .mclk(mclk), .reset_n(reset_n), 
        .card_id_sw(latched_id), 
        .z80_addr(z80_addr), .l_addr_hi(z80_addr[15:12]), 
        .l_data(l_data), .z80_iorq_n(z80_iorq_n), .z80_wr_n(z80_wr_n), .z80_mreq_n(z80_mreq_n), 
        .atl_addr(atl_addr), .atl_we_n(atl_we_n), .atl_oe_n(atl_oe_n),
        .active(internal_active),
        .cpu_updating(mmu_cpu_updating),
        .is_initializing(mmu_is_initializing),
        .init_ptr(mmu_init_ptr), 
        .z80_card_hit(mmu_card_hit), 
        .is_busy(mmu_busy) 
    );

    // ==========================================
    // 4. LOCAL MEMORY & LUT TAKEOVER MULTIPLEXING
    // ==========================================
    
    // [REVISION: Removed DMA multiplexing. Lines strictly follow Z80]
    assign l_addr = z80_addr[10:0];
    assign atl_ce_n = !(internal_z80_card_hit || mmu_busy);
    
    // ATL Data is only driven by CPLD when writing to the SRAM LUT
    assign atl_data = (!atl_we_n) ? l_data : 8'hzz;
    
    wire safe_to_access_ram = (internal_z80_card_hit && atl_we_n && memory_cycle);
    
    // [REVISION: In NoDMA mode, we assume a flat 1MB array. We use atl_data[7] for bank selection.]
    wire bank_select = atl_data[7]; 

    assign ram_ce0_n = (safe_to_access_ram && bank_select == 1'b0) ? 1'b0 : 1'b1;
    assign ram_ce1_n = (safe_to_access_ram && bank_select == 1'b1) ? 1'b0 : 1'b1;

    assign ram_oe_n = memory_cycle ? z80_rd_n : 1'b1;
    assign ram_we_n = memory_cycle ? z80_wr_n : 1'b1;

    // ==========================================
    // 5. TRANSCEIVER CONTROL
    // ==========================================
    
    // [REVISION: Cycle Stealing intercept logic removed. Transceivers controlled natively by hit logic.]
    assign z80_data_oe_n = !internal_z80_card_hit;
    assign l_dir         = z80_rd_n; // 1 = Master writing to Card, 0 = Card outputting to Master

endmodule
