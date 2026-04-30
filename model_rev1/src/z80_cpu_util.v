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
    input  wire wait_n,
    output reg reset_n
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
        reset_n = 1;
    end

    task wait_cycles(input integer cycles);
        integer i;
        begin
            for (i = 0; i < cycles; i = i + 1) @(posedge clk);
        end
    endtask

    task boot_sequence;
        begin
            reset_n = 1;
            wait_cycles(2);
            reset_n = 0;
            wait_cycles(5);
            reset_n = 1;
            wait_cycles(5);
        end
    endtask

    // ==========================================
    // CYCLE: Memory Read (Accurate T-States)
    // ==========================================
    task mem_read(input [15:0] target_addr, output [7:0] read_data);
        begin
            @(posedge clk); // T1 Start
            addr = target_addr;
            
            @(negedge clk); // MREQ falls
            mreq_n = 0;
            #10;            // ~10ns delay before RD falls
            rd_n = 0; 
            
            @(posedge clk); // T2 Start
            
            @(negedge clk); // TW/T3 setup: Sample WAIT
            while (!wait_n) @(negedge clk);

            // FALLING EDGE OF T3: Sample Data! (Transceivers still open)
            read_data = data;

            @(posedge clk); // T4 Start
            rd_n = 1;
            #10;            // ~10ns delay before MREQ rises
            mreq_n = 1;
        end
    endtask

    // ==========================================
    // CYCLE: Memory Write (Accurate T-States)
    // ==========================================
    task mem_write(input [15:0] target_addr, input [7:0] write_data);
        begin
            @(posedge clk); // T1 Start
            addr = target_addr;
            
            @(negedge clk); // MREQ falls
            mreq_n = 0;
            
            @(posedge clk); // T2 Start
            drive_data = 1;
            data_out = write_data;
            #10;            // ~10ns delay before WR falls
            wr_n = 0;

            @(negedge clk); // TW/T3 setup: Sample WAIT
            while (!wait_n) @(negedge clk);

            @(posedge clk); // T4 Start
            wr_n = 1;
            
            @(negedge clk); 
            #10;            // ~10ns delay before MREQ rises
            mreq_n = 1;
            drive_data = 0;
        end
    endtask

    // ==========================================
    // CYCLE: I/O Write
    // ==========================================
    task io_write(input [15:0] port_addr, input [7:0] write_data);
        begin
            @(posedge clk); // T1 Start
            addr = port_addr;
            drive_data = 1;
            data_out = write_data;

            @(posedge clk); // T2 Start
            
            @(negedge clk); // IORQ falls
            iorq_n = 0;
            #10;            // ~10ns delay before WR falls
            wr_n = 0;

            @(negedge clk); // TW (Z80 forces 1 wait state for I/O)
            while (!wait_n) @(negedge clk);

            @(posedge clk); // T3 Start

            @(negedge clk); // WR rises first
            wr_n = 1;
            #10;            // ~10ns delay before IORQ rises
            iorq_n = 1;
            drive_data = 0;
        end
    endtask

    // ==========================================
    // CYCLE: I/O Read
    // ==========================================
    task io_read(input [15:0] port_addr, output [7:0] read_data);
        begin
            @(posedge clk); // T1 Start
            addr = port_addr;

            @(posedge clk); // T2 Start
            
            @(negedge clk); // IORQ & RD fall
            iorq_n = 0;
            #10;
            rd_n = 0;

            @(negedge clk); // TW (Z80 forces 1 wait state for I/O)
            while (!wait_n) @(negedge clk);

            @(posedge clk); // T3 Start

            @(negedge clk); 
            read_data = data; // Sample data on falling edge of T3
            rd_n = 1;
            #10;
            iorq_n = 1;
        end
    endtask

    // ==========================================
    // CYCLE: Interrupt Acknowledge (INTACK)
    // ==========================================
    task intack(output [7:0] vector);
        begin
            @(posedge clk); // T1 Start
            m1_n = 0;

            @(posedge clk); // T2 Start
            iorq_n = 0; // IORQ drops with M1 for INTACK

            @(negedge clk); // TW: Sample WAIT (Z80 forces 2 auto-waits)
            while (!wait_n) @(negedge clk);

            @(posedge clk); // T3 Start (Vector is stable)
            vector = data;

            iorq_n = 1;
            m1_n = 1;
        end
    endtask

    task mmu_map_page(input [1:0] card_id, input [3:0] logical_window, input [7:0] physical_page);
        reg [15:0] io_addr;
        begin
            io_addr = (logical_window << 8) | 8'h30 | card_id;
            io_write(io_addr, physical_page);
        end
    endtask

    task init_mmu(input [1:0] card_id);
        integer i;
        begin
            for (i = 0; i < 16; i = i + 1) begin
                mmu_map_page(card_id, i[3:0], i[7:0]);
            end
        end
    endtask

endmodule
