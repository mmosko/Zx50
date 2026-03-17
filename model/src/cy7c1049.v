`timescale 1ns/1ps

module cy7c1049 (
    input  wire [18:0] addr,  // 19 bits for 512KB (A0-A18)
    inout  wire [7:0]  data,
    input  wire        ce_n,
    input  wire        oe_n,
    input  wire        we_n
);
    // 524,288 bytes of memory
    reg [7:0] memory_array [0:524287];

    // --- Read Logic (10ns Access Time) ---
    // The data bus is driven 10ns after OE, CE, and Address are all valid.
    wire [7:0] read_data = (!ce_n && !oe_n && we_n) ? memory_array[addr] : 8'hzz;
    assign #10 data = read_data;

    // --- Transparent Write Logic ---
    // This block wakes up the picosecond ANY of these signals change.
    always @(addr or data or ce_n or we_n) begin
        // Are the write conditions met?
        if (!ce_n && !we_n) begin
            // Ensure address is valid (not floating or unknown)
            if (addr !== 19'bxxxxxxxxxxxxxxxxxxx && addr !== 19'bzzzzzzzzzzzzzzzzzzz) begin
                // Intra-assignment delay: perfectly models the internal propagation 
                // delay of the write drivers without blocking the simulation thread.
                // If the Z80 data changes mid-write, the cell updates 5ns later.
                memory_array[addr] <= #5 data;
            end
        end
    end

    // --- Verification Aid (Optional) ---
    // Print to the console when a write officially completes (rising edge of WE)
    always @(posedge we_n) begin
        if (!ce_n) begin
            // $display("CY7C1049: Latched Write at Addr %h = %h", addr, data);
        end
    end

endmodule