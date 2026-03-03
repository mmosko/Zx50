module arbiter_exhaustive_tb;
    reg mclk, reset_n;
    
    // The 5-bit counter that will drive our inputs
    reg [4:0] test_vector; 
    
    // Wire the counter bits directly to the arbiter inputs
    wire mreq_n     = test_vector[0];
    wire iorq_n     = test_vector[1];
    wire mmu_active = test_vector[2];
    wire s_en_n     = test_vector[3];
    wire shd_active = test_vector[4];

    // Derived hits
    wire z80_hit = (!mreq_n || !iorq_n) && mmu_active;
    wire shd_hit = !s_en_n && shd_active;

    // Outputs from the Arbiter
    wire z80_oe_n, shd_oe_n, wait_n, s_busy_n;

    // ... (Instantiate your Arbiter here) ...

    initial begin
        mclk = 0;
        reset_n = 0;
        test_vector = 5'b11010; // Start in idle
        #100 reset_n = 1;
    end
    always #10 mclk = ~mclk;

    // Walk the counter every few clocks to let the state machine settle
    always @(posedge mclk) begin
        if (reset_n) test_vector <= test_vector + 1'b1;
    end

    // --- INVARIANT ASSERTIONS (The "Proptest") ---
    // These run on every single clock cycle. If they fail, the simulation halts.
    always @(posedge mclk) begin
        if (reset_n) begin
            // 1. Mutual Exclusion
            if (z80_oe_n == 0 && shd_oe_n == 0) begin
                $display("FATAL: Transceiver Short Circuit!");
                $fatal(1); 
            end

            // 2. Z80 Wait Safety
            if (z80_hit && (z80_oe_n != 0) && (wait_n != 0)) begin
                $display("FATAL: Z80 accessed unbuffered memory without a WAIT state!");
                $fatal(1);
            end

            // 3. Shadow Busy Safety
            if (shd_hit && (shd_oe_n != 0) && (s_busy_n != 0)) begin
                $display("FATAL: Shadow bus accessed unbuffered memory without S_BUSY!");
                $fatal(1);
            end
        end
    end
endmodule