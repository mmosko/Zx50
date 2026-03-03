module zx50_mem (
    input wire [11:0] addr_low,
    inout wire [7:0]  d_bus,
    input wire rd_n, wr_n, mreq_n,
    input wire [7:0]  p_addr_hi,
    input wire active
);
    // Assemble the 19-bit address for a 512KB SRAM chip
    wire [18:0] s_addr = {p_addr_hi[6:0], addr_low};

    // --- The Fail-Safe Chip Enables ---
    // Using strict equality (===) prevents 'z' or 'x' from propagating.
    // If active is exactly 1, and bit 7 matches the chip, pull CE low (0). Otherwise, stay high (1).
    wire ce0_n = (active === 1'b1 && p_addr_hi[7] === 1'b0) ? 1'b0 : 1'b1;
    wire ce1_n = (active === 1'b1 && p_addr_hi[7] === 1'b1) ? 1'b0 : 1'b1;

    // Simulation models for 2x 512KB SRAMs
    reg [7:0] ram0 [0:524287]; 
    reg [7:0] ram1 [0:524287]; 

    // --- Read Logic ---
    // Drive the bus ONLY if a specific chip is enabled AND it's a memory read.
    assign d_bus = (!mreq_n && !rd_n && !ce0_n) ? ram0[s_addr] :
                   (!mreq_n && !rd_n && !ce1_n) ? ram1[s_addr] : 
                   8'hzz;

    // --- Write Logic ---
    // Write ONLY to the chip whose CE is pulled low.
    always @(*) begin
        if (!mreq_n && !wr_n) begin
            if (!ce0_n) ram0[s_addr] <= d_bus;
            if (!ce1_n) ram1[s_addr] <= d_bus;
        end
    end
endmodule