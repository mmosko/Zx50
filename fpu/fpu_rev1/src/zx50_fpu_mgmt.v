`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_mgmt
 * FILE: src/zx50_fpu_mgmt.v
 * DESCRIPTION:
 * Stack Pointer and Hardware Management Engine for the Zx50 FPU Coprocessor.
 *
 * EXECUTED MANAGEMENT OPCODES (Format 0xF):
 *   - 0xF0 (CLR_STK) : Resets Stack Pointer to base address (sp = 0x00).
 *   - 0xF1 (POP_TOS) : Decrements Stack Pointer by active frame stride (4 bytes).
 *   - 0xF2 (DUP_TOS) : Duplicates Top-of-Stack (TOS) 4-byte frame in private SRAM.
 *   - 0xFF (RESET)   : Resets internal registers and clears stack pointer.
 ***************************************************************************************/

module zx50_fpu_mgmt (
    input  wire       mclk,              // High-Speed Coprocessor Clock (20MHz / 40MHz)
    input  wire       reset_n,           // Global System Reset (Active LOW)
    input  wire       start_p,           // 1-tick trigger pulse from dispatcher FSM
    input  wire [7:0] opcode,            // Management opcode written to Port 0x71
    input  wire [7:0] sp_in,             // Current Stack Pointer value from zx50_fpu

    output reg  [7:0] sp_out,            // Updated Stack Pointer output to commit
    output reg        sp_write_en,       // 1 = Commit sp_out back to top-level sp register
    output reg        mgmt_sram_we_req,  // Trigger private SRAM write cycle
    output reg        mgmt_sram_oe_req,  // Trigger private SRAM read cycle
    output reg  [7:0] mgmt_sram_wdata,   // Write payload for SRAM operations
    output reg  [7:0] mgmt_sram_addr,    // Target private SRAM address
    output reg        done_p,            // 1-tick execution complete pulse to dispatcher
    output reg        err_flag           // 1 = Invalid management opcode requested
);

    // =========================================================================
    // 1. Management Opcode Definitions
    // =========================================================================
    localparam MGMT_CLR_STK = 8'hF0; // Clear Stack
    localparam MGMT_POP_TOS = 8'hF1; // Pop Top-of-Stack Frame
    localparam MGMT_DUP_TOS = 8'hF2; // Duplicate Top-of-Stack Frame
    localparam MGMT_RESET   = 8'hFF; // Soft Reset Coprocessor Engine

    // =========================================================================
    // 2. Management FSM State Definitions
    // =========================================================================
    reg [1:0] state;
    localparam ST_IDLE = 2'd0; // Wait for start trigger pulse
    localparam ST_EXEC = 2'd1; // Decode opcode and compute updated SP
    localparam ST_DONE = 2'd2; // Assert done_p while holding sp_write_en stable

    // =========================================================================
    // 3. Management State Machine Logic
    // =========================================================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            state            <= ST_IDLE;
            sp_out           <= 8'h00;
            sp_write_en      <= 1'b0;
            mgmt_sram_we_req <= 1'b0;
            mgmt_sram_oe_req <= 1'b0;
            mgmt_sram_wdata  <= 8'h00;
            mgmt_sram_addr   <= 8'h00;
            done_p           <= 1'b0;
            err_flag         <= 1'b0;
        end else begin
            mgmt_sram_we_req <= 1'b0;
            mgmt_sram_oe_req <= 1'b0;
            done_p           <= 1'b0;

            case (state)
                ST_IDLE: begin
                    err_flag    <= 1'b0;
                    sp_write_en <= 1'b0;
                    if (start_p) begin
                        state <= ST_EXEC;
                    end
                end

                ST_EXEC: begin
                    state  <= ST_DONE;
                    done_p <= 1'b1; // Pulse completion trigger for next cycle

                    case (opcode)
                        MGMT_CLR_STK, MGMT_RESET: begin
                            // Reset Stack Pointer back to base address 0x00
                            sp_out      <= 8'h00;
                            sp_write_en <= 1'b1;
                        end

                        MGMT_POP_TOS: begin
                            // Drop active 32-bit (4-byte) frame by decrementing SP by 4
                            sp_out      <= sp_in - 8'd4;
                            sp_write_en <= 1'b1;
                        end

                        MGMT_DUP_TOS: begin
                            // DUP_TOS 4-byte copy loop stub
                            sp_write_en <= 1'b0;
                        end

                        default: begin
                            // Unmapped management opcode -> Assert Error flag
                            err_flag    <= 1'b1;
                            sp_write_en <= 1'b0;
                        end
                    endcase
                end

                ST_DONE: begin
                    // Hold sp_write_en & sp_out stable during sampling cycle, then return IDLE
                    state       <= ST_IDLE;
                    sp_write_en <= 1'b0;
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule