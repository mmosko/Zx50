`timescale 1ns/1ps

module zx50_clock_tb;

    reg run_in;
    reg step_n_in;
    wire mclk;
    wire zclk;

    // --- Pulse Counters & Snapshot Variables ---
    // Declared at the module level to satisfy standard Verilog strictness
    integer mclk_count = 0;
    integer zclk_count = 0;
    integer final_zclk_count = 0;
    integer final_mclk_count = 0;

    always @(posedge mclk) mclk_count = mclk_count + 1;
    always @(posedge zclk) zclk_count = zclk_count + 1;

    // Instantiate the Digital Twin
    zx50_clock uut (
        .run_in(run_in),
        .step_n_in(step_n_in),
        .mclk(mclk),
        .zclk(zclk)
    );

    initial begin
        $dumpfile("waves/zx50_clock.vcd");
        $dumpvars(0, zx50_clock_tb);

        // STARTUP: System powered on, but RUN switch is off.
        run_in = 0;
        step_n_in = 1;
        #100;

        // ==========================================
        // TEST 1: The Burst Step
        // ==========================================
        $display("[%0t] TEST 1: Initiating Burst Step...", $time);
        
        // Reset counters for the test
        mclk_count = 0;
        zclk_count = 0;
        
        step_n_in = 0;
        #25; // Hold button briefly
        step_n_in = 1; // Release button
        
        // Wait enough time for the single ZCLK cycle to finish
        // (4 * 27.76ns = ~111ns)
        #300; 

        $display("[%0t] TEST 1 Results: ZCLK = %0d, MCLK = %0d", $time, zclk_count, mclk_count);
        
        if (zclk_count !== 1) begin
            $display("FATAL: Expected exactly 1 ZCLK pulse, got %0d", zclk_count);
            $fatal(1);
        end
        if (mclk_count !== 4) begin
            $display("FATAL: Expected exactly 4 MCLK pulses, got %0d", mclk_count);
            $fatal(1);
        end
        $display("[%0t] TEST 1 PASS.", $time);


        // ==========================================
        // TEST 2: Free Run and Clean Halt
        // ==========================================
        $display("\n[%0t] TEST 2: Initiating Free Run...", $time);
        
        mclk_count = 0;
        zclk_count = 0;
        run_in = 1;
        
        // Let it run for exactly 10 ZCLK cycles
        repeat(10) @(posedge zclk);
        
        // Wait 30ns to ensure we are right in the middle of the 11th ZCLK cycle
        #30; 
        
        $display("[%0t] TEST 2: Dropping RUN switch mid-cycle...", $time);
        run_in = 0;
        
        // Wait enough time for the clock to cleanly halt at the end of its cycle
        #200; 

        // Snapshot the counters using the pre-declared variables
        final_zclk_count = zclk_count;
        final_mclk_count = mclk_count;
        
        // Wait a bit more to prove the clocks are truly dead
        #200; 
        
        $display("[%0t] TEST 2 Results: ZCLK = %0d, MCLK = %0d", $time, final_zclk_count, final_mclk_count);

        if (zclk_count !== final_zclk_count || mclk_count !== final_mclk_count) begin
            $display("FATAL: Clocks did not halt! Counters are still incrementing.");
            $fatal(1);
        end

        // The ultimate test of the clean halt: The ratio must remain perfectly 4:1
        if (final_mclk_count !== (final_zclk_count * 4)) begin
            $display("FATAL: Asymmetrical halt detected! MCLK (%0d) is not a perfect multiple of ZCLK (%0d). Runt pulse generated.", final_mclk_count, final_zclk_count);
            $fatal(1);
        end
        
        $display("[%0t] TEST 2 PASS. Clean halt verified.", $time);

        // ==========================================
        $display("\n[%0t] All Clock Mezzanine tests completed successfully.", $time);
        $finish;
    end


    // --- System Watchdog Timer ---
    initial begin
        #500000; 
        $display("FATAL [%0t]: Watchdog Timer Expired!", $time);
        $fatal(1);
    end
    
endmodule