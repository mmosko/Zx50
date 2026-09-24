`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu
 * FILE: src/zx50_fpu.v
 * DESCRIPTION:
 * Top-Level CPLD Logic for Microchip ATF1508AS CPLD (U11) on Zx50 CPU Card (Rev C1).
 * Instantiates zx50_fpu_dispatch for command execution with CDC level synchronizers.
 ***************************************************************************************/

module zx50_fpu (
    input  wire        mclk,        // 20MHz or 40MHz High-Speed Coprocessor Clock
    input  wire        zclk,        // 5MHz or 10MHz Host Z80 CPU Clock
    input  wire        reset_n,     // Global System Reset (Active LOW)
    input  wire        clk_spd,     // Speed Select Jumper (1=40MHz Fast, 0=20MHz Slow)

    // --- Host Z80 Backplane Bus Interface ---
    input  wire [15:0] z80_a,       // 16-bit Host Address Bus (Port 0x70/0x71 decoding)
    inout  wire [7:0]  z80_d,       // 8-bit Bidirectional Host Data Bus
    input  wire        z80_mreq_n,  // Memory Request (~MREQ)
    input  wire        z80_iorq_n,  // I/O Request (~IORQ)
    input  wire        z80_rd_n,    // Read Strobe (~RD)
    input  wire        z80_wr_n,    // Write Strobe (~WR)
    input  wire        z80_m1_n,    // Machine Cycle 1 (~M1)

    // --- Shared Backplane Handshake Lines (Wired-OR Open-Drain) ---
    inout  wire        wait_n,      // Active-LOW CPU Wait Request
    inout  wire        int_n,       // Active-LOW CPU Interrupt Request

    // --- Private Coprocessor Memory Bus ---
    output wire [13:0] ca,          // 14-bit Private Address Bus
    inout  wire [7:0]  cd,          // 8-bit Private Data Bus

    // Local SRAM (U12) Controls
    output wire        m_ce_n,
    output wire        m_oe_n,
    output wire        m_we_n,
    
    // Local Flash ROM (U13) Controls
    output wire        f_ce_n,
    output wire        f_oe_n,
    output wire        f_we_n
);

    // =========================================================================
    // 1. Internal Registers & State Variables
    // =========================================================================
    reg [7:0] sp;           // 8-bit Hardware Stack Pointer
    reg [7:0] opcode_reg;   // Latched opcode written to Port 0x71
    reg [7:0] status_reg;   // Status Register [BUSY, ZERO, SIGN, CARRY, OVF, UNF, ERR, 0]
    reg       exec_req;     // Level request signal to dispatcher
    
    reg       c_wait_req;   // Controls wait_n driver
    reg       c_int_req;    // Controls int_n driver

    reg       io_wr_busy;   // Write lock flag
    reg       io_rd_busy;   // Read lock flag

    // Private SRAM Pipeline Registers
    reg [7:0] sram_wdata;
    reg [7:0] sram_addr;
    reg       sram_we_req;
    reg       sram_we_strobe;
    reg       sram_we_hold;
    reg       sram_oe_req;

    // Private Flash Request Controls
    reg       flash_req;
    reg [1:0] flash_tick_cnt;
    wire [1:0] flash_target_ticks = clk_spd ? 2'd2 : 2'd1;

    // Dispatcher Submodule Handshake Nets
    wire       dispatch_done_ack;
    wire       dispatch_err;
    wire [4:0] dispatch_flags;

    // Synchronize done_ack into ZCLK domain
    reg [1:0] ack_sync;
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) ack_sync <= 2'b00;
        else          ack_sync <= {ack_sync[0], dispatch_done_ack};
    end
    wire dispatch_done_sync = ack_sync[1];

    // =========================================================================
    // 2. Submodule Instantiation: Command Dispatcher
    // =========================================================================
    zx50_fpu_dispatch dispatcher (
        .mclk(mclk),
        .reset_n(reset_n),
        .exec_req(exec_req),
        .opcode(opcode_reg),
        .done_ack(dispatch_done_ack),
        .err_flag(dispatch_err),
        .status_flags(dispatch_flags)
    );

    // =========================================================================
    // 3. Host Z80 Bus Decoding Logic
    // =========================================================================
    wire is_io_write = (!z80_iorq_n && !z80_wr_n && z80_m1_n);
    wire is_io_read  = (!z80_iorq_n && !z80_rd_n && z80_m1_n);

    wire port_70_sel = (z80_a[7:0] == 8'h70);
    wire port_71_sel = (z80_a[7:0] == 8'h71);

    // =========================================================================
    // 4. Host Z80 Interface State Machine (ZCLK Domain)
    // =========================================================================
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) begin
            sp          <= 8'h00;
            opcode_reg  <= 8'h00;
            status_reg  <= 8'h00;
            exec_req    <= 1'b0;
            c_wait_req  <= 1'b0;
            c_int_req   <= 1'b0;
            sram_we_req <= 1'b0;
            sram_oe_req <= 1'b0;
            sram_wdata  <= 8'h00;
            sram_addr   <= 8'h00;
            io_wr_busy  <= 1'b0;
            io_rd_busy  <= 1'b0;
        end else begin

            // -----------------------------------------------------------------
            // Command Execution Completion Handshake (Level Acknowledge)
            // -----------------------------------------------------------------
            if (dispatch_done_sync && exec_req) begin
                status_reg[7]   <= 1'b0;          // Clear BUSY flag
                status_reg[1]   <= dispatch_err;  // Set/Clear ERR flag
                status_reg[6:2] <= dispatch_flags; // Update math status flags
                c_wait_req      <= 1'b0;          // Release wait_n line
                exec_req        <= 1'b0;          // Clear request flag
            end

            // -----------------------------------------------------------------
            // HOST I/O WRITE OPERATIONS (~WR Active Low)
            // -----------------------------------------------------------------
            if (is_io_write) begin
                if (!io_wr_busy) begin
                    io_wr_busy <= 1'b1;

                    if (port_70_sel) begin
                        // PORT 0x70 WRITE (DATA_PUSH)
                        sram_wdata  <= z80_d;
                        sram_addr   <= sp;
                        sram_we_req <= 1'b1;
                        sp          <= sp + 1'b1;
                    end else if (port_71_sel) begin
                        // PORT 0x71 WRITE (CMD_EXEC)
                        opcode_reg    <= z80_d;
                        status_reg[7] <= 1'b1; // BUSY = 1
                        status_reg[1] <= 1'b0; // ERR = 0
                        exec_req      <= 1'b1; // Raise level request
                        c_wait_req    <= 1'b1; // Pull wait_n LOW
                    end
                end else begin
                    sram_we_req <= 1'b0;
                end
            end else begin
                io_wr_busy  <= 1'b0;
                sram_we_req <= 1'b0;
            end

            // -----------------------------------------------------------------
            // HOST I/O READ OPERATIONS (~RD Active Low)
            // -----------------------------------------------------------------
            if (is_io_read && port_70_sel) begin
                sram_oe_req <= 1'b1;
                if (!io_rd_busy) begin
                    io_rd_busy <= 1'b1;
                    sp         <= sp - 1'b1;
                end
            end else begin
                io_rd_busy  <= 1'b0;
                sram_oe_req <= 1'b0;
            end
        end
    end

    // =========================================================================
    // 5. Private Memory Pipeline & Timing Controller (MCLK Domain)
    // =========================================================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            sram_we_strobe <= 1'b0;
            sram_we_hold   <= 1'b0;
            flash_req      <= 1'b0;
            flash_tick_cnt <= 2'd0;
        end else begin
            if (sram_we_req && !sram_we_strobe && !sram_we_hold) begin
                sram_we_strobe <= 1'b1;
                sram_we_hold   <= 1'b0;
            end else if (sram_we_strobe) begin
                sram_we_strobe <= 1'b0;
                sram_we_hold   <= 1'b1;
            end else begin
                sram_we_strobe <= 1'b0;
                sram_we_hold   <= 1'b0;
            end

            if (flash_req) begin
                if (flash_tick_cnt == flash_target_ticks) begin
                    flash_tick_cnt <= 2'd0;
                    flash_req      <= 1'b0;
                end else begin
                    flash_tick_cnt <= flash_tick_cnt + 1'b1;
                end
            end
        end
    end

    // =========================================================================
    // 6. Output Drivers & Tri-State Control Logic
    // =========================================================================
    wire z80_drive_status = is_io_read && port_71_sel;
    wire z80_drive_sram   = is_io_read && port_70_sel;

    assign z80_d  = z80_drive_status ? status_reg :
                    (z80_drive_sram   ? cd         : 8'hzz);

    wire sram_write_active = (sram_we_strobe || sram_we_hold);

    assign ca     = sram_write_active ? {6'b000000, sram_addr} : {6'b000000, sp};

    assign m_ce_n = !(sram_write_active || sram_oe_req);
    assign m_we_n = !sram_we_strobe;
    assign m_oe_n = !sram_oe_req;

    assign f_ce_n = !flash_req;
    assign f_oe_n = !flash_req;
    assign f_we_n = 1'b1;

    assign cd     = sram_write_active ? sram_wdata : 8'hzz;

    assign wait_n = c_wait_req ? 1'b0 : 1'bz;
    assign int_n  = c_int_req  ? 1'b0 : 1'bz;

endmodule
