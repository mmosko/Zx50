`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_z_memory_test_tb
 * =====================================================================================
 * WHAT IT IS TESTING:
 * An exhaustive 1 Megabyte Memory validation test for the Zx50 Memory Card.
 * This simulates writing to and reading from every single addressable byte across the 
 * two 512KB physical SRAM chips through the CPLD's dynamic Address Translation Lookaside 
 * (ATL) SRAM.
 *
 * WHY WE ARE TESTING IT:
 * With the move to "Rev 1.0 Clean Hardware", the CPLD no longer has to execute 
 * complex 2KB interleaving hacks. Instead, it provides a full 12-bit physical offset 
 * directly to the memory chips (A0-A11), yielding native 4KB paging boundaries.
 * The upper physical address bit (A19 / atl_data[7]) acts as a clean logical 
 * chip select to toggle between CE0 and CE1.
 * This testbench proves that this translation provides a perfectly contiguous, 
 * alias-free 1MB space.
 *
 * HOW IT WORKS:
 * 1. Boots the zx50_clock and Z80 BFM.
 * 2. Iterates through all 256 physical 4KB pages.
 * 3. Programs the MMU (via the BFM) to map each physical page into logical Window 0.
 * 4. Writes a pseudo-random hash byte (derived from the full 20-bit physical address) 
 * to all 4,096 offsets within the page.
 * 5. After writing all 1MB, it iterates through the pages again and reads all 1MB back.
 * 6. Asserts $fatal(1) if any byte read does not match its mathematically expected hash.
 ***************************************************************************************/

module zx50_z_memory_test_tb;

    // --- System Signals ---
    wire mclk, zclk; 
    wire reset_n; 
    
    // --- Clock Generation (Digital Twin) ---
    zx50_clock clk_gen (
        .run_in(1'b1),    // Free run enabled 
        .step_n_in(1'b1), // Not stepping 
        .mclk(mclk), 
        .zclk(zclk) 
    );

    // --- Z80 Backplane Buses (Driven by BFM) ---
    wire [15:0] z80_addr; 
    wire [7:0]  z80_data;
    wire z80_mreq_n, z80_iorq_n, z80_wr_n, z80_rd_n, z80_m1_n; 
    wire z80_wait_n, z80_int_n;

    // --- Shadow Bus Mock ---
    wire [15:0] sh_addr; 
    wire [7:0]  sh_data;
    wire sh_en_n, sh_rw_n, sh_inc_n, sh_stb_n, sh_done_n, sh_busy_n; 

    // Pullups for open-drain/tri-state lines
    assign sh_en_n    = 1'H1;
    assign sh_busy_n  = 1'H1; 
    assign z80_wait_n = 1'H1; 

    // ==========================================
    // The Z80 Bus Master (BFM)
    // ==========================================
    z80_cpu_util z80 (
        .clk(zclk),       // BFM runs on the divided Z80 clock! 
        .reset_n(reset_n),
        .addr(z80_addr),  
        .data(z80_data), 
        .mreq_n(z80_mreq_n),  
        .iorq_n(z80_iorq_n),  
        .rd_n(z80_rd_n),  
        .wr_n(z80_wr_n),  
        .m1_n(z80_m1_n), 
        .wait_n(1'b1)  
    );

    // ==========================================
    // Device Under Test (Memory Card)
    // ==========================================
    zx50_mem_card #(.CARD_ID(4'h1)) UUT (
        .mclk(mclk),      // Memory Card runs on the fast master clock! 
        .zclk(zclk),      // NEW: Memory Card needs ZCLK for backplane synchronization
        .reset_n(reset_n), 
        .z80_a(z80_addr), 
        .z80_d(z80_data), 
        .z80_mreq_n(z80_mreq_n), 
        .z80_iorq_n(z80_iorq_n), 
        .z80_wr_n(z80_wr_n), 
        .z80_rd_n(z80_rd_n), 
        .z80_m1_n(z80_m1_n), 
        .wait_n(z80_wait_n), 
        .int_n(z80_int_n), 
        .sh_data(sh_data), 
        .sh_en_n(sh_en_n), 
        .sh_rw_n(sh_rw_n), 
        .sh_inc_n(sh_inc_n), 
        .sh_stb_n(sh_stb_n), 
        .sh_done_n(sh_done_n), 
        .sh_busy_n(sh_busy_n) 
    );

    // --- Main Test Sequence ---
    integer phys_page; 
    integer offset; 
    reg [19:0] full_phys_addr; 
    reg [7:0]  hash_pattern;
    reg [7:0]  read_val; 

    initial begin
        $display("========================================");
        $display(" ZX50 MEMORY CARD 1MB EXHAUSTIVE TEST"); 
        $display("========================================"); 

        // Boot Sequence
        z80.boot_sequence(); 

        $display("-> CPLD Booted. Commencing 1MB Write Cycle..."); 

        // 1. WRITE CYCLE: 256 physical pages * 4096 bytes
        for (phys_page = 0; phys_page < 256; phys_page = phys_page + 1) begin 
            
            // Use BFM to map physical page to logical Window 0 (0x0000) on Card 1
            z80.mmu_map_page(4'h1, 4'h0, phys_page);
            
            for (offset = 0; offset < 4096; offset = offset + 1) begin 
                // Construct the true 20-bit physical address mathematically
                full_phys_addr = (phys_page << 12) | offset; 
                
                // Deterministic pseudo-random pattern based on absolute address
                hash_pattern = (full_phys_addr ^ (full_phys_addr >> 8) ^ (full_phys_addr >> 16)) & 8'hFF;
                
                // Use BFM to write the hash to the logical offset (0x0000 - 0x0FFF)
                z80.mem_write(offset, hash_pattern);
            end 
            
            // Display Progress
            if (phys_page % 32 == 0) $display("   ... Wrote %0d / 256 pages", phys_page);
        end 

        $display("-> Write Complete. Commencing 1MB Verification Cycle...");
        
        // 2. READ/VERIFY CYCLE
        for (phys_page = 0; phys_page < 256; phys_page = phys_page + 1) begin 
            
            // Remap the physical page back to logical Window 0
            z80.mmu_map_page(4'h1, 4'h0, phys_page);
            
            for (offset = 0; offset < 4096; offset = offset + 1) begin 
                // Reconstruct the 20-bit address and expected hash
                full_phys_addr = (phys_page << 12) | offset; 
                hash_pattern = (full_phys_addr ^ (full_phys_addr >> 8) ^ (full_phys_addr >> 16)) & 8'hFF;
                
                // Use BFM to read the value back from the logical offset
                z80.mem_read(offset, read_val);
                
                if (read_val !== hash_pattern) begin 
                    $display("FATAL: Aliasing or Write Error at Phys Page %0x, Offset %04X.", phys_page, offset);
                    $display("Expected Hash: %02X, Got: %02X", hash_pattern, read_val);
                    $fatal(1); 
                end 
            end
            
            // Read Progress Indicator
            if (phys_page % 32 == 0) $display("   ... Read %0d / 256 pages", phys_page);
        end 

        $display("========================================"); 
        $display(" SUCCESS! 1MB RAM verified with 0 Aliasing Errors."); 
        $display("========================================");
        $finish; 
    end

    // --- System Watchdog Timer ---
    initial begin
        #700000000;
        $display("FATAL [%0t]: Watchdog Timer Expired! Testbench deadlock detected.", $time);  
        $fatal(1); 
    end

endmodule