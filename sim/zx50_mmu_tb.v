`timescale 1ns/1ps

module zx50_mmu_tb;
    // Bus Signals
    reg [15:0] addr;
    reg [7:0] d_bus;
    reg iorq_n, wr_n, mreq_n;
    reg boot_a, boot_b;
    reg [3:0] id_sw_a, id_sw_b;
    reg reset_n;

    // Output Monitoring
    wire [7:0] p_hi_a, p_hi_b;
    wire active_a, active_b;

    // Instance 1: Card A (Boot Card, ID 0)
    zx50_mmu card_a (
        .addr(addr), .d_bus(d_bus), .card_id_sw(id_sw_a),
        .iorq_n(iorq_n), .wr_n(wr_n), .mreq_n(mreq_n), .reset_n(reset_n),
        .boot_en_n(boot_a), .p_addr_hi(p_hi_a), .active(active_a)
    );

    // Instance 2: Card B (Secondary Card, ID 1)
    zx50_mmu card_b (
        .addr(addr), .d_bus(d_bus), .card_id_sw(id_sw_b),
        .iorq_n(iorq_n), .wr_n(wr_n), .mreq_n(mreq_n), .reset_n(reset_n),
        .boot_en_n(boot_b), .p_addr_hi(p_hi_b), .active(active_b)
    );

    integer i;
    reg failed;

    initial begin
        $dumpfile("waves/zx50_mmu.vcd");
        $dumpvars(0, zx50_mmu_tb);
        
        // --- INITIALIZATION ---
        failed = 0;
        id_sw_a = 4'h0; id_sw_b = 4'h1;

        reset_n = 1; 
        iorq_n = 1;     wr_n = 1;    mreq_n = 1;
        boot_a = 0; boot_b = 1; // Set jumpers BEFORE reset
        addr = 16'h0000; d_bus = 8'h00;

        #10;
        reset_n = 0; // Assert Reset
        #50;
        reset_n = 1; // Release Reset
        #10;

        $display("--- Reset complete. Starting tests. ---");

        #100;

        // --- TEST 1: GATING CHECK (MREQ_N IS HIGH) ---
        // Address points to a valid boot page (0x8000), but MREQ is high.
        // Active must remain LOW.
        addr = 16'h8000; 
        #100;
        if (active_a !== 1'b0) begin
            $display("FAIL: active_a is high while mreq_n is high! Gating failed.");
            failed = 1;
        end

        // --- TEST 2: VALID MEMORY READ (WITH 70NS SETUP) ---
        $display("--- Simulating Z80 Memory Read (70ns TAS) ---");
        addr = 16'h8000;    // 1. Assert Address
        #70;                // 2. Wait for Setup Delay
        mreq_n = 0;         // 3. Assert MREQ_N
        #100;
        if (active_a !== 1'b1) begin
            $display("FAIL: active_a failed to trigger during valid MREQ.");
            failed = 1;
        end
        mreq_n = 1;         // 4. End Cycle
        #20;
        if (active_a !== 1'b0) begin
            $display("FAIL: active_a stayed high after MREQ_N ended.");
            failed = 1;
        end

        // --- TEST 3: DISTRIBUTED HANDOVER & SNOOP ---
        $display("--- Testing Handover: Card B takes Page 0 ---");
        // IO Write to Port 0x31, Page 0, Data 0xEE
        addr = 16'h0031; d_bus = 8'hEE;
        #20; iorq_n = 0; wr_n = 0;
        #100; iorq_n = 1; wr_n = 1; // Handover triggers on rising edge
        
        #50;
        // Verify Card B is configured but silent (mreq_n=1)
        addr = 16'h0000;
        #70;
        if (active_b !== 1'b0) begin
            $display("FAIL: Card B is active for Page 0 without MREQ_N.");
            failed = 1;
        end
        
        mreq_n = 0; // Trigger Card B
        #50;
        if (active_b === 1'b1 && p_hi_b === 8'hEE) begin
            $display("PASS: Card B successfully took over and is gated by MREQ_N.");
        end else begin
            $display("FAIL: Card B handover check failed.");
            failed = 1;
        end
        mreq_n = 1;

        // --- FINAL SUMMARY ---
        if (!failed) $display("****** ALL Zx50 MMU TESTS PASSED ******");
        else $display("!!!!!! TESTS FAILED !!!!!!");
        
        #100;
        $finish;
    end
endmodule