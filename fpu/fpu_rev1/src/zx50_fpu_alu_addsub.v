`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_alu_addsub
 * FILE: src/zx50_fpu_alu_addsub.v
 * DESCRIPTION:
 * 8-Bit Byte-Serial Adder / Subtractor / Negator for ZX50 FPU Coprocessor.
 *
 * OPERATIONS HANDLED:
 * - OP_ADD (0x0) : NOS + TOS -> NOS
 * - OP_SUB (0x1) : NOS - TOS -> NOS
 * - OP_CHS (0x5) : Two's Complement Negation (-TOS -> NOS)
 ***************************************************************************************/

module zx50_fpu_alu_addsub (
    input  wire        mclk,            // Coprocessor Clock (20MHz / 40MHz)
    input  wire        reset_n,         // Global System Reset (Active LOW)

    // --- Control Interface ---
    input  wire        start_p,         // 1-tick start pulse
    input  wire [3:0]  fmt,             // Opcode format field (0x0 = i16, 0x1 = i32)
    input  wire [3:0]  op,              // Opcode operation field
    input  wire [7:0]  sp_in,           // Stack Pointer input

    output reg         done_p,          // Execution complete pulse
    output reg         err_flag,        // Error flag
    output reg  [4:0]  status_flags,    // [ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW]

    // --- Private Memory Master Interface ---
    output reg         mem_we_req,      // SRAM write request
    output reg         mem_oe_req,      // SRAM read request
    output wire        sel_flash,       // Always 0 (SRAM access only)
    output reg  [14:0] mem_addr,        // Private 15-bit address bus
    output reg  [7:0]  mem_wdata,       // Write payload
    input  wire [7:0]  mem_rdata,       // Readback data payload
    input  wire        mem_ready        // Transaction completion handshake
);

    // Operation Decoding
    localparam OP_ADD = 4'h0;
    localparam OP_SUB = 4'h1;
    localparam OP_CHS = 4'h5;

    // Internal State Machine
    reg [2:0] state;
    localparam ST_IDLE   = 3'd0;
    localparam ST_READ_A = 3'd1;
    localparam ST_READ_B = 3'd2;
    localparam ST_EXEC   = 3'd3;
    localparam ST_WRITE  = 3'd4;
    localparam ST_FINISH = 3'd5;

    reg [7:0] acc;
    reg [7:0] operand_b;
    reg       carry_borrow;
    reg [2:0] byte_cnt;

    assign sel_flash = 1'b0; // Add/Sub/CHS never query Flash ROM
    wire [2:0] max_bytes = (fmt == 4'h0) ? 3'd1 : 3'd3;

    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            state        <= ST_IDLE;
            acc          <= 8'h00;
            operand_b    <= 8'h00;
            carry_borrow <= 1'b0;
            byte_cnt     <= 3'd0;
            done_p       <= 1'b0;
            err_flag     <= 1'b0;
            status_flags <= 5'b00000;
            mem_we_req   <= 1'b0;
            mem_oe_req   <= 1'b0;
            mem_addr     <= 15'h0000;
            mem_wdata    <= 8'h00;
        end else begin
            done_p     <= 1'b0;
            mem_we_req <= 1'b0;
            mem_oe_req <= 1'b0;

            case (state)
                ST_IDLE: begin
                    err_flag     <= 1'b0;
                    byte_cnt     <= 3'd0;
                    carry_borrow <= 1'b0;
                    if (start_p) begin
                        state <= ST_READ_A;
                    end
                end

                // --- Read TOS Byte (Operand A) ---
                ST_READ_A: begin
                    mem_oe_req <= 1'b1;
                    mem_addr   <= {7'b0000000, (sp_in - 8'd4 + {5'b00000, byte_cnt})};
                    
                    if (mem_ready) begin
                        acc   <= mem_rdata;
                        state <= ST_READ_B;
                    end
                end

                // --- Read NOS Byte (Operand B) ---
                ST_READ_B: begin
                    mem_oe_req <= 1'b1;
                    mem_addr   <= {7'b0000000, (sp_in - 8'd8 + {5'b00000, byte_cnt})};
                    
                    if (mem_ready) begin
                        operand_b <= mem_rdata;
                        state     <= ST_EXEC;
                    end
                end

                // --- 8-Bit Calculation ---
                ST_EXEC: begin
                    case (op)
                        OP_ADD: begin
                            {carry_borrow, acc} <= operand_b + acc + carry_borrow;
                        end

                        OP_SUB: begin
                            {carry_borrow, acc} <= operand_b - acc - carry_borrow;
                        end

                        OP_CHS: begin
                            {carry_borrow, acc} <= (~acc) + 1'b1;
                        end

                        default: begin
                            acc <= acc;
                        end
                    endcase

                    state <= ST_WRITE;
                end

                // --- Write Result Back to NOS Frame ---
                ST_WRITE: begin
                    mem_we_req <= 1'b1;
                    mem_addr   <= {7'b0000000, (sp_in - 8'd8 + {5'b00000, byte_cnt})};
                    mem_wdata  <= acc;

                    if (mem_ready) begin
                        if (byte_cnt == max_bytes) begin
                            state <= ST_FINISH;
                        end else begin
                            byte_cnt <= byte_cnt + 1'b1;
                            state    <= ST_READ_A;
                        end
                    end
                end

                // --- Lock Status Flags and Assert Completion Pulse ---
                ST_FINISH: begin
                    done_p          <= 1'b1;
                    status_flags[4] <= (acc == 8'h00); // ZERO
                    status_flags[3] <= acc[7];         // SIGN
                    status_flags[2] <= carry_borrow;   // CARRY
                    status_flags[1] <= 1'b0;           // OVERFLOW
                    status_flags[0] <= 1'b0;           // UNDERFLOW
                    state           <= ST_IDLE;
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
