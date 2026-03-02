/*
 * Module: zx50_mmu
 * Logic: Distributed MMU for Zx50 Bus
 * Goal: Verify 16-page translation and snoop-based handover.
 */
module zx50_mmu (
    input wire [15:0] addr,     // Z80 Address Bus
    input wire [7:0] d_bus,     // Z80 Data Bus
    input wire [3:0] card_id_sw,// Physical DIP Switch (0-15)
    input wire iorq_n,          // I/O Request
    input wire wr_n,            // Write Enable
    input wire boot_en_n,       // Boot Jumper
    
    output reg [7:0] p_addr_hi, // Physical Page P[19:12]
    output reg active           // Card Select
);

    parameter MMU_FAMILY_ID = 8'h30;
    parameter MMU_MASK      = 8'hF0;

    reg [7:0] atl_table [0:15]; // 128 Bits
    reg [15:0] pal_bits;        // 16 Bits

    // Distributed Snoop: Rising edge for stability
    always @(posedge iorq_n or posedge wr_n) begin
        if ((addr[7:0] & MMU_MASK) == MMU_FAMILY_ID) begin
            // If the write is to MY specific port
            if (addr[7:0] == (MMU_FAMILY_ID | card_id_sw)) begin
                atl_table[addr[11:8]] <= d_bus;
                pal_bits[addr[11:8]]  <= 1'b1;
            end 
            // If the write is to any other MMU port in the family
            else begin
                pal_bits[addr[11:8]]  <= 1'b0; // Step down
            end
        end
    end

    // Combinational Translation
    always @(*) begin
        p_addr_hi = atl_table[addr[15:12]];
        active    = pal_bits[addr[15:12]];
    end

    // 1:1 Initial Mapping Logic
    integer i;
    initial begin
        for (i = 0; i < 16; i = i + 1) begin
            atl_table[i] = i[7:0]; // 1:1 Mapping
            pal_bits[i]  = (!boot_en_n && i >= 8) ? 1'b1 : 1'b0; 
        end
    end
endmodule
