`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: sst39sf040
 * DESCRIPTION:
 * Simulation model for the SST39SF040 512KB (512K x 8) CMOS Flash ROM.
 * Configured with 55ns access time (SST39SF040-55) and JEDEC command sequence processing.
 *
 * PARAMETERS:
 *   MEM_INIT_FILE      : Path to optional hex file for table pre-loading.
 *   ALLOW_DIRECT_WRITE : If 1, enables direct SRAM-style byte writes (bypasses JEDEC FSM).
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

    // --- Array Initialization ---
    integer i;
    initial begin
        for (i = 0; i < 524288; i = i + 1) begin
            memory_array[i] = 8'hFF;
        end
        
        if (MEM_INIT_FILE != "") begin
            $readmemh(MEM_INIT_FILE, memory_array);
            $display("[%t ns] FLASH [SST39SF040]: Loaded memory table from %s", $time, MEM_INIT_FILE);
        end
    end

    // --- Read Logic ---
    // t_AA = 55ns (Address Access Time)
    // t_HZ = 15ns (Output Disable to High-Z)
    reg [7:0] data_out;
    wire read_enable = (!ce_n && !oe_n && we_n);

    always @(*) begin
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

    // --- JEDEC Write Command FSM ---
    reg [2:0] cmd_state;
    localparam ST_IDLE       = 3'd0;
    localparam ST_CMD1       = 3'd1; // Got 5555:AA (or 1555:AA on 14-bit CA bus)
    localparam ST_CMD2       = 3'd2; // Got 2AAA:55
    localparam ST_BYTE_PROG  = 3'd3; // Got 5555:A0 -> Next write is data
    localparam ST_ERASE_1    = 3'd4; // Got 5555:80 -> Waiting for 5555:AA
    localparam ST_ERASE_2    = 3'd5; // Got 5555:AA -> Waiting for 2AAA:55
    localparam ST_ERASE_3    = 3'd6; // Waiting for Chip (5555:10) or Sector Erase (Sector:30)

    // Mask check for lower 14 bits (CA[13:0] active window on CPLD)
    wire [13:0] addr_14bit = addr[13:0];

    always @(posedge we_n or posedge ce_n) begin
        if ((we_n && !ce_n) || (ce_n && !we_n)) begin
            if (ALLOW_DIRECT_WRITE) begin
                // Direct SRAM-style write for rapid testbench execution
                memory_array[addr] <= memory_array[addr] & data;
                $display("[%t ns] FLASH [SST39SF040]: Direct write at addr %h <= %h", $time, addr, data);
            end else begin
                // Standard NOR Flash JEDEC Command Decoding
                case (cmd_state)
                    ST_IDLE: begin
                        if ((addr_14bit == 14'h1555 || addr[14:0] == 15'h5555) && data == 8'hAA)
                            cmd_state <= ST_CMD1;
                        else if (data == 8'hF0) // Software Reset / Exit
                            cmd_state <= ST_IDLE;
                    end

                    ST_CMD1: begin
                        if (addr_14bit == 14'h2AAA && data == 8'h55)
                            cmd_state <= ST_CMD2;
                        else
                            cmd_state <= ST_IDLE;
                    end

                    ST_CMD2: begin
                        if ((addr_14bit == 14'h1555 || addr[14:0] == 15'h5555) && data == 8'hA0)
                            cmd_state <= ST_BYTE_PROG;
                        else if ((addr_14bit == 14'h1555 || addr[14:0] == 15'h5555) && data == 8'h80)
                            cmd_state <= ST_ERASE_1;
                        else
                            cmd_state <= ST_IDLE;
                    end

                    ST_BYTE_PROG: begin
                        // NOR Flash physics: Programming can only flip 1 -> 0
                        memory_array[addr] <= memory_array[addr] & data;
                        $display("[%t ns] FLASH [SST39SF040]: Byte Programmed at %h <= %h (Value: %h)", 
                                 $time, addr, data, memory_array[addr] & data);
                        cmd_state <= ST_IDLE;
                    end

                    ST_ERASE_1: begin
                        if ((addr_14bit == 14'h1555 || addr[14:0] == 15'h5555) && data == 8'hAA)
                            cmd_state <= ST_ERASE_2;
                        else
                            cmd_state <= ST_IDLE;
                    end

                    ST_ERASE_2: begin
                        if (addr_14bit == 14'h2AAA && data == 8'h55)
                            cmd_state <= ST_ERASE_3;
                        else
                            cmd_state <= ST_IDLE;
                    end

                    ST_ERASE_3: begin
                        if ((addr_14bit == 14'h1555 || addr[14:0] == 15'h5555) && data == 8'h10) begin
                            // Chip Erase: Reset all bytes to 0xFF
                            for (i = 0; i < 524288; i = i + 1)
                                memory_array[i] <= 8'hFF;
                            $display("[%t ns] FLASH [SST39SF040]: Chip Erase Completed!", $time);
                        end else if (data == 8'h30) begin
                            // 4KB Sector Erase (addr[18:12] defines sector)
                            for (i = 0; i < 4096; i = i + 1)
                                memory_array[{addr[18:12], 12'b0} + i] <= 8'hFF;
                            $display("[%t ns] FLASH [SST39SF040]: 4KB Sector Erase at Sector %h Completed!", $time, addr[18:12]);
                        end
                        cmd_state <= ST_IDLE;
                    end

                    default: cmd_state <= ST_IDLE;
                endcase
            end
        end
    end

endmodule
