`timescale 1ns/1ps

// 74ABT244: Octal Buffer/Line Driver (Unidirectional)
module ic_74abt244 (
    input  wire [7:0] a,
    output wire [7:0] y,
    input  wire       oe_n
);
    // Typical propagation delay: 3ns
    assign #3 y = (!oe_n) ? a : 8'hzz;
endmodule
