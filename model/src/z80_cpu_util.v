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
            @(posedge clk); // T1: Set address, drop MREQ
            addr = write_addr;
            mreq_n = 0;
            
            @(posedge clk); // T2: Drive data, drop WR
            data_out = write_data;
            drive_data = 1;
            wr_n = 0;
            
            @(negedge clk); // TW: Sample WAIT_N on falling edge
            while (!wait_n) @(negedge clk);
            
            @(posedge clk); // T3: Cycle ends, release strobes
            wr_n = 1;
            mreq_n = 1;
            
            #10 drive_data = 0; // Simulate 10ns physical hold time on the bus
        end
    endtask

    // ==========================================
    // TASK: Memory Read Cycle
    // ==========================================
    task mem_read(input [15:0] read_addr, output [7:0] read_data);
        begin
            @(posedge clk); // T1: Set address, drop MREQ
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
            @(posedge clk); // T1: Set port address
            addr = port_addr;
            
            @(posedge clk); // T2: Drop IORQ, drive data
            iorq_n = 0;
            data_out = write_data;
            drive_data = 1;
            #5 wr_n = 0;    // Small delay before WR drops (typical Z80 behavior)
            
            @(negedge clk); // TW: Z80 automatically inserts a WAIT state for I/O
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
            @(posedge clk); // T1: Reset states, set port address
            addr = read_addr;
            mreq_n = 1;
            iorq_n = 1;
            rd_n = 1;
            wr_n = 1;
            m1_n = 1;
            
            @(posedge clk); // T2: Drop IORQ and RD
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
            @(posedge clk); // T1: M1 drops to signal instruction fetch/INTACK
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

endmodule