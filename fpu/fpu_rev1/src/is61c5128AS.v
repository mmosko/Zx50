`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: is61c5128as
 * DESCRIPTION:
 * ISSI IS61C5128AS (512K x 8) 25ns Asynchronous SRAM Model.
 * Fast 25ns read access, 8ns high-Z release, posedge WE/CE write sampling.
 * Uses explicit sensitivity list to prevent iverilog @(*) array elaboration hangs.
 ***************************************************************************************/

module is61c5128as #(
    parameter MEM_INIT_FILE = ""
)(
    input  wire [18:0] addr,  // Address Bus (A0-A18)
    inout  wire [7:0]  data,  // Data Bus (I/O0-I/O7)
    input  wire        ce_n,  // Chip Enable (~CE)
    input  wire        oe_n,  // Output Enable (~OE)
    input  wire        we_n   // Write Enable (~WE)
);

    // 512K x 8 Memory Array
    reg [7:0] memory_array [0:524287];

    // --- Optional Memory Pre-load ---
    initial begin
        if (MEM_INIT_FILE != "") begin
            $readmemh(MEM_INIT_FILE, memory_array);
            $display("[%t ns] SRAM [IS61C5128AS]: Loaded memory from %s", $time, MEM_INIT_FILE);
        end
    end

    // --- Read Logic ---
    reg [7:0] data_out;
    wire read_enable = (!ce_n && !oe_n && we_n);

    // EXPLICIT SENSITIVITY: Avoids @(*) array unrolling trap in iverilog
    always @(read_enable or addr) begin
        if (read_enable) begin
            if (^addr !== 1'bx) begin
                data_out <= #25 memory_array[addr];
            end else begin
                data_out <= #25 8'hxx;
            end
        end else begin
            data_out <= #8 8'hzz;
        end
    end

    assign data = data_out;

    // --- Write Logic ---
    always @(posedge we_n or posedge ce_n) begin
        if ((we_n && !ce_n) || (ce_n && !we_n)) begin
            if (^addr !== 1'bx && ^data !== 1'bx) begin
                memory_array[addr] <= data;
            end else begin
                $display("[%t ns] SRAM WRITE ERROR: Suppressed write due to X/Z state on addr/data!", $time);
            end
        end
    end

endmodule
