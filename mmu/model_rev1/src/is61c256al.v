`timescale 1ns/1ps

module is61c256al (
    input  wire [14:0] addr,  // 32K
    inout  wire [7:0]  data,
    input  wire        ce_n,
    input  wire        oe_n,
    input  wire        we_n
);
    reg [7:0] memory_array [0:32767];

    // --- Read Logic (10ns Access Time) ---
    // If we are enabled, outputting, and NOT writing, drive the bus.
    wire [7:0] read_data = (!ce_n && !oe_n && we_n) ? memory_array[addr] : 8'hzz;
    assign #10 data = read_data;

    // --- Transparent Write Logic ---
    // React to ANY changes in address, data, or control lines
    always @(addr or data or ce_n or we_n) begin
        // Are the write conditions met?
        if (!ce_n && !we_n) begin
            // Ensure address is not floating before trying to write
            if (addr !== 15'bxxxxxxxxxxxxxxx && addr !== 15'bzzzzzzzzzzzzzzz) begin
                // Simulate the internal propagation delay of the write drivers (e.g., 5ns)
                #5; 
                
                // Re-verify conditions after the delay in case it was just a backplane glitch
                if (!ce_n && !we_n) begin
                    memory_array[addr] <= data;
                end
            end
        end
    end

endmodule