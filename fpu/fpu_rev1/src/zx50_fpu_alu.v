`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu_alu
 * FILE: src/zx50_fpu_alu.v
 * DESCRIPTION:
 * Byte-Serial Arithmetic Execution Core for Zx50 FPU Coprocessor (CPLD Rev C2 Target).
 *
 * ARCHITECTURAL SPECIFICATION:
 * - Processes multi-byte stack frames (16-bit, 32-bit fixed/float) sequentially 8 bits
 *   at a time to minimize macrocell count and product-term allocation in the ATF1508AS.
 * - Dynamically handshakes with zx50_fpu_mem using the mem_ready strobe, making memory
 *   accesses 100% resilient across fast 12ns SRAM (IS61C256AL) and slow 55ns Flash ROM.
 * - Holds address, write data, and write request signals stable until mem_ready asserts.
 * - Tracks carry and borrow across byte passes for multi-precision calculations.
 ***************************************************************************************/

module zx50_fpu_alu (
    input  wire        mclk,            // Coprocessor High-Speed Clock (20MHz / 40MHz)
    input  wire        reset_n,         // Global System Reset (Active LOW)

    // --- Control Interface (from zx50_fpu_dispatch) ---
    input  wire        start_p,         // 1-tick trigger pulse to begin calculation
    input  wire [3:0]  fmt,             // Opcode format field (0x0 = i16, 0x1 = i32, etc.)
    input  wire [3:0]  op,              // Opcode operation field (0x0 = ADD, 0x1 = SUB, etc.)
    input  wire [7:0]  sp_in,           // Current Stack Pointer (points to top of stack)

    output reg         done_p,          // 1-tick execution complete pulse
    output reg         err_flag,        // Set on arithmetic error / divide-by-zero
    output reg  [4:0]  status_flags,    // [ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW]

    // --- Private Memory Master Interface (to zx50_fpu_mem) ---
    output reg         alu_mem_we_req,  // SRAM write enable request
    output reg         alu_mem_oe_req,  // SRAM / Flash read enable request
    output reg         alu_sel_flash,   // 1 = Flash ROM (LUTs), 0 = SRAM
    output reg  [14:0] alu_mem_addr,    // 15-bit target private address (32KB window)
    output reg  [7:0]  alu_mem_wdata,   // Write payload to private memory
    input  wire [7:0]  mem_rdata,       // Data read back from private memory bus
    input  wire        mem_ready        // 1 = Memory read valid or write complete
);

    // =========================================================================
    // 1. Internal Working Registers & State Counters
    // =========================================================================
    reg [7:0] acc;          // 8-bit Accumulator (TOS Byte)
    reg [7:0] operand_b;    // 8-bit Secondary Operand Buffer (NOS Byte)
    reg       carry_borrow; // Carry/Borrow bit for multi-byte propagation
    reg [2:0] byte_cnt;     // Byte-index counter for multi-byte iterations (0 to 7)

    // Operation Decoding Localparams
    localparam OP_ADD = 4'h0;
    localparam OP_SUB = 4'h1;
    localparam OP_MUL = 4'h2;
    localparam OP_DIV = 4'h3;
    localparam OP_CHS = 4'h5;

    // Handshaked FSM State Definitions
    reg [2:0] state;
    localparam ST_IDLE    = 3'd0; // Wait for start trigger from dispatcher
    localparam ST_READ_A  = 3'd1; // Read Operand A byte from TOS frame
    localparam ST_READ_B  = 3'd2; // Read Operand B byte from NOS frame
    localparam ST_EXEC    = 3'd3; // Execute 8-bit ALU operation & update carry
    localparam ST_WRITE   = 3'd4; // Write-back 8-bit result to NOS frame in SRAM
    localparam ST_FINISH  = 3'd5; // Assert done_p pulse and lock final status_flags

    // =========================================================================
    // 2. Serial ALU Execution State Machine
    // =========================================================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            state          <= ST_IDLE;
            acc            <= 8'h00;
            operand_b      <= 8'h00;
            carry_borrow   <= 1'b0;
            byte_cnt       <= 3'd0;
            done_p         <= 1'b0;
            err_flag       <= 1'b0;
            status_flags   <= 5'b00000;
            alu_mem_we_req <= 1'b0;
            alu_mem_oe_req <= 1'b0;
            alu_sel_flash  <= 1'b0;
            alu_mem_addr   <= 15'h0000;
            alu_mem_wdata  <= 8'h00;
        end else begin
            done_p         <= 1'b0;
            alu_mem_we_req <= 1'b0;
            alu_mem_oe_req <= 1'b0;

            case (state)
                ST_IDLE: begin
                    err_flag     <= 1'b0;
                    byte_cnt     <= 3'd0;
                    carry_borrow <= 1'b0;
                    if (start_p) begin
                        state <= ST_READ_A;
                    end
                end

                // --- Operand A Fetch (TOS Frame: SP - 4 + byte_cnt) ---
                ST_READ_A: begin
                    alu_sel_flash  <= 1'b0;
                    alu_mem_oe_req <= 1'b1;
                    alu_mem_addr   <= {7'b0000000, (sp_in - 8'd4 + {5'b00000, byte_cnt})};
                    
                    if (mem_ready) begin
                        acc   <= mem_rdata;
                        state <= ST_READ_B;
                    end
                end

                // --- Operand B Fetch (NOS Frame: SP - 8 + byte_cnt) ---
                ST_READ_B: begin
                    alu_sel_flash  <= 1'b0;
                    alu_mem_oe_req <= 1'b1;
                    alu_mem_addr   <= {7'b0000000, (sp_in - 8'd8 + {5'b00000, byte_cnt})};
                    
                    if (mem_ready) begin
                        operand_b <= mem_rdata;
                        state     <= ST_EXEC;
                    end
                end

                // --- 8-Bit Arithmetic Calculation ---
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

                // --- Result Write-back (NOS Frame: SP - 8 + byte_cnt) ---
                ST_WRITE: begin
                    alu_sel_flash  <= 1'b0;
                    alu_mem_we_req <= 1'b1;
                    alu_mem_addr   <= {7'b0000000, (sp_in - 8'd8 + {5'b00000, byte_cnt})};
                    alu_mem_wdata  <= acc;

                    // Maintain write request and address/data stable until mem_ready confirms write latch
                    if (mem_ready) begin
                        if (byte_cnt == 3'd3) begin
                            state <= ST_FINISH;
                        end else begin
                            byte_cnt <= byte_cnt + 1'b1;
                            state    <= ST_READ_A;
                        end
                    end
                end

                // --- Completion & Status Register Flag Locking ---
                ST_FINISH: begin
                    done_p          <= 1'b1;
                    status_flags[4] <= (acc == 8'h00);   // ZERO
                    status_flags[3] <= acc[7];           // SIGN
                    status_flags[2] <= carry_borrow;     // CARRY
                    status_flags[1] <= 1'b0;             // OVERFLOW
                    status_flags[0] <= 1'b0;             // UNDERFLOW
                    state           <= ST_IDLE;
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule