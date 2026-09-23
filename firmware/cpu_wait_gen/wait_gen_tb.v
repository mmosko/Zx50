`timescale 1ns/1ps

module wait_gen_tb;
    reg zclk;
    reg reset_n;
    reg run;
    reg step_n;

    wire m1_n;
    wire wait_gate;
    wire wait_n = ~wait_gate; // Open-drain MOSFET pulls ~WAIT Low when wait_gate = 1
    wire [7:0] t_state;

    // Instantiate CPU
    z80_cpu_model cpu (
        .zclk(zclk),
        .reset_n(reset_n),
        .wait_n(wait_n),
        .m1_n(m1_n),
        .t_state(t_state)
    );

    // Instantiate Single-Step Logic
    wait_gen uut (
        .run(run),
        .step_n(step_n),
        .m1_n(m1_n),
        .wait_gate(wait_gate)
    );

    // 4 MHz Master ZCLK Generation (250ns Period: 125ns High, 125ns Low)
    always #125 zclk = ~zclk;

    initial begin
        $dumpfile("wait_gen.vcd");
        $dumpvars(0, wait_gen_tb);

        // Initial State (Buttons released, pull-up resistors High)
        zclk    = 0;
        reset_n = 0;
        run     = 0;
        step_n  = 1; // MUST START HIGH (Active-Low Switch Released)

        #300 reset_n = 1; // Release Reset

        // 1. Let CPU execute 2 full instructions in free-run mode
        #3000;

        // 2. Turn RUN switch ON (Single-Step Mode Armed)
        $display("T=%0t: [System Event] Human turns RUN switch ON", $time);
        #100 run = 1;

        // Observe CPU entering M1_TW state and freezing m1_n LOW
        #3000;

        // 3. Press STEP Button 1 (Held down for 10 ZCLK cycles)
        $display("T=%0t: [System Event] STEP 1: PRESS", $time);
        #40 step_n = 0;
        #2500;

        $display("T=%0t: [System Event] STEP 1: RELEASE", $time);
        step_n = 1;
        #3000; // CPU executes exactly 1 instruction and re-halts in M1_TW

        // 4. Press STEP Button 2
        $display("T=%0t: [System Event] STEP 2: PRESS", $time);
        #50 step_n = 0;
        #2500;

        $display("T=%0t: [System Event] STEP 2: RELEASE", $time);
        step_n = 1;
        #3000;

        // 5. Turn RUN switch OFF (Return to Free-Run)
        $display("T=%0t: [System Event] Human turns RUN switch OFF", $time);
        #30 run = 0;
        #3000;

        $finish;
    end
endmodule