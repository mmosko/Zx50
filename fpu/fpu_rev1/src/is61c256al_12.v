`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: is61c256al_12
 * FILE: src/is61c256al_12.v
 * DESCRIPTION:
 * High-Fidelity Timing Simulation Model for ISSI IS61C256AL-12TLI (32K x 8 12ns SRAM).
 * Standard IEEE 1364-2001 Verilog compliant for iverilog compilation.
 ***************************************************************************************/

module is61c256al_12 #(
    parameter MEM_INIT_FILE = ""
)(
    input  wire [14:0] addr,  // Address Bus (A0-A14)
    inout  wire [7:0]  data,  // Data Bus (I/O0-I/O7)
    input  wire        ce_n,  // Chip Enable (~CE)
    input  wire        oe_n,  // Output Enable (~OE)
    input  wire        we_n   // Write Enable (~WE)
);

    // =========================================================================
    // 1. Memory Array & Pre-load
    // =========================================================================
    reg [7:0] memory_array [0:32767];

    initial begin
        if (MEM_INIT_FILE != "") begin
            $readmemh(MEM_INIT_FILE, memory_array);
            $display("[%t ns] SRAM [IS61C256AL-12TLI]: Pre-loaded array from %s", $time, MEM_INIT_FILE);
        end
    end

    // =========================================================================
    // 2. Read Cycle Timing Logic
    // =========================================================================
    reg [7:0] internal_data;
    reg       oe_driver;

    time t_addr_change;
    time t_ce_low;
    time t_oe_low;

    initial begin
        internal_data = 8'hXX;
        oe_driver     = 1'b0;
        t_addr_change = 0;
        t_ce_low      = 0;
        t_oe_low      = 0;
    end

    always @(addr) t_addr_change = $time;
    always @(negedge ce_n) t_ce_low = $time;
    always @(negedge oe_n) t_oe_low = $time;

    wire read_active = (!ce_n && !oe_n && we_n);

    always @(read_active or addr) begin
        if (read_active) begin
            if (^addr !== 1'bx) begin
                internal_data <= #12 memory_array[addr];
            end else begin
                internal_data <= #12 8'hXX;
            end
            oe_driver <= #6 1'b1; // Output drivers turn on after tDOE (6ns)
        end
    end

    always @(ce_n or oe_n or we_n) begin
        if (!we_n) begin
            oe_driver <= #6 1'b0; // tHZWE = 6ns
        end else if (oe_n) begin
            oe_driver <= #6 1'b0; // tHZOE = 6ns
        end else if (ce_n) begin
            oe_driver <= #7 1'b0; // tHZCS = 7ns
        end
    end

    assign data = (oe_driver && read_active) ? internal_data : 8'bZ;

    // =========================================================================
    // 3. Write Cycle Timing & Verification Logic
    // =========================================================================
    time t_write_start;
    time t_data_change;
    time t_pwe;
    time t_sd;
    time t_aw;
    reg  in_write_cycle;

    initial begin
        t_write_start  = 0;
        t_data_change  = 0;
        t_pwe          = 0;
        t_sd           = 0;
        t_aw           = 0;
        in_write_cycle = 1'b0;
    end

    always @(data) t_data_change = $time;

    // Detect active write window
    always @(ce_n or we_n) begin
        if (!ce_n && !we_n) begin
            if (!in_write_cycle) begin
                t_write_start  = $time;
                in_write_cycle = 1'b1;
            end
        end
    end

    // Execute Write on Write-Termination Edge (posedge we_n or posedge ce_n)
    always @(posedge we_n or posedge ce_n) begin
        if (in_write_cycle) begin
            in_write_cycle = 1'b0; // Clear active write state
            t_pwe = $time - t_write_start;
            t_sd  = $time - t_data_change;
            t_aw  = $time - t_addr_change;

            // --- TIMING VIOLATION CHECKS ---
            if (oe_n && (t_pwe < 8)) begin
                $display("[%t ns] SRAM ERROR: tPWE2 (WE Pulse Width, OE High) Violated! Pulse = %0d ns (Min = 8 ns)", $time, t_pwe);
            end else if (!oe_n && (t_pwe < 9)) begin
                $display("[%t ns] SRAM ERROR: tPWE1 (WE Pulse Width, OE Low) Violated! Pulse = %0d ns (Min = 9 ns)", $time, t_pwe);
            end

            if (t_sd < 7) begin
                $display("[%t ns] SRAM ERROR: tSD (Data Setup Time) Violated! Setup = %0d ns (Min = 7 ns)", $time, t_sd);
            end

            if (t_aw < 10) begin
                $display("[%t ns] SRAM ERROR: tAW/tSCS (Address/CE Setup Time) Violated! Setup = %0d ns (Min = 10 ns)", $time, t_aw);
            end

            // --- WRITE EXECUTION ---
            if (^addr !== 1'bx && ^data !== 1'bx) begin
                memory_array[addr] <= data;
            end else begin
                $display("[%t ns] SRAM WRITE ERROR: Suppressed write due to X/Z on Address (%h) or Data (%h)!", $time, addr, data);
            end
        end
    end

endmodule