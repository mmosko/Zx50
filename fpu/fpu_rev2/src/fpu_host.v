`timescale 1ns/1ps

/***************************************************************************************
* MODULE: fpu_host
* DESCRIPTION:
* Host Bus Interface Subsystem for Zx50 FPU Rev 2.
*
* Functionality:
* 1. Port 0x70 (Data Stack - PUSH / POP):
*    - HOST WRITE: Assembles 4 incoming bytes into the 32-bit `host_in` register.
*      On the 4th byte, it sets `opcode_out = 8'hF2` (PUSH_STACK), pulls `wait_n` LOW,
*      and pulses `exec_start` for 1 fclk cycle.
*    - HOST READ: Serializes the 32-bit `host_out` staging register byte-by-byte
*      across 4 sequential Z80 Port 0x70 reads.
*
* 2. Port 0x71 (Command / Status):
*    - HOST WRITE: Latches 8-bit user opcode into `opcode_out`, pulls `wait_n` LOW,
*      and pulses `exec_start` for 1 fclk cycle.
*    - HOST READ: Delivers current 8-bit `status_in` register onto Z80 data bus.
*
* 3. Clock Domain Synchronization:
*    - Synchronizes asynchronous Z80 I/O control signals into the `fclk` domain.
***************************************************************************************/

