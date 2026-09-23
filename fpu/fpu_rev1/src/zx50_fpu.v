`timescale 1ns/1ps

// The ATF1508AS CPLD Core Logic
module zx50_fpu (
    input  wire        mclk,        // 20MHz or 40MHz Coprocessor Clock
    input  wire        zclk,        // 5MHz or 10MHz Host Z80 Clock
    input  wire        reset_n,     // Active-low Global Reset
    input  wire        clk_spd,     // 1=Fast MCLK (40MHz), 0=Slow MCLK (20MHz)

    // Z80 Host Bus Interface
    input  wire [15:0] z80_a,
    inout  wire [7:0]  z80_d,
    input  wire        z80_mreq_n,
    input  wire        z80_iorq_n,
    input  wire        z80_rd_n,
    input  wire        z80_wr_n,
    input  wire        z80_m1_n,

    // Shared Open-Drain Bus Lines (Active Low)
    inout  wire        wait_n,      // Tri-state: 0 = Assert WAIT, Z = Release
    inout  wire        int_n,       // Tri-state: 0 = Assert INT,  Z = Release

    // Private Memory Bus Interface (CA[13:0] & CD[7:0])
    output wire [13:0] ca,
    inout  wire [7:0]  cd,

    // Local SRAM (U12 - 25ns Fixed) Controls
    output wire        m_ce_n,
    output wire        m_oe_n,
    output wire        m_we_n,
    
    // Local Flash (U13 - 55ns Fixed) Controls
    output wire        f_ce_n,
    output wire        f_oe_n,
    output wire        f_we_n
);

    // =========================================================================
    // 1. Registers & Internal Signals
    // =========================================================================
    reg [7:0] sp;           // 8-bit Stack Pointer (0x0000 - 0x00FF in private SRAM)
    reg [7:0] opcode_reg;   // Latched opcode written to port 0x71
    reg [7:0] status_reg;   // [BUSY, ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW, ERR, 0]
    reg       exec_start;   // Trigger pulse for execution state machine
    
    // Internal Assertion Flags (1 = Pull bus line LOW, 0 = High-Z)
    reg       c_wait_req;   
    reg       c_int_req;

    // Synchronizer shift registers for Z80 asynchronous signals (mclk domain)
    reg [2:0] iorq_sync;
    reg [2:0] rd_sync;
    reg [2:0] wr_sync;

    // Private Memory Request Flags & Pipeline Counters
    reg [7:0] sram_wdata;
    reg       sram_we_req;
    reg       sram_oe_req;
    reg [1:0] sram_tick_cnt;

    reg       flash_req;
    reg [1:0] flash_tick_cnt;

    // Dynamic Target Cycle Limits based on clk_spd
    // SRAM (25ns): Slow MCLK (20MHz/50ns) -> 1 tick (cnt=0); Fast MCLK (40MHz/25ns) -> 2 ticks (cnt=1)
    wire [1:0] sram_target_ticks  = clk_spd ? 2'd1 : 2'd0;

    // Flash (55ns): Slow MCLK (20MHz/50ns) -> 2 ticks (cnt=1); Fast MCLK (40MHz/25ns) -> 3 ticks (cnt=2)
    wire [1:0] flash_target_ticks = clk_spd ? 2'd2 : 2'd1;

    // =========================================================================
    // 2. Signal Synchronization & Edge Detection (zclk Domain)
    // =========================================================================
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) begin
            iorq_sync <= 3'b111;
            rd_sync   <= 3'b111;
            wr_sync   <= 3'b111;
        end else begin
            iorq_sync <= {iorq_sync[1:0], z80_iorq_n};
            rd_sync   <= {rd_sync[1:0],   z80_rd_n};
            wr_sync   <= {wr_sync[1:0],   z80_wr_n};
        end
    end

    // Decoded Z80 I/O Cycle Controls
    wire is_io_cycle  = (!iorq_sync[1] && z80_m1_n);
    wire port_70_sel  = is_io_cycle && (z80_a[7:0] == 8'h70);
    wire port_71_sel  = is_io_cycle && (z80_a[7:0] == 8'h71);

    wire io_wr_strobe = is_io_cycle && (wr_sync[2] && !wr_sync[1]); // Falling edge of ~WR
    wire io_rd_strobe = is_io_cycle && (rd_sync[2] && !rd_sync[1]); // Falling edge of ~RD

    // =========================================================================
    // 3. Reset & Initialization Block
    // =========================================================================
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) begin
            sp             <= 8'h00;
            opcode_reg     <= 8'h00;
            status_reg     <= 8'h00; // ERR=0, BUSY=0
            exec_start     <= 1'b0;
            c_wait_req     <= 1'b0;  // High-Z (Deasserted)
            c_int_req      <= 1'b0;  // High-Z (Deasserted)
            sram_we_req    <= 1'b0;
            sram_oe_req    <= 1'b0;
            sram_wdata     <= 8'h00;
            sram_tick_cnt  <= 2'd0;
            flash_req      <= 1'b0;
            flash_tick_cnt <= 2'd0;
        end else begin
            exec_start <= 1'b0; // Default 1-tick pulse clear

            // -----------------------------------------------------------------
            // Port Writes (0x70 = DATA_PUSH, 0x71 = CMD_EXEC)
            // -----------------------------------------------------------------
            if (io_wr_strobe) begin
                if (port_70_sel) begin
                    // DATA_PUSH: Store Z80 data at current SP and increment SP
                    sram_wdata    <= z80_d;
                    sram_we_req   <= 1'b1;
                    sram_tick_cnt <= 2'd0;
                    sp            <= sp + 1'b1;
                end else if (port_71_sel) begin
                    // CMD_EXEC: Latch opcode, set BUSY flag, and trigger calculation
                    opcode_reg    <= z80_d;
                    status_reg[7] <= 1'b1; // BUSY = 1
                    status_reg[1] <= 1'b0; // ERR = 0
                    exec_start    <= 1'b1;
                    c_wait_req    <= 1'b1; // Pulls ~WAIT line LOW
                end
            end

            // SRAM Write Cycle Timing Logic
            if (sram_we_req) begin
                if (sram_tick_cnt == sram_target_ticks) begin
                    sram_we_req   <= 1'b0;
                    sram_tick_cnt <= 2'd0;
                end else begin
                    sram_tick_cnt <= sram_tick_cnt + 1'b1;
                end
            end

            // -----------------------------------------------------------------
            // Port Reads (0x70 = DATA_POP)
            // -----------------------------------------------------------------
            if (io_rd_strobe && port_70_sel) begin
                // DATA_POP: Decrement SP first, then fetch byte from SRAM
                sp          <= sp - 1'b1;
                sram_oe_req <= 1'b1;
            end else if (!port_70_sel || rd_sync[1]) begin
                sram_oe_req <= 1'b0;
            end

            // -----------------------------------------------------------------
            // Private Flash Pipeline Control
            // -----------------------------------------------------------------
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
    // 4. Host Z80 & Private Bus Output Drivers
    // =========================================================================
    // Drive Z80 Data Bus during Port 0x71 Status Read or Port 0x70 Data Pop
    wire z80_drive_status = port_71_sel && !rd_sync[1];
    wire z80_drive_sram   = port_70_sel && !rd_sync[1];

    assign z80_d  = z80_drive_status ? status_reg :
                    (z80_drive_sram   ? cd : 8'hzz);

    // Private Address Routing: Stack targets lower 256 bytes of U12 SRAM
    assign ca     = {6'b000000, sp};

    // Private SRAM Controls
    assign m_ce_n = !(sram_we_req || sram_oe_req);
    assign m_we_n = !sram_we_req;
    assign m_oe_n = !sram_oe_req;

    // Private Flash Controls
    assign f_ce_n = !flash_req;
    assign f_oe_n = !flash_req;
    assign f_we_n = 1'b1;

    // Private Data Bus Drive (during SRAM Writes)
    assign cd     = sram_we_req ? sram_wdata : 8'hzz;

    // Open-Drain Handshake Outputs for Shared Active-Low Buses
    assign wait_n = c_wait_req ? 1'b0 : 1'bz;
    assign int_n  = c_int_req  ? 1'b0 : 1'bz;

endmodule
