`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: sst39sf040
 * DESCRIPTION:
 * Simulation model for the SST39SF040 512KB (512K x 8) CMOS Flash ROM.
 * Configured with 55ns access time (SST39SF040-55).
 * Uses explicit sensitivity list to prevent iverilog @(*) array elaboration hangs.
 ***************************************************************************************/

module sst39sf040 #(
    parameter MEM_INIT_FILE      = "",
    parameter ALLOW_DIRECT_WRITE = 0 
)(
    input  wire [18:0] addr,  // Address Bus A0-A18
    inout  wire [7:0]  data,  // Data Bus D0-D7
    input  wire        ce_n,  // Chip Enable (~CE)
    input  wire        oe_n,  // Output Enable (~OE)
    input  wire        we_n   // Write Enable (~WE)
);

    // 512K x 8 Flash Memory Array
    reg [7:0] memory_array [0:524287];

    // --- Optional Memory Pre-load ---
    initial begin
        if (MEM_INIT_FILE != "") begin
            $readmemh(MEM_INIT_FILE, memory_array);
            $display("[%t ns] FLASH [SST39SF040]: Loaded memory table from %s", $time, MEM_INIT_FILE);
        end
    end

    // --- Read Logic ---
    reg [7:0] data_out;
    wire read_enable = (!ce_n && !oe_n && we_n);

    // EXPLICIT SENSITIVITY: Avoids @(*) array unrolling trap in iverilog
    always @(read_enable or addr) begin
        if (read_enable) begin
            if (^addr !== 1'bx) begin
                data_out <= #55 memory_array[addr];
            end else begin
                data_out <= #55 8'hxx;
            end
        end else begin
            data_out <= #15 8'hzz;
        end
    end

    assign data = data_out;

    // --- Write Logic (Warning Only) ---
    always @(negedge we_n) begin
        if (!ce_n) begin
            $display("WARNING [SST39SF040]: Write attempted at %h. Flash programming sequence not modeled!", addr);
            $fatal(1);
        end
    end

endmodule
