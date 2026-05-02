`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_clock
 * DESCRIPTION:
 * A digital twin of the physical Clock Mezzanine board[cite: 244].
 * Uses a Dual Flip-Flop architecture to allow async starting (so the simulator 
 * doesn't deadlock) but strict synchronous stopping on the falling edge of ZCLK.
 * This physically prevents runt pulses from crashing the Z80.
 ***************************************************************************************/

module zx50_clock (
    input  wire run_in,       // 1 = Free Run, 0 = Stop at end of current ZCLK
    input  wire step_n_in,    // Active Low momentary pulse to step 1 ZCLK
    output wire mclk,         // Gated Master Clock (to Shadow Bus)
    output wire zclk          // Divided Z80 Clock (to CPU)
);

    // --- On-Board Pull-up Resistors ---
    // Simulates physical 10k resistors to +5V on the Mezzanine PCB.
    // If the front panel is disconnected, the system safely defaults to Free-Run.
    pullup(run_in);
    pullup(step_n_in);

    // --- Global Frequency Definitions ---
    // Defined as half-periods in nanoseconds.
    // MCLK = ~36 MHz -> Period = 27.77ns -> Half = 13.88ns [cite: 246]
    parameter MCLK_HALF_PERIOD = 13.88; 

    // --- 1. The Raw Oscillator ---
    // Represents the physical 36MHz canned crystal oscillator on the PCB.
    reg raw_mclk;
    always #MCLK_HALF_PERIOD raw_mclk = ~raw_mclk; // [cite: 248]

    initial begin
        // Explicitly initialize the clock to 0 at simulation start [cite: 247]
        raw_mclk = 0;
    end

    // --- 2. Flip-Flop A: The STEP Synchronizer ---
    // Maps to 1/2 of a physical 74HC74 Dual D-Flip-Flop.
    // - Asynchronously forced HIGH when the STEP button is pressed (~PRE).
    // - Synchronously clocked LOW on the falling edge of ZCLK to end the step cleanly.
    reg step_sync = 0;
    always @(negedge zclk or negedge step_n_in) begin
        if (!step_n_in)
            step_sync <= 1'b1; // Async Preset (Start immediately)
        else
            step_sync <= 1'b0; // Cleared on negedge ZCLK (Stop cleanly)
    end

    // --- 3. Flip-Flop B: The RUN Synchronizer ---
    // Maps to the other 1/2 of the physical 74HC74 Dual D-Flip-Flop.
    // - Asynchronously forced HIGH when the RUN switch is flipped up.
    // - Synchronously clocked LOW on the falling edge of ZCLK when switch is flipped down.
    reg run_sync = 0;
    always @(negedge zclk or posedge run_in) begin
        if (run_in)
            run_sync <= 1'b1;  // Async Preset (Start immediately)
        else
            run_sync <= 1'b0;  // Cleared on negedge ZCLK (Stop cleanly)
    end

    // OR gate (74HC32) combines the two valid run conditions
    wire async_req = step_sync | run_sync;

    // --- 4. The Glitch-Free Clock Gating Register ---
    // This is the industry-standard way to gate clocks safely.
    // It catches the combined async request ONLY when raw_mclk is safely LOW,
    // guaranteeing that the AND gate never chops a clock pulse in half.
    reg mclk_en_safe = 0;
    always @(negedge raw_mclk) begin
        mclk_en_safe <= async_req;
    end

    // The physical 74HC08 AND gate that actually drives the Shadow Bus
    assign mclk = raw_mclk & mclk_en_safe;

    // --- 5. The Divider (74HC4040 Counter) ---
    // Clocks on the falling edge of the gated MCLK, just like physical ripple counters.
    reg [3:0] counter = 0;
    always @(negedge mclk) begin
        counter <= counter + 1'b1;
    end

    // Tap the counter. counter[1] divides by 4 (e.g., 36MHz MCLK -> 9MHz ZCLK)
    assign zclk = counter[1]; 

    // ==========================================
    // Timing Utility Tasks
    // ==========================================
    
    // Usage: clk_gen.wait_mclk(5); [cite: 249]
    task wait_mclk(input integer cycles); // [cite: 250]
        integer i;
        begin
            for (i = 0; i < cycles; i = i + 1) begin
                @(posedge mclk); // [cite: 250]
            end // [cite: 251]
        end
    endtask

    // Usage: clk_gen.wait_zclk(10); [cite: 251]
    task wait_zclk(input integer cycles); // [cite: 252]
        integer i;
        begin
            for (i = 0; i < cycles; i = i + 1) begin
                @(posedge zclk); // [cite: 252]
            end // [cite: 253]
        end
    endtask

endmodule