module fpu_host (
    input  wire        fclk,            // Core high-speed clock (80 MHz / 160 MHz)
    input  wire        fpu_reset_n,     // Core active-LOW reset (gated with PLL lock)

    // --- Host Z80 Bus Pins ---
    input  wire [7:0]  z80_a,           // Lower 8-bit Z80 Address Bus (Port 0x70 / 0x71)
    inout  wire [7:0]  z80_d,           // Bidirectional 8-bit Z80 Data Bus
    input  wire        z80_iorq_n,      // I/O Request (~IORQ)
    input  wire        z80_rd_n,        // Read Strobe (~RD)
    input  wire        z80_wr_n,        // Write Strobe (~WR)
    input  wire        z80_m1_n,        // Machine Cycle 1 (~M1, masks INTACK)

    // --- Shared Backplane Handshake Lines (Open-Drain) ---
    output wire        wait_n,          // CPU Wait Request (1 = High-Z, 0 = Pull LOW to stall)
    output wire        int_n,           // CPU Interrupt Request (1 = High-Z, 0 = Pull LOW)

    // --- Dispatcher & Execution Core Interface ---
    output reg  [31:0] host_in,         // Assembled 32-bit host input staging word
    input  wire [31:0] host_out,        // Staged 32-bit word to be read by host
    output reg  [7:0]  opcode_out,      // Latched 8-bit command sent to dispatcher
    output reg         exec_start,      // 1 fclk pulse to trigger execution dispatcher

    input  wire        dispatch_done,   // 1 fclk pulse from microcode HALT / completion
    input  wire [7:0]  status_in        // Internal STATUS register [BSY, D, S, C, V, U, ERR, Z]
);

    // Fixed opcode for writing HOST register to TOS
    localparam OPCODE_PUSH_STACK = 8'hF2;

    // =========================================================================
    // 1. CDC Synchronizers (Z80 Bus Signals -> FCLK Domain)
    // =========================================================================
    reg [2:0] iorq_sync, rd_sync, wr_sync, m1_sync;

    always @(posedge fclk or negedge fpu_reset_n) begin
        if (!fpu_reset_n) begin
            iorq_sync <= 3'b111;
            rd_sync   <= 3'b111;
            wr_sync   <= 3'b111;
            m1_sync   <= 3'b111;
        end else begin
            iorq_sync <= {iorq_sync[1:0], z80_iorq_n};
            rd_sync   <= {rd_sync[1:0],   z80_rd_n};
            wr_sync   <= {wr_sync[1:0],   z80_wr_n};
            m1_sync   <= {m1_sync[1:0],   z80_m1_n};
        end
    end

    // Detect valid I/O accesses in FCLK domain
    wire is_io_cycle = (!iorq_sync[1] && m1_sync[1]); // ~IORQ active, not INTACK
    wire io_wr_falling_edge = is_io_cycle && (wr_sync[2] && !wr_sync[1]);
    wire io_rd_falling_edge = is_io_cycle && (rd_sync[2] && !rd_sync[1]);

    wire port_70_sel = (z80_a == 8'h70);
    wire port_71_sel = (z80_a == 8'h71);

    // =========================================================================
    // 2. Port 0x70 4-Byte Assembler & Serializer State
    // =========================================================================
    reg [1:0] wr_byte_cnt;             // Tracks byte 0, 1, 2, 3 for 32-bit Host Write
    reg [1:0] rd_byte_cnt;             // Tracks byte 0, 1, 2, 3 for 32-bit Host Read
    reg       c_wait_req;              // Wait flag driving wait_n line
    reg       c_int_req;               // Interrupt flag driving int_n line

    // Byte selector for Port 0x70 reads
    reg [7:0] port_70_rdata;
    always @(*) begin
        case (rd_byte_cnt)
            2'b00: port_70_rdata = host_out[7:0];
            2'b01: port_70_rdata = host_out[15:8];
            2'b10: port_70_rdata = host_out[23:16];
            2'b11: port_70_rdata = host_out[31:24];
        endcase
    end

    // =========================================================================
    // 3. Host Interface Logic & Execution Triggering
    // =========================================================================
    always @(posedge fclk or negedge fpu_reset_n) begin
        if (!fpu_reset_n) begin
            host_in     <= 32'h0000_0000;
            opcode_out  <= 8'h00;
            exec_start  <= 1'b0;
            wr_byte_cnt <= 2'b00;
            rd_byte_cnt <= 2'b00;
            c_wait_req  <= 1'b0;
            c_int_req   <= 1'b0;
        end else begin
            // Default 1-cycle pulse reset
            exec_start <= 1'b0;

            // Release CPU Wait line when microcode execution completes
            if (dispatch_done) begin
                c_wait_req <= 1'b0;
            end

            // -----------------------------------------------------------------
            // HOST I/O WRITE OPERATIONS (Z80 -> FPU)
            // -----------------------------------------------------------------
            if (io_wr_falling_edge) begin
                if (port_70_sel) begin
                    // Assemble 4 bytes into HOST_IN (Little-Endian)
                    case (wr_byte_cnt)
                        2'b00: host_in[7:0]   <= z80_d;
                        2'b01: host_in[15:8]  <= z80_d;
                        2'b10: host_in[23:16] <= z80_d;
                        2'b11: host_in[31:24] <= z80_d;
                    endcase

                    wr_byte_cnt <= wr_byte_cnt + 1'b1;

                    // On the 4th byte, send PUSH_STACK opcode (0xF2) to dispatcher
                    if (wr_byte_cnt == 2'b11) begin
                        opcode_out <= OPCODE_PUSH_STACK;
                        exec_start <= 1'b1;
                        c_wait_req <= 1'b1; // Hold wait_n until microcode PUSH finishes
                    end
                end 
                else if (port_71_sel) begin
                    // Latch opcode written to Port 0x71 and trigger execution
                    opcode_out <= z80_d;
                    exec_start <= 1'b1;
                    c_wait_req <= 1'b1; // Hold wait_n until microcode completes
                end
            end

            // -----------------------------------------------------------------
            // HOST I/O READ OPERATIONS (FPU -> Z80)
            // -----------------------------------------------------------------
            if (io_rd_falling_edge && port_70_sel) begin
                rd_byte_cnt <= rd_byte_cnt + 1'b1;
            end
        end
    end

    // =========================================================================
    // 4. Output Bus & Tri-State Drivers
    // =========================================================================
    wire z80_drive_status = is_io_cycle && !rd_sync[1] && port_71_sel;
    wire z80_drive_data   = is_io_cycle && !rd_sync[1] && port_70_sel;

    // Drive Z80 Data Bus during I/O Read cycles
    assign z80_d   = z80_drive_status ? status_in     :
                     (z80_drive_data  ? port_70_rdata : 8'hzz);

    // Open-Drain Backplane Outputs (0 = Pull Low, Z = High Impedance / Release)
    assign wait_n = c_wait_req ? 1'b0 : 1'bz;
    assign int_n  = c_int_req  ? 1'b0 : 1'bz;

endmodule
