`timescale 1ns/1ps

// Emulates 2x Cypress CY7C1049GN-10VXIT (512K x 8 SRAM)
module zx50_mem (
    input  wire [18:0] addr,    // 19 bits for 512KB
    inout  wire [7:0]  data,
    input  wire        ce0_n,
    input  wire        ce1_n,
    input  wire        oe_n,
    input  wire        we_n
);
    // 512KB = 524,288 bytes
    reg [7:0] ram0 [0:524287]; 
    reg [7:0] ram1 [0:524287];

    assign #10 data = (!ce0_n && !oe_n && we_n) ? ram0[addr] :
                      (!ce1_n && !oe_n && we_n) ? ram1[addr] : 8'hzz;

    // --- Write Logic ---
    // Capture data on the rising edge of WE_n (End of write cycle)
    always @(posedge we_n) begin
        if (!ce0_n) begin
            ram0[addr] <= data;
            $display("SRAM Write [Bank 0]: Addr=%h, Data=%h", addr, data);
        end
        if (!ce1_n) begin
            ram1[addr] <= data;
            $display("SRAM Write [Bank 1]: Addr=%h, Data=%h", addr, data);
        end
    end

endmodule