`timescale 1ns/1ps

// 74ABT245: Octal Bidirectional Transceiver
module ic_74abt245 (
    inout  wire [7:0] a,
    inout  wire [7:0] b,
    input  wire       dir,   // 1 = A to B, 0 = B to A
    input  wire       oe_n
);
    // Typical propagation delay: 3ns
    assign #3 b = (!oe_n && dir)  ? a : 8'hzz;
    assign #3 a = (!oe_n && !dir) ? b : 8'hzz;
endmodule
