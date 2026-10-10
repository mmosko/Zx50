`timescale 1ns/1ps

/***************************************************************************************
* MODULE: zx50_fpu_data_ram
* DESCRIPTION:
* System Data RAM and Table ROM for Zx50 FPU Rev 2.
* Maps to 4 cascaded MachXO2 EBR blocks (EBR 0, 1, 2, 3) in 1024 x 32-bit configuration.
*
* Memory Partition:
* - 0x000 - 0x0FF (256 words / 1 KB): Writeable RAM (Stack, Scratchpad, User Storage)
* - 0x100 - 0x3FF (768 words / 3 KB): Read-Only Constants, Trig, Chebyshev, Seed LUTs
***************************************************************************************/

module zx50_fpu_data_ram #(
    parameter INIT_FILE = "fpu_data_ram.hex"
)(
    input  wire        fclk,
    input  wire [9:0]  addr,        // 10-bit DATA_RAM Address (0x000..0x3FF)
    input  wire [31:0] din,         // Data input for writeback
    input  wire        we,          // Write enable request
    output reg  [31:0] dout         // Data output
);

    // 1,024 words x 32 bits (4 KB total)
    reg [31:0] mem [0:1023];

    // Hardware Write-Protection Guard:
    // Writes are ONLY allowed within the low 256-word RAM region (addr[9:8] == 2'b00).
    // Addresses >= 0x100 (ROM space) automatically suppress inner_we.
    wire inner_we = we && (addr[9:8] == 2'b00);

    // Pre-load RAM/ROM initial image during simulation/synthesis
    initial begin
        if (INIT_FILE != "") begin
            $readmemh(INIT_FILE, mem);
        end
    end

    // Synchronous Read/Write Execution
    always @(posedge fclk) begin
        if (inner_we) begin
            mem[addr] <= din;
        end
        dout <= mem[addr];
    end

endmodule
