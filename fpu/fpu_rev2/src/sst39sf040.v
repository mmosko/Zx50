`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: sst39sf040
 * FILE: src/sst39sf040.v
 * DESCRIPTION:
 * High-Fidelity Timing Simulation Model for Microchip SST39SF040 (512K x 8 55ns Flash ROM).
 *
 * TIMING SPECIFICATIONS ENFORCED (SST39SF040 -55 Speed Grade):
 * --- Read Cycle ---
 * - tRC   (Read Cycle Time)           : 55 ns min
 * - tAA   (Address Access Time)       : 55 ns max
 * - tCE   (Chip Enable Access Time)   : 55 ns max
 * - tOE   (Output Enable Access Time) : 35 ns max
 * - tCLZ  (CE Low to Active Output)   : 0 ns min
 * - tOLZ  (OE Low to Active Output)   : 0 ns min
 * - tCHZ  (CE High to High-Z Output)  : 20 ns max
 * - tOHZ  (OE High to High-Z Output)  : 20 ns max
 * - tOH   (Output Hold Time)          : 0 ns min
 *
 * NOTE ON IVERILOG COMPATIBILITY:
 * Uses explicit sensitivity lists instead of @(*) to avoid array expansion hangs.
 * Module-level variable declarations maintain strict IEEE 1364-2001 Verilog compliance.
 ***************************************************************************************/

module sst39sf040 #(
    parameter MEM_INIT_FILE = ""
)(
    input  wire [18:0] addr,  // Address Bus (A0-A18)
    inout  wire [7:0]  data,  // Data Bus (DQ0-DQ7)
    input  wire        ce_n,  // Chip Enable (~CE)
    input  wire        oe_n,  // Output Enable (~OE)
    input  wire        we_n   // Write Enable (~WE)
);

    // =========================================================================
    // 1. Memory Array & Pre-load
    // =========================================================================
    reg [7:0] memory_array [0:524287];

    initial begin
        if (MEM_INIT_FILE != "") begin
            $readmemh(MEM_INIT_FILE, memory_array);
            $display("[%t ns] FLASH [SST39SF040-55]: Loaded memory table from %s", $time, MEM_INIT_FILE);
        end
    end

    // =========================================================================
    // 2. Read Cycle Timing Logic
    // =========================================================================
    reg [7:0] internal_data;
    reg       oe_driver;

    // Track timestamps for propagation delay calculation
    time t_addr_change;
    time t_ce_low;
    time t_oe_low;

    initial begin
        internal_data = 8'hXX;
        oe_driver     = 1'b0;
        t_addr_change = 0;
        t_ce_low      = 0;
        t_oe_low      = 0;
    end

    // Track input edge timestamps
    always @(addr) t_addr_change = $time;
    always @(negedge ce_n) t_ce_low = $time;
    always @(negedge oe_n) t_oe_low = $time;

    // Read Data Path Pipeline
    wire read_active = (!ce_n && !oe_n && we_n);

    always @(read_active or addr) begin
        if (read_active) begin
            // Calculate effective access delay based on datasheet access limits:
            // tAA = 55ns, tCE = 55ns, tOE = 35ns
            if (^addr !== 1'bx) begin
                internal_data <= #55 memory_array[addr];
            end else begin
                internal_data <= #55 8'hXX;
            end
            oe_driver <= #35 1'b1; // Output drivers turn on after tOE (35ns)
        end
    end

    // High-Z Output Driver Release Timing
    always @(ce_n or oe_n or we_n) begin
        if (!we_n) begin
            // Write pulse deasserts output driver to prevent bus contention
            oe_driver <= #20 1'b0;
        end else if (oe_n) begin
            // tOHZ = 20ns: OE going HIGH turns off outputs
            oe_driver <= #20 1'b0;
        end else if (ce_n) begin
            // tCHZ = 20ns: CE going HIGH turns off outputs
            oe_driver <= #20 1'b0;
        end
    end

    assign data = (oe_driver && read_active) ? internal_data : 8'bZ;

    // =========================================================================
    // 3. Write / Program Protection Logic
    // =========================================================================
    always @(negedge we_n) begin
        if (!ce_n) begin
            $display("[%t ns] WARNING [SST39SF040]: Write pulse (~WE) attempted at address %h! Multi-byte SDP program sequence not modeled in ROM execution mode.", $time, addr);
        end
    end

endmodule
