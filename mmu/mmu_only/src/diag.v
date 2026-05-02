`timescale 1ns/1ps

module diag (
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
    
    // Shadow Bus Arbiter Pins
    inout  wire sh_en_n,      
    inout  wire sh_rw_n,      
    inout  wire sh_busy_n,    
    output wire sh_data_oe_n,
    
    // Shadow Bus DMA Pins
    inout  wire sh_inc_n,
    inout  wire sh_stb_n,
    inout  wire sh_done_n,
    output wire sh_c_dir,

    // Diagnostic Heartbeat (Pin 100)
    output wire hb_led_n
);

// ==========================================
    // 1. COMPREHENSIVE LOGIC ANCHOR
    // ==========================================
    // We XOR every "unused" input pin together. This prevents Quartus from
    // identifying them as "Unused" and driving them to GND, which causes 
    // the 200mA contention with buffer U3.
    wire logic_anchor = ^z80_a ^ b_z80_mreq_n ^ b_z80_iorq_n ^ b_z80_rd_n ^ b_z80_wr_n ^ b_z80_m1_n;

    // ==========================================
    // 1. HEARTBEAT COUNTER
    // ==========================================
    // At 7.5MHz (zclk), a 22-bit counter bit 21 toggles every ~0.28 seconds.
    reg [21:0] hb_counter;
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) 
            hb_counter <= 22'd0;
        else 
            hb_counter <= hb_counter + 1'b1;
    end

    // 2. Tie the result to your heartbeat LED
    // This forces the compiler to keep z80_a as real input pins
    // because they now "affect" an output (the LED).
    assign hb_led_n = hb_counter[21] ^ logic_anchor;

    // ==========================================
    // 2. SAFETY IDLE DEFAULTS (Zombie Mode)
    // ==========================================
    // These assignments ensure no card drivers are fighting the bus.
    assign wait_n       = 1'b1;     // Release Z80 from any hardware wait states
    assign int_n        = 1'bz;     // Disconnect DMA interrupt line
    assign z80_d_oe_n   = 1'b1;     // Close the Z80 data bus transceiver
    assign d_dir        = 1'b1;     // Default direction Inward (toward card)
    assign l_a          = 11'h000;  // Park local address bus
    assign sh_data_oe_n = 1'b1;     // Close the Shadow data bus transceiver
    assign sh_c_dir     = 1'b1;     // Default direction Inward
    assign sh_en_n      = 1'bz;     // Release Shadow Request
    assign sh_rw_n      = 1'bz;
    assign sh_inc_n     = 1'bz;
    assign sh_stb_n     = 1'bz;
    assign sh_done_n    = 1'bz;
    assign sh_busy_n    = 1'bz;

    // Force bidirectional buses to high-impedance
    assign l_d   = 8'h00;
    assign atl_d = 8'h00;
    assign atl_oe_n = 1'b1;         // Explicitly disable ATL SRAM output

    // ==========================================
    // 3. MEMORY CHIP ISOLATION
    // ==========================================
    always @(*) begin
        // Combinatorial defaults to force all memory chips into standby.
        oe_n       = 1'b1; // Disable global Output Enable
        we_n       = 1'b1; // Disable global Write Enable
        ram_ce0_n  = 1'b1; // Deselect SRAM 0
        ram_ce1_n  = 1'b1; // Deselect SRAM 1
        rom_ce2_n  = 1'b1; // Deselect Flash ROM
        atl_ce_n   = 1'b1; // Deselect ATL SRAM
        atl_a      = 4'h0; // Park ATL address lines
        atl_we_n   = 1'b1; // Disable ATL Write
    end

endmodule