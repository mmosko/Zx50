`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_dispatch
 * FILE: src/zx50_fpu_dispatch.v
 * DESCRIPTION:
 * Command Execution Dispatcher for the Zx50 FPU Coprocessor (CPLD Rev C1).
 *
 * FUNCTIONALITY:
 * - Decodes full opcode matrix: Format [7:4] and Operation [3:0].
 * - Decodes Management Opcodes (Format 0xF: CLR_STK, POP_TOS, DUP_TOS, RESET).
 * - Flags unmapped operations or invalid format fields via err_flag.
 * - Uses 4-phase level handshaking (exec_req / done_ack) for ZCLK/MCLK CDC.
 ***************************************************************************************/

module zx50_fpu_dispatch (
    input  wire       mclk,          // High-Speed Coprocessor Clock (20MHz / 40MHz)
    input  wire       reset_n,       // Global System Reset (Active LOW)
    input  wire       exec_req,      // Level request signal from ZCLK domain
    input  wire [7:0] opcode,        // Latched command opcode from Port 0x71

    output reg        done_ack,      // Level acknowledge signal to ZCLK domain
    output reg        err_flag,      // Set to 1 if opcode is invalid or unsupported
    output reg  [4:0] status_flags   // [ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW]
);

    // =========================================================================
    // 1. Opcode Matrix Definitions (FPU_REV1.md)
    // =========================================================================
    
    // --- Format Fields (opcode[7:4]) ---
    localparam FMT_I16     = 4'h0; // 16-Bit Signed Integer
    localparam FMT_I32     = 4'h1; // 32-Bit Signed Integer
    localparam FMT_I64     = 4'h2; // 64-Bit Signed Integer
    localparam FMT_FX1616  = 4'h3; // 32-Bit IEEE-754 / 16.16 Fixed Point
    localparam FMT_DFLOAT  = 4'h4; // 64-Bit IEEE-754 Double Precision Float
    localparam FMT_CFLOAT  = 4'h5; // 32-Bit Complex Float (a + bi)
    localparam FMT_SPECIAL = 4'hE; // Custom Extensions / Table Access
    localparam FMT_MGMT    = 4'hF; // Hardware & Stack Management

    // --- Operation Fields (opcode[3:0]) ---
    localparam OP_ADD      = 4'h0; // Addition (TOS = NOS + TOS)
    localparam OP_SUB      = 4'h1; // Subtraction (TOS = NOS - TOS)
    localparam OP_MUL      = 4'h2; // Multiplication (TOS = NOS * TOS)
    localparam OP_DIV      = 4'h3; // Division (TOS = NOS / TOS)
    localparam OP_SQRT     = 4'h4; // Square Root
    localparam OP_CHS      = 4'h5; // Change Sign (TOS = -TOS)
    localparam OP_SIN      = 4'h6; // Sine via Flash LUT
    localparam OP_COS      = 4'h7; // Cosine via Flash LUT
    localparam OP_EXP      = 4'h8; // Exponential via Flash LUT
    localparam OP_LN       = 4'h9; // Natural Log via Flash LUT
    localparam OP_LOG10    = 4'hA; // Base-10 Log via Flash LUT
    localparam OP_LOG_MUL  = 4'hB; // Fast Log-Table Multiply
    localparam OP_LOG_DIV  = 4'hC; // Fast Log-Table Divide

    // --- Hardware / Stack Management Opcodes (Format 0xF) ---
    localparam MGMT_CLR_STK = 8'hF0; // Clear Stack Pointer (SP = 0x00)
    localparam MGMT_POP_TOS = 8'hF1; // Drop Top of Stack
    localparam MGMT_DUP_TOS = 8'hF2; // Duplicate Top of Stack
    localparam MGMT_RESET   = 8'hFF; // Soft Reset Execution FSM

    // Opcode Field Extraction
    wire [3:0] fmt = opcode[7:4];
    wire [3:0] op  = opcode[3:0];

    // =========================================================================
    // 2. Clock Domain Crossing (CDC) Synchronizer for exec_req
    // =========================================================================
    reg [1:0] req_sync;
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) req_sync <= 2'b00;
        else          req_sync <= {req_sync[0], exec_req};
    end
    wire exec_req_mclk = req_sync[1];

    // =========================================================================
    // 3. Dispatch State Machine States
    // =========================================================================
    reg [2:0] state;
    localparam ST_IDLE   = 3'd0; // Waiting for synchronized exec_req
    localparam ST_DECODE = 3'd1; // Full Opcode Table Decoder
    localparam ST_EXEC   = 3'd2; // Arithmetic/Table Execution Phase
    localparam ST_FINISH = 3'd3; // Assert done_ack and hold until request drops

    reg [3:0] exec_cnt;         // Cycle counter for execution timing

    // =========================================================================
    // 4. Command Dispatch & Execution FSM
    // =========================================================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            state        <= ST_IDLE;
            done_ack     <= 1'b0;
            err_flag     <= 1'b0;
            status_flags <= 5'b00000;
            exec_cnt     <= 4'd0;
        end else begin
            case (state)
                ST_IDLE: begin
                    if (exec_req_mclk && !done_ack) begin
                        state    <= ST_DECODE;
                        exec_cnt <= 4'd0;
                    end else if (!exec_req_mclk) begin
                        done_ack <= 1'b0; // Clear ack once host drops request
                    end
                end

                ST_DECODE: begin
                    err_flag <= 1'b0; // Default clear error flag

                    case (fmt)
                        // -----------------------------------------------------
                        // Hardware & Stack Management Commands (Format 0xF)
                        // -----------------------------------------------------
                        FMT_MGMT: begin
                            case (opcode)
                                MGMT_CLR_STK, MGMT_POP_TOS, MGMT_DUP_TOS, MGMT_RESET: begin
                                    state <= ST_FINISH;
                                end
                                default: begin
                                    err_flag <= 1'b1; // Invalid management opcode
                                    state    <= ST_FINISH;
                                end
                            endcase
                        end

                        // -----------------------------------------------------
                        // Arithmetic Formats (i16, i32, i64, fx1616, dfloat, cfloat)
                        // -----------------------------------------------------
                        FMT_I16, FMT_I32, FMT_I64, FMT_FX1616, FMT_DFLOAT, FMT_CFLOAT: begin
                            case (op)
                                OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_SQRT, OP_CHS,
                                OP_SIN, OP_COS, OP_EXP, OP_LN, OP_LOG10, OP_LOG_MUL, OP_LOG_DIV: begin
                                    state <= ST_EXEC;
                                end
                                default: begin
                                    err_flag <= 1'b1; // Unmapped operation field
                                    state    <= ST_FINISH;
                                end
                            endcase
                        end

                        // -----------------------------------------------------
                        // Custom Extensions (Format 0xE)
                        // -----------------------------------------------------
                        FMT_SPECIAL: begin
                            state <= ST_EXEC;
                        end

                        default: begin
                            err_flag <= 1'b1; // Unmapped format field
                            state    <= ST_FINISH;
                        end
                    endcase
                end

                ST_EXEC: begin
                    // Execution step stub - will route to math core / SRAM fetch submodules
                    if (exec_cnt == 4'd4) begin
                        exec_cnt <= 4'd0;
                        state    <= ST_FINISH;
                    end else begin
                        exec_cnt <= exec_cnt + 1'b1;
                    end
                end

                ST_FINISH: begin
                    done_ack <= 1'b1; // Assert level acknowledge
                    if (!exec_req_mclk) begin
                        done_ack <= 1'b0; // Release ack once ZCLK domain clears request
                        state    <= ST_IDLE;
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule