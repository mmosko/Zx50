`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_dispatch
 * FILE: src/zx50_fpu_dispatch.v
 * DESCRIPTION:
 * Command Execution Dispatcher for the Zx50 FPU Coprocessor (CPLD Rev C1).
 *
 * ARCHITECTURAL SPECIFICATION:
 * - Decodes full opcode matrix: Format [7:4] and Operation [3:0].
 * - Delegates Format 0xF management opcodes to zx50_fpu_mgmt.
 * - Implements 4-phase level handshaking (exec_req / done_ack) with 2-stage synchronizers
 *   to guarantee safe Clock Domain Crossing (CDC) between ZCLK and MCLK domains.
 * - Routes submodule private SRAM write/read requests up to the top-level SRAM controller.
 ***************************************************************************************/

module zx50_fpu_dispatch (
    input  wire       mclk,              // High-Speed Coprocessor Clock (20MHz / 40MHz)
    input  wire       reset_n,           // Global System Reset (Active LOW)
    input  wire       exec_req,          // Level request signal from ZCLK domain
    input  wire [7:0] opcode,            // Latched command opcode from Port 0x71
    input  wire [7:0] sp_in,             // Current Stack Pointer value from zx50_fpu

    output reg        done_ack,          // Level acknowledge signal to ZCLK domain
    output reg        err_flag,          // Set to 1 if opcode is invalid or unsupported
    output reg  [4:0] status_flags,      // [ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW]
    output wire [7:0] new_sp,            // Updated Stack Pointer output to commit
    output wire       sp_write_en,       // SP write enable flag
    output wire       disp_sram_we_req,  // Engine SRAM write request output
    output wire       disp_sram_oe_req,  // Engine SRAM read output enable request
    output wire [7:0] disp_sram_wdata,   // Engine SRAM write data payload
    output wire [7:0] disp_sram_addr     // Engine SRAM target address
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
    localparam OP_ADD      = 4'h0; // Addition
    localparam OP_SUB      = 4'h1; // Subtraction
    localparam OP_MUL      = 4'h2; // Multiplication
    localparam OP_DIV      = 4'h3; // Division
    localparam OP_SQRT     = 4'h4; // Square Root
    localparam OP_CHS      = 4'h5; // Change Sign
    localparam OP_SIN      = 4'h6; // Sine via Flash LUT
    localparam OP_COS      = 4'h7; // Cosine via Flash LUT
    localparam OP_EXP      = 4'h8; // Exponential via Flash LUT
    localparam OP_LN       = 4'h9; // Natural Log via Flash LUT
    localparam OP_LOG10    = 4'hA; // Base-10 Log via Flash LUT
    localparam OP_LOG_MUL  = 4'hB; // Fast Log-Table Multiply
    localparam OP_LOG_DIV  = 4'hC; // Fast Log-Table Divide

    wire [3:0] fmt = opcode[7:4];
    wire [3:0] op  = opcode[3:0];

    // =========================================================================
    // 2. Internal Output Registers
    // =========================================================================
    reg       sp_write_en_reg;
    reg [7:0] new_sp_reg;

    assign sp_write_en = sp_write_en_reg;
    assign new_sp      = new_sp_reg;

    // =========================================================================
    // 3. Clock Domain Crossing (CDC) Synchronizer for exec_req
    // =========================================================================
    reg [1:0] req_sync;
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) req_sync <= 2'b00;
        else          req_sync <= {req_sync[0], exec_req};
    end
    wire exec_req_mclk = req_sync[1];

    // =========================================================================
    // 4. Submodule Instantiation: Stack Management Engine
    // =========================================================================
    reg  mgmt_start_p;
    wire mgmt_done_p;
    wire mgmt_err;
    wire mgmt_sp_write_en;
    wire [7:0] mgmt_sp_out;

    zx50_fpu_mgmt mgmt_engine (
        .mclk(mclk),
        .reset_n(reset_n),
        .start_p(mgmt_start_p),
        .opcode(opcode),
        .sp_in(sp_in),
        .sp_out(mgmt_sp_out),
        .sp_write_en(mgmt_sp_write_en),
        .mgmt_sram_we_req(disp_sram_we_req),
        .mgmt_sram_oe_req(disp_sram_oe_req),
        .mgmt_sram_wdata(disp_sram_wdata),
        .mgmt_sram_addr(disp_sram_addr),
        .done_p(mgmt_done_p),
        .err_flag(mgmt_err)
    );

    // =========================================================================
    // 5. Dispatch State Machine Logic
    // =========================================================================
    reg [2:0] state;
    localparam ST_IDLE      = 3'd0; // Wait for synchronized exec_req
    localparam ST_DECODE    = 3'd1; // Decode opcode format & operation fields
    localparam ST_MGMT_WAIT = 3'd2; // Wait for management submodule completion
    localparam ST_EXEC      = 3'd3; // Arithmetic / LUT execution phase
    localparam ST_FINISH    = 3'd4; // Assert done_ack level signal

    reg [3:0] exec_cnt; // Cycle counter for execution timing

    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            state           <= ST_IDLE;
            done_ack        <= 1'b0;
            err_flag        <= 1'b0;
            status_flags    <= 5'b00000;
            mgmt_start_p    <= 1'b0;
            exec_cnt        <= 4'd0;
            sp_write_en_reg <= 1'b0;
            new_sp_reg      <= 8'h00;
        end else begin
            mgmt_start_p <= 1'b0;

            case (state)
                ST_IDLE: begin
                    if (exec_req_mclk && !done_ack) begin
                        state           <= ST_DECODE;
                        exec_cnt        <= 4'd0;
                        sp_write_en_reg <= 1'b0;
                    end else if (!exec_req_mclk) begin
                        done_ack        <= 1'b0; // Release ack once ZCLK domain clears request
                        sp_write_en_reg <= 1'b0;
                    end
                end

                ST_DECODE: begin
                    err_flag <= 1'b0;

                    case (fmt)
                        // --- Format 0xF: Stack & Hardware Management ---
                        FMT_MGMT: begin
                            mgmt_start_p <= 1'b1;
                            state        <= ST_MGMT_WAIT;
                        end

                        // --- Formats 0x0 - 0x5: Native & Floating Arithmetic ---
                        FMT_I16, FMT_I32, FMT_I64, FMT_FX1616, FMT_DFLOAT, FMT_CFLOAT: begin
                            case (op)
                                OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_SQRT, OP_CHS,
                                OP_SIN, OP_COS, OP_EXP, OP_LN, OP_LOG10, OP_LOG_MUL, OP_LOG_DIV: begin
                                    state <= ST_EXEC;
                                end
                                default: begin
                                    err_flag <= 1'b1; // Unmapped operation
                                    state    <= ST_FINISH;
                                end
                            endcase
                        end

                        // --- Format 0xE: Custom Extensions ---
                        FMT_SPECIAL: begin
                            state <= ST_EXEC;
                        end

                        default: begin
                            err_flag <= 1'b1; // Unmapped format
                            state    <= ST_FINISH;
                        end
                    endcase
                end

                ST_MGMT_WAIT: begin
                    if (mgmt_done_p) begin
                        err_flag        <= mgmt_err;
                        sp_write_en_reg <= mgmt_sp_write_en;
                        new_sp_reg      <= mgmt_sp_out;
                        state           <= ST_FINISH;
                    end
                end

                ST_EXEC: begin
                    // Simulated execution cycle stub
                    if (exec_cnt == 4'd4) begin
                        exec_cnt <= 4'd0;
                        state    <= ST_FINISH;
                    end else begin
                        exec_cnt <= exec_cnt + 1'b1;
                    end
                end

                ST_FINISH: begin
                    done_ack <= 1'b1; // Assert CDC level acknowledge
                    if (!exec_req_mclk) begin
                        done_ack        <= 1'b0; // Release ack once host clears request
                        sp_write_en_reg <= 1'b0;
                        state           <= ST_IDLE;
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
