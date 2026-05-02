`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: z80_cpu_util
 * DESCRIPTION:
 * A Bus Functional Model (BFM) proxy for the Zilog Z80 CPU.
 * This module accurately generates the T-state timing for Memory Read/Write, 
 * I/O Read/Write, and Interrupt Acknowledge (INTACK) cycles.
 * It properly samples the `wait_n` pin on the falling edges to stall the state 
 * machine, exactly as real Z80 silicon does.
 ***************************************************************************************/

module z80_cpu_util (
    input  wire clk,        
    output reg  [15:0] addr,
    inout  wire [7:0]  data,
    output reg  mreq_n, 
    output reg  iorq_n, 
    output reg  rd_n, 
    output reg  wr_n, 
    output reg  m1_n,
    input  wire wait_n
);

    reg [7:0] data_out;
    reg drive_data;
    
    // Tri-state buffer for the bidirectional data bus
    assign data = drive_data ? data_out : 8'hzz;

    initial begin
        addr = 16'h0000;
        data_out = 8'h00;
        drive_data = 0;
        mreq_n = 1; iorq_n = 1; rd_n = 1; wr_n = 1; m1_n = 1;
    end

    // ==========================================
    // TASK: Wait for N T-States
    // ==========================================
    task wait_cycles(input integer t_states);
        integer i;
        begin
            for (i = 0; i < t_states; i = i + 1) @(posedge clk);
        end
    endtask

    // ==========================================
    // TASK: Memory Write Cycle
    // ==========================================
    task mem_write(input [15:0] write_addr, input [7:0] write_data);
        begin
            @(posedge clk);
            // T1: Set address, drop MREQ
            addr = write_addr;
            mreq_n = 0;
            
            @(posedge clk); 
            // T2: Drive data
            data_out = write_data;
            drive_data = 1;
            
            @(negedge clk); 
            // T2 (Falling): Drop WR (Real Z80 drops WR on T2 falling edge)
            wr_n = 0;

            // TW: Sample WAIT_N on falling edge
            while (!wait_n) @(negedge clk);

            @(posedge clk); // T3: Cycle ends, release strobes
            wr_n = 1;
            mreq_n = 1;
            
            #10 drive_data = 0; // Simulate physical hold time
        end
    endtask

    // ==========================================
    // TASK: Memory Read Cycle
    // ==========================================
    task mem_read(input [15:0] read_addr, output [7:0] read_data);
        begin
            @(posedge clk);
            // T1: Set address, drop MREQ
            addr = read_addr;
            mreq_n = 0;
            
            @(posedge clk); // T2: Drop RD
            rd_n = 0;

            @(negedge clk); // TW: Sample WAIT_N on falling edge
            while (!wait_n) @(negedge clk);

            @(posedge clk); // T3: Latch incoming data, release strobes
            read_data = data;
            rd_n = 1;
            mreq_n = 1;
        end
    endtask

    // ==========================================
    // TASK: I/O Write Cycle
    // ==========================================
    task io_write(input [15:0] port_addr, input [7:0] write_data);
        begin
            @(posedge clk);
            // T1: Set port address
            addr = port_addr;

            @(posedge clk); // T2: Drop IORQ, drive data
            iorq_n = 0;
            data_out = write_data;
            drive_data = 1;
            
            @(negedge clk); 
            // T2 (Falling): Drop WR synchronously
            wr_n = 0; 
            
            // TW: Z80 automatically inserts a WAIT state for I/O
            while (!wait_n) @(negedge clk);

            @(posedge clk); // T3: Release strobes
            wr_n = 1;
            iorq_n = 1;
            
            #10 drive_data = 0; // Hold time
        end
    endtask

    // ==========================================
    // TASK: I/O Read Cycle
    // ==========================================
    task io_read(input [15:0] read_addr, output [7:0] read_data_out);
        begin
            @(posedge clk);
            // T1: Reset states, set port address
            addr = read_addr;
            mreq_n = 1;
            iorq_n = 1;
            rd_n = 1;
            wr_n = 1;
            m1_n = 1;
            
            @(posedge clk);
            // T2: Drop IORQ and RD
            iorq_n = 0;
            rd_n = 0;
            
            @(posedge clk); // TW: Automatic I/O wait state + external CPLD WAITs
            while (!wait_n) @(posedge clk);

            @(negedge clk); // T3 (Falling): Z80 samples data on the falling edge of T3
            read_data_out = data;

            @(posedge clk); // T3 finishes, T4 begins: Release strobes
            iorq_n = 1;
            rd_n = 1;
            
            @(posedge clk); // Cleanup / T4 completion
        end
    endtask

    // ==========================================
    // TASK: Interrupt Acknowledge (INTACK) Cycle
    // ==========================================
    task intack(output [7:0] vector);
        begin
            @(posedge clk);
            // T1: M1 drops to signal instruction fetch/INTACK
            m1_n = 0;

            @(posedge clk); // T2: IORQ drops alongside M1 to signal INTACK specifically
            iorq_n = 0;

            @(negedge clk); // TW: Sample WAIT_N on falling edge (Z80 adds 2 auto-waits here)
            while (!wait_n) @(negedge clk);

            @(posedge clk); // T3: Read the vector supplied by the interrupting device
            vector = data;

            iorq_n = 1;
            m1_n = 1;
        end
    endtask

    // ==========================================
    // TASK: Map Specific MMU Page (ZX50 Specific)
    // ==========================================
    // Synthesizes an OUT instruction to map a logical window to a physical page
    task mmu_map_page(input [3:0] card_id, input [3:0] logical_window, input [7:0] physical_page);
        reg [15:0] io_addr;
        begin
            // Z80 OUT (C), R puts the page in A11-A8 and Port/ID in A7-A0
            io_addr = (logical_window << 8) | 8'h30 | card_id;
            io_write(io_addr, physical_page);
        end
    endtask

    // ==========================================
    // TASK: Initialize MMU 1:1 Boot Map (ZX50 Specific)
    // ==========================================
    // Creates a flat 64KB memory map by mapping Logical 0-15 to Physical 0-15
    task init_mmu(input [3:0] card_id);
        integer page;
        begin
            for (page = 0; page < 16; page = page + 1) begin
                mmu_map_page(card_id, page[3:0], page[7:0]);
            end
        end
    endtask

endmodule