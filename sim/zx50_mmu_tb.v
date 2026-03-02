`timescale 1ns/1ps

module zx50_mmu_tb;
    reg [15:0] addr;
    reg [7:0] d_bus;
    reg iorq_n, wr_n, boot_a, boot_b;
    
    wire [7:0] p_hi_a, p_hi_b;
    wire active_a, active_b;

    // Instance 1: Card A (Port 0x30)
    zx50_mmu #(.MY_CARD_ID(8'h30)) card_a (
        .addr(addr), .d_bus(d_bus), .iorq_n(iorq_n), .wr_n(wr_n),
        .boot_en_n(boot_a), .p_addr_hi(p_hi_a), .active(active_a)
    );

    // Instance 2: Card B (Port 0x31)
    zx50_mmu #(.MY_CARD_ID(8'h31)) card_b (
        .addr(addr), .d_bus(d_bus), .iorq_n(iorq_n), .wr_n(wr_n),
        .boot_en_n(boot_b), .p_addr_hi(p_hi_b), .active(active_b)
    );

    initial begin
        $dumpfile("waves/zx50_mmu_sim.vcd");
        $dumpvars(0, zx50_mmu_tb);

        // SETUP: Card A is the boot card, Card B is not
        boot_a = 0; boot_b = 1;
        iorq_n = 1; wr_n = 1; addr = 0; d_bus = 0;
        #100;

        // TEST 1: Check Page 8 (0x8000). Card A should be active, Bank should be 0x08.
        addr = 16'h8000;
        #50; 

        // TEST 2: Z80 writes to Port 0x31 (Card B). Map Page 8 to Physical Bank 0xEE.
        // This should cause Card A to go INACTIVE for Page 8.
        addr = 16'h0831; d_bus = 8'hEE;
        #20; iorq_n = 0; wr_n = 0;
        #100; iorq_n = 1; wr_n = 1; // Rising edge triggers snoop
        
        // TEST 3: Return to Page 8 (0x8000). Now Card B should be active.
        #50; addr = 16'h8000;
        #100;
        
        $display("Simulation Complete. Check GTKWave for active_a vs active_b.");
        $finish;
    end
endmodule
