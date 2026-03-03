`timescale 1ns/1ps

module zx50_conflict_tb;
    reg [15:0] addr;
    reg [7:0] d_bus;
    reg iorq_n, wr_n, mreq_n, reset_n;
    reg boot_a, boot_b;
    reg [3:0] id_sw_a, id_sw_b;

    wire [7:0] p_hi_a, p_hi_b;
    wire active_a, active_b;

    // Card A (ID 0)
    zx50_mmu card_a (.addr(addr), .d_bus(d_bus), .card_id_sw(id_sw_a), .iorq_n(iorq_n), .wr_n(wr_n), .mreq_n(mreq_n), .reset_n(reset_n), .boot_en_n(boot_a), .p_addr_hi(p_hi_a), .active(active_a));
    // Card B (ID 1)
    zx50_mmu card_b (.addr(addr), .d_bus(d_bus), .card_id_sw(id_sw_b), .iorq_n(iorq_n), .wr_n(wr_n), .mreq_n(mreq_n), .reset_n(reset_n), .boot_en_n(boot_b), .p_addr_hi(p_hi_b), .active(active_b));

    reg failed;

    initial begin
        $dumpfile("waves/zx50_conflict.vcd");
        $dumpvars(0, zx50_conflict_tb);
        
        failed = 0;
        reset_n = 1; iorq_n = 1; wr_n = 1; mreq_n = 1;
        id_sw_a = 4'h0; id_sw_b = 4'h1;
        boot_a = 0; boot_b = 1; // Card A is the boot card
        
        // 1. Synchronized Power-On Reset
        #10;
         reset_n = 0;
        #50;
         reset_n = 1;
        #10;

        // 2. Test: Verification of initial state (Page 8 / 0x8000)
        addr = 16'h8000; #70; mreq_n = 0; #10;
        if (active_a !== 1'b1 || active_b !== 1'b0) begin
            $display("FAIL: Initial boot state conflict or missing ownership.");
            failed = 1;
        end
        mreq_n = 1; #50;

        // 3. Test: Handover Conflict Resolution
        $display("--- Moving Page 8 from Card A to Card B ---");
        // Write to Card B (Port 0x31) to claim Page 8 (0x08XX)
        addr = 16'h0831; d_bus = 8'hBB; 
        #20; iorq_n = 0; wr_n = 0;
        #100; iorq_n = 1; wr_n = 1; // Rising edge triggers Snoop
        
        // 4. Verification: Card A must have "Stepped Down"
        #50; addr = 16'h8000; #70; mreq_n = 0; #10;
        if (active_a === 1'b1) begin
            $display("FAIL: BUS CONFLICT! Card A failed to release Page 8.");
            failed = 1;
        end
        if (active_b !== 1'b1) begin
            $display("FAIL: Card B failed to claim Page 8.");
            failed = 1;
        end

        if (!failed) $display("****** CONFLICT RESOLUTION PASSED ******");
        else $display("!!!!!! CONFLICT RESOLUTION FAILED !!!!!!");
        $finish;
    end
endmodule