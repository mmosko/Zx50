`timescale 1ns/1ps

module z80_cpu_util (
    input  wire clk,        
    output reg  [15:0] addr,
    inout  wire [7:0]  data,
    output reg  mreq_n, iorq_n, rd_n, wr_n, m1_n,
    input  wire wait_n
);
    reg [7:0] data_out;
    reg drive_data;
    
    assign data = drive_data ? data_out : 8'hzz;

    initial begin
        addr = 16'h0000;
        data_out = 8'h00;
        drive_data = 0;
        mreq_n = 1; iorq_n = 1; rd_n = 1; wr_n = 1; m1_n = 1;
    end

    // --- TASK: Wait for N T-States ---
    task wait_cycles(input integer t_states);
        integer i;
        begin
            for (i = 0; i < t_states; i = i + 1) @(posedge clk);
        end
    endtask

    // --- TASK: Memory Write ---
    task mem_write(input [15:0] write_addr, input [7:0] write_data);
        begin
            @(posedge clk); // T1
            addr = write_addr;
            mreq_n = 0;
            
            @(posedge clk); // T2
            data_out = write_data;
            drive_data = 1;
            wr_n = 0;
            
            @(negedge clk); // TW (Wait States)
            while (!wait_n) @(negedge clk);
            
            @(posedge clk); // T3
            wr_n = 1;
            mreq_n = 1;
            
            #10 drive_data = 0; // 10ns physical hold time
        end
    endtask

    // --- TASK: Memory Read ---
    task mem_read(input [15:0] read_addr, output [7:0] read_data);
        begin
            @(posedge clk); // T1
            addr = read_addr;
            mreq_n = 0;
            
            @(posedge clk); // T2
            rd_n = 0;
            
            @(negedge clk); // TW
            while (!wait_n) @(negedge clk);
            
            @(posedge clk); // T3
            read_data = data; 
            rd_n = 1;
            mreq_n = 1;
        end
    endtask

    // --- TASK: I/O Write ---
    task io_write(input [15:0] port_addr, input [7:0] write_data);
        begin
            @(posedge clk); // T1
            addr = port_addr;
            
            @(posedge clk); // T2
            iorq_n = 0;
            data_out = write_data;
            drive_data = 1;
            #5 wr_n = 0; // I/O WR delay
            
            @(negedge clk); // TW
            while (!wait_n) @(negedge clk);
            
            @(posedge clk); // T3
            wr_n = 1;
            iorq_n = 1;
            #10 drive_data = 0;
        end
    endtask
endmodule