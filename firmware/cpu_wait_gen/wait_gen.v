`timescale 1ns/1ps

// ============================================================================
// Behavioral Z80 CPU Model (Master ZCLK Driven)
// ============================================================================
module z80_cpu_model (
    input  wire zclk,       // Master Z80 Clock
    input  wire reset_n,    // Active-low Reset
    input  wire wait_n,     // Active-low ~WAIT input from bus
    output reg  m1_n,       // Active-low ~M1 output pin
    output reg [7:0] t_state// Diagnostic State Output
);

    // T-State Encodings
    localparam M1_T1 = 8'h11, M1_T2 = 8'h12, M1_TW = 8'h10, M1_T3 = 8'h13, M1_T4 = 8'h14;
    localparam M2_T1 = 8'h21, M2_T2 = 8'h22, M2_T3 = 8'h23;
    localparam M3_T1 = 8'h31, M3_T2 = 8'h32, M3_T3 = 8'h33, M3_T4 = 8'h34, M3_T5 = 8'h35;

    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) begin
            t_state <= M1_T1;
            m1_n    <= 1'b1;
        end else begin
            case (t_state)
                // --- M1 Opcode Fetch (4 T-States + TW) ---
                M1_T1: begin
                    m1_n    <= 1'b0;        // ~M1 asserts Low at T1
                    t_state <= M1_T2;
                end
                M1_T2: begin
                    m1_n <= 1'b0;
                    if (!wait_n)
                        t_state <= M1_TW;   // Freeze in TW if ~WAIT is Low
                    else
                        t_state <= M1_T3;
                end
                M1_TW: begin
                    m1_n <= 1'b0;           // ~M1 FROZEN LOW DURING WAIT STATE!
                    if (!wait_n)
                        t_state <= M1_TW;   // Stay in TW while ~WAIT is Low
                    else
                        t_state <= M1_T3;   // Resume to T3 when ~WAIT releases
                end
                M1_T3: begin
                    m1_n    <= 1'b1;        // ~M1 de-asserts High at T3
                    t_state <= M1_T4;
                end
                M1_T4: begin
                    m1_n    <= 1'b1;
                    t_state <= M2_T1;
                end

                // --- M2 Memory Read (3 T-States) ---
                M2_T1: t_state <= M2_T2;
                M2_T2: t_state <= M2_T3;
                M2_T3: t_state <= M3_T1;

                // --- M3 Execution (5 T-States) ---
                M3_T1: t_state <= M3_T2;
                M3_T2: t_state <= M3_T3;
                M3_T3: t_state <= M3_T4;
                M3_T4: t_state <= M3_T5;
                M3_T5: t_state <= M1_T1;    // Loop back to next instruction M1

                default: t_state <= M1_T1;
            endcase
        end
    end

endmodule


`timescale 1ns/1ps

// ============================================================================
// Single-Step Gate Hardware (U9: 74AHCT74 + U10: 74AHCT132)
// ============================================================================
module wait_gen (
    input  wire run,        // 1 = Single-Step Mode Enabled, 0 = Free-Run
    input  wire step_n,     // Step Button (Active-Low)
    input  wire m1_n,       // Active-Low Z80 ~M1 Pin
    output wire wait_gate   // 1 = Drives Q2 FET to pull ~WAIT Low (HALT)
);

    wire u10_1y;     // U10 Pin 3  (1Y)  -> U9 Pin 3  (1CLK)
    wire u10_2y;     // U10 Pin 6  (2Y)  -> U10 Pins 9&10 (3A, 3B)
    wire ff2_clr_n;  // U10 Pin 8  (3Y)  -> U9 Pin 13 (2~CLR)
    wire ff1_clr_n;  // U10 Pin 11 (4Y)  -> U9 Pin 1  (1~CLR)

    wire u9_1q_n;    // U9 Pin 6   (1~Q) -> U10 Pin 4 (2A)
    wire u9_2q_n;    // U9 Pin 8   (2~Q) -> U10 Pin 13 (4B)
    wire u9_1q;      // U9 Pin 5   (1Q)  -> NC

    // U10: 74AHCT132 (Quad NAND Schmitt-Trigger)
    sn74ahct132 u10 (
        .a1(step_n),    .b1(step_n),    .y1(u10_1y),   // Gate 1: Inverter ~STEP -> 1CLK
        .a2(u9_1q_n),   .b2(run),       .y2(u10_2y),   // Gate 2: NAND(1~Q, RUN)
        .a3(u10_2y),    .b3(u10_2y),    .y3(ff2_clr_n),// Gate 3: Inverter Gate 2 -> 2~CLR (RUN & 1~Q)
        .a4(m1_n),      .b4(u9_2q_n),   .y4(ff1_clr_n) // Gate 4: NAND(~M1, 2~Q) -> 1~CLR
    );

    // U9: SN74AHCT74 (Dual D Flip-Flop)
    sn74ahct74 u9 (
        .clr1_n(ff1_clr_n), .d1(1'b1), .clk1(u10_1y), .pre1_n(1'b1), .q1(u9_1q), .q1_n(u9_1q_n),
        .clr2_n(ff2_clr_n), .d2(1'b1), .clk2(m1_n),   .pre2_n(1'b1), .q2(wait_gate), .q2_n(u9_2q_n)
    );

endmodule


// ============================================================================
// Chip Behavioral Models
// ============================================================================
module sn74ahct74 (
    input wire clr1_n, d1, clk1, pre1_n, output reg q1, q1_n,
    input wire clr2_n, d2, clk2, pre2_n, output reg q2, q2_n
);
    always @(posedge clk1 or negedge clr1_n or negedge pre1_n) begin
        if (!clr1_n && !pre1_n)      begin q1 <= 1'b1; q1_n <= 1'b1; end
        else if (!clr1_n)            begin q1 <= 1'b0; q1_n <= 1'b1; end
        else if (!pre1_n)            begin q1 <= 1'b1; q1_n <= 1'b0; end
        else                         begin q1 <= d1;   q1_n <= ~d1;  end
    end

    always @(posedge clk2 or negedge clr2_n or negedge pre2_n) begin
        if (!clr2_n && !pre2_n)      begin q2 <= 1'b1; q2_n <= 1'b1; end
        else if (!clr2_n)            begin q2 <= 1'b0; q2_n <= 1'b1; end
        else if (!pre2_n)            begin q2 <= 1'b1; q2_n <= 1'b0; end
        else                         begin q2 <= d2;   q2_n <= ~d2;  end
    end
endmodule

module sn74ahct132 (
    input wire a1, b1, output wire y1,
    input wire a2, b2, output wire y2,
    input wire a3, b3, output wire y3,
    input wire a4, b4, output wire y4
);
    assign y1 = ~(a1 & b1);
    assign y2 = ~(a2 & b2);
    assign y3 = ~(a3 & b3);
    assign y4 = ~(a4 & b4);
endmodule