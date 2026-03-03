`timescale 1ns/1ps

// Emulates 2x Cypress CY7C1049GN-10VXIT (512K x 8 SRAM)
module zx50_mem (
    input  wire [18:0] addr,    // 19-bit physical address (A0-A18)
    inout  wire [7:0]  data,    // Bidirectional data bus
    input  wire        ce0_n,   // Chip Enable for Lower 512KB (Bank 0x00-0x7F)
    input  wire        ce1_n,   // Chip Enable for Upper 512KB (Bank 0x80-0xFF)
    input  wire        oe_n,    // Output Enable (~RD)
    input  wire        we_n     // Write Enable (~WR)
);

    // Two 512KB physical silicon arrays 
    reg [7:0] ram0 [0:524287]; 
    reg [7:0] ram1 [0:524287];

    // --- Read Logic ---
    // Drive the bus ONLY if a specific chip is enabled, output is enabled, AND we are not writing.
    assign data = (!ce0_n && !oe_n && we_n) ? ram0[addr] :
                  (!ce1_n && !oe_n && we_n) ? ram1[addr] : 
                  8'hzz;

    // --- Write Logic ---
    // Real asynchronous SRAMs latch data at the end of the write pulse (rising edge of WE)
    always @(posedge we_n) begin
        if (!ce0_n) ram0[addr] <= data;
        if (!ce1_n) ram1[addr] <= data;
    end

endmodule