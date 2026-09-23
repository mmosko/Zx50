`timescale 1ns/1ps

// ISSI IS61C5128AS (512K x 8) 25ns Asynchronous SRAM Model
module is61c5128as #(
    parameter MEM_INIT_FILE = "" // Optional: "firmware.hex" for simulation pre-load
)(
    input  wire [18:0] addr,  // Address Bus (A0-A18)
    inout  wire [7:0]  data,  // Data Bus (I/O0-I/O7)
    input  wire        ce_n,  // Chip Enable (~CE)
    input  wire        oe_n,  // Output Enable (~OE)
    input  wire        we_n   // Write Enable (~WE)
);

    // 512K x 8 Memory Array
    reg [7:0] memory_array [0:524287];

    // Optional Memory Initialization
    initial begin
        if (MEM_INIT_FILE != "") begin
            $readmemh(MEM_INIT_FILE, memory_array);
        end
    end

    // --- Read Logic ---
    // t_AA  = 25ns (Address / Chip Enable Access Time)
    // t_HZ  = 8ns  (Output Disable Time to High-Z)
    reg [7:0] data_out;
    wire read_enable = (!ce_n && !oe_n && we_n);

    always @(*) begin
        if (read_enable) begin
            if (^addr !== 1'bx) begin
                data_out <= #25 memory_array[addr]; // Valid Read
            end else begin
                data_out <= #25 8'hxx;              // Floating/Unknown Address
            end
        end else begin
            data_out <= #8 8'hzz;                   // Fast High-Z release
        end
    end

    assign data = data_out;

    // --- Write Logic ---
    // SRAM commits data on the trailing (rising) edge of ~WE or ~CE.
    always @(posedge we_n or posedge ce_n) begin
        // Verify write conditions were active at the moment of the rising edge
        if ((we_n && !ce_n) || (ce_n && !we_n)) begin
            if (^addr !== 1'bx && ^data !== 1'bx) begin
                memory_array[addr] <= data;
            end else begin
                $display("[%t ns] SRAM WRITE ERROR: Suppressed write due to X/Z state on addr/data!", $time);
            end
        end
    end

endmodule
