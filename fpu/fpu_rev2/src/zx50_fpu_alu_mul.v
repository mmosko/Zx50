`timescale 1ns/1ps
`include "fpu_rom_map.vh"

/***************************************************************************************
 * MODULE: zx50_fpu_alu_mul
 * FILE: src/zx50_fpu_alu_mul.v
 * DESCRIPTION:
 * Quarter-Square Hardware Multiplier Submodule for ZX50 FPU Coprocessor.
 *
 * ALGORITHM:
 *   a * b = f(a + b) - f(|a - b|)   where f(n) = floor(n^2 / 4)
 * Queries 16-bit f(n) entries directly from private Flash ROM using FLASH_QS_TABLE_BASE.
 ***************************************************************************************/

module zx50_fpu_alu_mul (
    input  wire        mclk,            // Coprocessor Clock (20MHz / 40MHz)
    input  wire        reset_n,         // Global System Reset (Active LOW)

    // --- Control Interface ---
    input  wire        start_p,         // 1-tick start pulse
    input  wire [3:0]  fmt,             // Opcode format field (0x0 = i16, 0x1 = i32)
    input  wire [7:0]  sp_in,           // Stack Pointer input

    output reg         done_p,          // Execution complete pulse
    output reg         err_flag,        // Error flag
    output reg  [4:0]  status_flags,    // [ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW]

    // --- Private Memory Master Interface ---
    output reg         mem_we_req,      // SRAM write request
    output reg         mem_oe_req,      // SRAM/Flash read request
    output reg         sel_flash,       // 1 = Flash ROM, 0 = SRAM
    output reg  [14:0] mem_addr,        // Private 15-bit address bus
    output reg  [7:0]  mem_wdata,       // Write payload
    input  wire [7:0]  mem_rdata,       // Readback data payload
    input  wire        mem_ready        // Transaction completion handshake
);

    // Internal FSM States
    reg [3:0] state;
    localparam ST_IDLE          = 4'd0;
    localparam ST_READ_A        = 4'd1;
    localparam ST_READ_B        = 4'd2;
    localparam ST_MUL_PREP      = 4'd3;
    localparam ST_MUL_RD_FSUM_L = 4'd4;
    localparam ST_MUL_RD_FSUM_M = 4'd5;
    localparam ST_MUL_RD_FDIF_L = 4'd6;
    localparam ST_MUL_RD_FDIF_M = 4'd7;
    localparam ST_MUL_SUB       = 4'd8;
    localparam ST_MUL_WRITE_LO  = 4'd9;
    localparam ST_MUL_WRITE_HI  = 4'd10;
    localparam ST_MUL_WRITE_PAD = 4'd11;
    localparam ST_FINISH        = 4'd12;

    reg [7:0]  acc;
    reg [7:0]  operand_b;
    reg [8:0]  qs_sum;
    reg [7:0]  qs_diff;
    reg [15:0] qs_f_sum;
    reg [15:0] qs_f_diff;
    reg [15:0] mul_product;
    reg [2:0]  byte_cnt;

    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            state       <= ST_IDLE;
            acc         <= 8'h00;
            operand_b   <= 8'h00;
            qs_sum      <= 9'd0;
            qs_diff     <= 8'd0;
            qs_f_sum    <= 16'd0;
            qs_f_diff   <= 16'd0;
            mul_product <= 16'd0;
            byte_cnt    <= 3'd0;
            done_p      <= 1'b0;
            err_flag    <= 1'b0;
            status_flags<= 5'b00000;
            mem_we_req  <= 1'b0;
            mem_oe_req  <= 1'b0;
            sel_flash   <= 1'b0;
            mem_addr    <= 15'h0000;
            mem_wdata   <= 8'h00;
        end else begin
            done_p     <= 1'b0;
            mem_we_req <= 1'b0;
            mem_oe_req <= 1'b0;

            case (state)
                ST_IDLE: begin
                    err_flag <= 1'b0;
                    byte_cnt <= 3'd0;
                    if (start_p) begin
                        state <= ST_READ_A;
                    end
                end

                // --- Read TOS LSB (a) ---
                ST_READ_A: begin
                    sel_flash  <= 1'b0;
                    mem_oe_req <= 1'b1;
                    mem_addr   <= {7'b0000000, (sp_in - 8'd4)};

                    if (mem_ready) begin
                        acc   <= mem_rdata;
                        state <= ST_READ_B;
                    end
                end

                // --- Read NOS LSB (b) ---
                ST_READ_B: begin
                    sel_flash  <= 1'b0;
                    mem_oe_req <= 1'b1;
                    mem_addr   <= {7'b0000000, (sp_in - 8'd8)};

                    if (mem_ready) begin
                        operand_b <= mem_rdata;
                        state     <= ST_MUL_PREP;
                    end
                end

                // --- Compute Lookup Keys: (a + b) and |a - b| ---
                ST_MUL_PREP: begin
                    qs_sum <= acc + operand_b;
                    if (acc >= operand_b) begin
                        qs_diff <= acc - operand_b;
                    end else begin
                        qs_diff <= operand_b - acc;
                    end
                    state <= ST_MUL_RD_FSUM_L;
                end

                // --- Query Flash ROM: f(a + b) LSB ---
                ST_MUL_RD_FSUM_L: begin
                    sel_flash  <= 1'b1;
                    mem_oe_req <= 1'b1;
                    mem_addr   <= `FLASH_QS_TABLE_BASE + {5'b00000, qs_sum, 1'b0};

                    if (mem_ready) begin
                        qs_f_sum[7:0] <= mem_rdata;
                        state         <= ST_MUL_RD_FSUM_M;
                    end
                end

                // --- Query Flash ROM: f(a + b) MSB ---
                ST_MUL_RD_FSUM_M: begin
                    sel_flash  <= 1'b1;
                    mem_oe_req <= 1'b1;
                    mem_addr   <= `FLASH_QS_TABLE_BASE + {5'b00000, qs_sum, 1'b1};

                    if (mem_ready) begin
                        qs_f_sum[15:8] <= mem_rdata;
                        state          <= ST_MUL_RD_FDIF_L;
                    end
                end

                // --- Query Flash ROM: f(|a - b|) LSB ---
                ST_MUL_RD_FDIF_L: begin
                    sel_flash  <= 1'b1;
                    mem_oe_req <= 1'b1;
                    mem_addr   <= `FLASH_QS_TABLE_BASE + {6'b000000, qs_diff, 1'b0};

                    if (mem_ready) begin
                        qs_f_diff[7:0] <= mem_rdata;
                        state          <= ST_MUL_RD_FDIF_M;
                    end
                end

                // --- Query Flash ROM: f(|a - b|) MSB ---
                ST_MUL_RD_FDIF_M: begin
                    sel_flash  <= 1'b1;
                    mem_oe_req <= 1'b1;
                    mem_addr   <= `FLASH_QS_TABLE_BASE + {6'b000000, qs_diff, 1'b1};

                    if (mem_ready) begin
                        qs_f_diff[15:8] <= mem_rdata;
                        state           <= ST_MUL_SUB;
                    end
                end

                // --- Subtract LUT Entries: Product = f(a+b) - f(|a-b|) ---
                ST_MUL_SUB: begin
                    mul_product <= qs_f_sum - qs_f_diff;
                    state       <= ST_MUL_WRITE_LO;
                end

                // --- Write Product LSB to Byte 0 of NOS Frame ---
                ST_MUL_WRITE_LO: begin
                    sel_flash  <= 1'b0;
                    mem_we_req <= 1'b1;
                    mem_addr   <= {7'b0000000, (sp_in - 8'd8)};
                    mem_wdata  <= mul_product[7:0];

                    if (mem_ready) begin
                        state <= ST_MUL_WRITE_HI;
                    end
                end

                // --- Write Product MSB to Byte 1 of NOS Frame ---
                ST_MUL_WRITE_HI: begin
                    sel_flash  <= 1'b0;
                    mem_we_req <= 1'b1;
                    mem_addr   <= {7'b0000000, (sp_in - 8'd8 + 8'd1)};
                    mem_wdata  <= mul_product[15:8];

                    if (mem_ready) begin
                        if (fmt == 4'h0) begin // i16 format (2 bytes complete)
                            state <= ST_FINISH;
                        end else begin         // i32 format (zero-pad bytes 2 & 3)
                            byte_cnt <= 3'd2;
                            state    <= ST_MUL_WRITE_PAD;
                        end
                    end
                end

                // --- Zero-Pad Upper Bytes for 32-Bit Frame ---
                ST_MUL_WRITE_PAD: begin
                    sel_flash  <= 1'b0;
                    mem_we_req <= 1'b1;
                    mem_addr   <= {7'b0000000, (sp_in - 8'd8 + {5'b00000, byte_cnt})};
                    mem_wdata  <= 8'h00;

                    if (mem_ready) begin
                        if (byte_cnt == 3'd3) begin
                            state <= ST_FINISH;
                        end else begin
                            byte_cnt <= byte_cnt + 1'b1;
                            state    <= ST_MUL_WRITE_PAD;
                        end
                    end
                end

                // --- Lock Flags and Completion Pulse ---
                ST_FINISH: begin
                    done_p          <= 1'b1;
                    status_flags[4] <= (mul_product == 16'h0000); // ZERO
                    status_flags[3] <= mul_product[15];          // SIGN
                    status_flags[2] <= 1'b0;                     // CARRY
                    status_flags[1] <= 1'b0;                     // OVERFLOW
                    status_flags[0] <= 1'b0;                     // UNDERFLOW
                    state           <= ST_IDLE;
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
