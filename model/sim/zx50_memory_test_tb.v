`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_memory_test_tb
 * * WHAT IT IS TESTING:
 * An exhaustive 1 Megabyte Memory Striping and Paging test for the Zx50 Memory Card.
 * This simulates writing to and reading from every single addressable byte across the 
 * two 512KB physical SRAM chips through the CPLD's dynamic Address Translation Lookaside 
 * (ATL) SRAM.
 * * WHY WE ARE TESTING IT:
 * The physical Rev A PCB design routes 11 bits of the Z80 address bus (A0-A10) and 
 * 8 bits of the ATL page table data to the physical SRAM chips. This yields exactly 
 * 19 bits (512KB per chip), leaving the Z80's A11 pin orphaned and leaving zero bits 
 * available for dedicated Chip Select lines. 
 * * To solve this without cutting traces, the CPLD intercepts Z80 A11 and uses it to 
 * dynamically toggle between CE0 and CE1. As a result, every 4KB logical page 
 * (defined by A15:A12) is actually physically striped across both SRAM chips in 
 * interleaved 2KB blocks. This testbench exists to prove that this non-standard 
 * hardware RAID-0 style striping provides a perfectly contiguous, alias-free 1MB space.
 * * HOW IT WORKS:
 * 1. Boots the CPLD and waits for the MMU's auto-wipe initialization to finish.
 * 2. Iterates through all 256 physical 4KB pages.
 * 3. Programs the MMU (via I/O port 0x30) to map each physical page into logical 
 * Window 0 (0x0000 - 0x0FFF).
 * 4. Writes a pseudo-random hash byte (derived from the full 20-bit physical address) 
 * to all 4,096 offsets.
 * 5. After writing all 1MB, it remaps the pages and reads all 1MB back.
 * 6. Asserts $fatal(1) if any byte read does not match its expected hash, instantly 
 * failing the Makefile.
 ***************************************************************************************/
 
module zx50_memory_test_tb;

    // --- System Signals ---
    reg mclk;
    reg reset_n;
    reg [3:0] card_id_sw;

    // --- Z80 Bus Mock ---
    reg [15:0] z80_addr;
    reg [7:0]  z80_data_out;
    wire [7:0] z80_data;
    reg        z80_drive_data; // 1 = TB drives bus, 0 = High-Z (Read)
    
    reg z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n;
    reg z80_m1_n, z80_iei;
    
    wire z80_wait_n, z80_ieo, z80_int_n;

    // --- Shadow Bus Mock ---
    wire [15:0] sh_addr;
    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n;

    // Tri-state Z80 data bus driver
    assign z80_data = z80_drive_data ? z80_data_out : 8'hzz;

    // Pullups for open-drain/tri-state lines
    assign sh_en_n   = 1'H1;
    assign sh_busy_n = 1'H1;
    assign z80_wait_n = 1'H1;

    // --- Device Under Test ---
    zx50_mem_card UUT (
        .mclk(mclk),
        .reset_n(reset_n),
        .card_id_sw(card_id_sw),
        .z80_addr(z80_addr),
        .z80_data(z80_data),
        .z80_mreq_n(z80_mreq_n),
        .z80_iorq_n(z80_iorq_n),
        .z80_wr_n(z80_wr_n),
        .z80_rd_n(z80_rd_n),
        .z80_m1_n(z80_m1_n),
        .z80_iei(z80_iei),
        .z80_wait_n(z80_wait_n),
        .z80_ieo(z80_ieo),
        .z80_int_n(z80_int_n),
        .sh_addr(sh_addr),
        .sh_data(sh_data),
        .sh_en_n(sh_en_n),
        .sh_rw_n(sh_rw_n),
        .sh_inc_n(sh_inc_n),
        .sh_stb_n(sh_stb_n),
        .sh_done_n(sh_done_n),
        .sh_busy_n(sh_busy_n)
    );

    // --- Clock Generation (40 MHz) ---
    always #12.5 mclk = ~mclk;

    // --- Z80 Bus Cycle Tasks ---
    
    // Map a physical 4KB page (0-255) into a logical Z80 window (0-15)
    task mmu_map_page;
        input [3:0] logical_window;
        input [7:0] physical_page;
        begin
            @(negedge mclk);
            z80_addr       <= {4'h0, logical_window, 8'h30}; // I/O Port 0x30 + offset
            z80_data_out   <= physical_page;
            z80_drive_data <= 1'b1;
            z80_iorq_n     <= 1'b0;
            z80_wr_n       <= 1'b0;
            
            @(negedge mclk);
            @(negedge mclk); // Hold for 2 clocks to satisfy sync_we
            
            z80_iorq_n     <= 1'b1;
            z80_wr_n       <= 1'b1;
            z80_drive_data <= 1'b0;
            @(negedge mclk);
        end
    endtask

    // Write a byte to Z80 memory
    task z80_write_mem;
        input [15:0] addr;
        input [7:0]  data;
        begin
            @(negedge mclk);
            z80_addr       <= addr;
            z80_data_out   <= data;
            z80_drive_data <= 1'b1;
            z80_mreq_n     <= 1'b0;
            z80_wr_n       <= 1'b0;
            
            @(negedge mclk); // Simulate typical Z80 write cycle time
            
            z80_mreq_n     <= 1'b1;
            z80_wr_n       <= 1'b1;
            z80_drive_data <= 1'b0;
            @(negedge mclk);
        end
    endtask

    // Read a byte from Z80 memory and verify
    task z80_read_verify_mem;
        input [15:0] addr;
        input [7:0]  expected_data;
        reg   [7:0]  read_val;
        begin
            @(negedge mclk);
            z80_addr       <= addr;
            z80_drive_data <= 1'b0; // Let the SRAM drive the bus
            z80_mreq_n     <= 1'b0;
            z80_rd_n       <= 1'b0;
            
            @(negedge mclk);
            @(negedge mclk); // Give SRAM time to output
            
            read_val = z80_data;
            
            if (read_val !== expected_data) begin
                // Use $fatal(1) to immediately exit with an error code for the Makefile
                $fatal(1, "FAIL: Aliasing or Write Error at Z80 Addr %04X. Expected %02X, Got %02X", addr, expected_data, read_val);
            end
            
            z80_mreq_n     <= 1'b1;
            z80_rd_n       <= 1'b1;
            @(negedge mclk);
        end
    endtask

    // --- Main Test Sequence ---
    integer phys_page;
    integer offset;
    reg [19:0] full_phys_addr;
    reg [7:0]  hash_pattern;

    initial begin
        $display("========================================");
        $display(" ZX50 MEMORY CARD 1MB EXHAUSTIVE TEST");
        $display("========================================");

        // Initialize signals
        mclk = 0;
        reset_n = 0;
        card_id_sw = 4'h0;
        z80_addr = 16'h0000;
        z80_data_out = 8'h00;
        z80_drive_data = 0;
        z80_mreq_n = 1; z80_iorq_n = 1; z80_wr_n = 1; z80_rd_n = 1;
        z80_m1_n = 1; z80_iei = 1;

        // Hold reset for CPLD to settle
        #100 reset_n = 1;
        
        // Wait for MMU Hardware Auto-Wipe (16 clocks)
        #500; 

        $display("-> CPLD Booted. Commencing 1MB Write Cycle...");

        // 1. WRITE CYCLE: 256 physical pages * 4096 bytes
        for (phys_page = 0; phys_page < 256; phys_page = phys_page + 1) begin
            // Map the physical page into Z80 Window 0 (0x0000 - 0x0FFF)
            mmu_map_page(4'h0, phys_page);
            
            for (offset = 0; offset < 4096; offset = offset + 1) begin
                full_phys_addr = (phys_page << 12) | offset;
                // Generate a deterministic pattern based on the absolute 20-bit address
                hash_pattern = (full_phys_addr ^ (full_phys_addr >> 8) ^ (full_phys_addr >> 16)) & 8'hFF;
                
                z80_write_mem(offset, hash_pattern);
            end
            
            if (phys_page % 32 == 0) $display("   ... Wrote %0d / 256 pages", phys_page);
        end

        $display("-> Write Complete. Commencing 1MB Verification Cycle...");

        // 2. READ/VERIFY CYCLE
        for (phys_page = 0; phys_page < 256; phys_page = phys_page + 1) begin
            // Map the page again
            mmu_map_page(4'h0, phys_page);
            
            for (offset = 0; offset < 4096; offset = offset + 1) begin
                full_phys_addr = (phys_page << 12) | offset;
                hash_pattern = (full_phys_addr ^ (full_phys_addr >> 8) ^ (full_phys_addr >> 16)) & 8'hFF;
                
                z80_read_verify_mem(offset, hash_pattern);
            end
        end

        $display("========================================");
        $display(" SUCCESS! 1MB Striped RAM verified with 0 Aliasing Errors.");
        $display("========================================");
        $finish;
    end

endmodule