`timescale 1ns/1ps

/***************************************************************************************
* MODULE: fpu_clock
* DESCRIPTION:
* Clock Generation & Multiplier Module for Zx50 FPU Rev 2 (Lattice MachXO2-2000).
*
* - Multiplies MCLK by x4 to generate high-speed internal core clock FCLK:
*     * 20 MHz MCLK -> 80 MHz FCLK
*     * 40 MHz MCLK -> 160 MHz FCLK
* - Generates gated active-LOW reset (fpu_reset_n) synchronized with PLL lock status.
* - Supports dual-path execution:
*     * SYNTHESIS: Instantiates IPexpress wrapper around MachXO2 EHXPLLJ primitive.
*     * SIMULATION: Pure Verilog 4x frequency generator (Icarus / ModelSim / Riviera).
***************************************************************************************/

module fpu_clock (
    input  wire mclk,          // High-speed coprocessor clock input (20 MHz / 40 MHz)
    input  wire reset_n,       // External active-LOW system reset
    output wire fclk,          // Internal x4 multiplied core clock (80 MHz / 160 MHz)
    output wire pll_lock,      // Direct PLL phase lock status flag (1 = Locked)
    output wire fpu_reset_n    // Gated active-LOW core reset (reset_n & pll_lock)
);

`ifdef SYNTHESIS
    // =========================================================================
    // 1. Lattice MachXO2 Synthesis Path (EHXPLLJ Hard IP via IPexpress)
    // =========================================================================
    wire lock_net;

    // Instantiates Diamond IPexpress PLL module named 'fpu_pll'
    fpu_pll pll_inst (
        .CLKI   (mclk),         // Primary clock input
        .RST    (~reset_n),     // EHXPLLJ reset is active-HIGH
        .CLKOP  (fclk),         // Primary x4 clock output
        .LOCK   (lock_net)      // PLL lock indicator
    );

    assign pll_lock    = lock_net;
    assign fpu_reset_n = reset_n & lock_net;

`else
    // =========================================================================
    // 2. Behavioral Simulation Path (Pure Verilog Testbench Model)
    // =========================================================================
    realtime t_last = 0;
    realtime t_half_period = 0;
    reg      fclk_sim = 1'b0;
    reg      lock_sim = 1'b0;

    // Dynamically measure incoming MCLK period to calculate 4x FCLK half-period
    always @(posedge mclk) begin
        if (t_last > 0) begin
            t_half_period = ($realtime - t_last) / 8.0;
        end
        t_last = $realtime;
    end

    // Simulate PLL acquiring lock after clock stabilizes
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            lock_sim <= 1'b0;
        end else begin
            if (t_half_period > 0) begin
                lock_sim <= 1'b1;
            end
        end
    end

    // Generate 8 clock toggles per MCLK cycle (4 complete FCLK clock periods)
    always @(mclk) begin
        if (t_half_period > 0) begin
            #t_half_period fclk_sim = ~fclk_sim;
            #t_half_period fclk_sim = ~fclk_sim;
            #t_half_period fclk_sim = ~fclk_sim;
            #t_half_period fclk_sim = ~fclk_sim;
            #t_half_period fclk_sim = ~fclk_sim;
            #t_half_period fclk_sim = ~fclk_sim;
            #t_half_period fclk_sim = ~fclk_sim;
            #t_half_period fclk_sim = ~fclk_sim;
        end
    end

    assign fclk        = (t_half_period > 0) ? fclk_sim : mclk;
    assign pll_lock    = lock_sim;
    assign fpu_reset_n = reset_n & lock_sim;

`endif

endmodule
