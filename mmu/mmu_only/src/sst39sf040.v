`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: sst39sf040
 * DESCRIPTION:
 * Simulation model for the SST39SF040 512KB Flash ROM.
 * Currently models basic asynchronous read operations and initializes to 0xFF.
 * Flash programming sequences (5555->AA, etc.) are not yet modeled.
 ***************************************************************************************/

module sst39sf040 (
    input  wire [18:0] addr,  // 19 bits for 512KB (A0-A18)
    inout  wire [7:0]  data,
    input  wire        ce_n,
    input  wire        oe_n,
    input  wire        we_n
);
    // 524,288 bytes of memory
    reg [7:0] memory_array [0:524287];

    // Initialize erased flash state to 0xFF
    integer i;
    reg [7:0]  hash_pattern;
    initial begin
        for (i = 0; i < 524288; i = i + 1) begin
            hash_pattern = (i ^ (i >> 8) ^ (i >> 16)) & 8'hFF;
            memory_array[i] = hash_pattern;
        end
            
    end

    // --- Read Logic (10ns Access Time for sim) ---
    // The data bus is driven when CE and OE are low, and WE is high.
    wire [7:0] read_data = (!ce_n && !oe_n && we_n) ? memory_array[addr] : 8'hzz;
    assign #10 data = read_data;

    // --- Write Logic (Warning Only) ---
    always @(negedge we_n) begin
        if (!ce_n) begin
            $display("WARNING [SST39SF040]: Write attempted at %h. Flash programming sequence not modeled!", addr);
            $fatal(1);
        end
    end

endmodule
