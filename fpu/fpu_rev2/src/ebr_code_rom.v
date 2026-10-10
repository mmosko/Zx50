`timescale 1ns/1ps

/***************************************************************************************
* MODULE: ebr_code_rom
* DESCRIPTION:
* Microcode Execution Store for Zx50 FPU Rev 2.
* Maps to 4 cascaded MachXO2 EBR blocks (EBR 4, 5, 6, 7) in 1024 x 32-bit configuration.
*
* Sequenced directly by the 10-bit Program Counter (UPC[9:0]).
***************************************************************************************/

module ebr_code_rom #(
    parameter INIT_FILE = "fpu_code_rom.hex"
)(
    input  wire        fclk,
    input  wire [9:0]  addr,        // UPC[9:0] (0x000..0x3FF)
    output reg  [31:0] dout         // Fetched 32-bit Micro-Instruction
);

    // 1,024 words x 32 bits (4 KB total)
    reg [31:0] mem [0:1023];

    // Pre-load microcode binary hex file during simulation/synthesis
    initial begin
        if (INIT_FILE != "") begin
            $readmemh(INIT_FILE, mem);
        end
    end

    // Synchronous Read Cycle (Single-cycle EBR access)
    always @(posedge fclk) begin
        dout <= mem[addr];
    end

endmodule
