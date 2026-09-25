`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_fpu
 * FILE: src/zx50_fpu.v
 * DESCRIPTION:
 * Top-Level CPLD Logic for Microchip ATF1508AS CPLD (U11) on Zx50 CPU Card (Rev C2).
 *
 * ARCHITECTURAL CLOCK DOMAINS:
 * 1. ZCLK Domain (Host Z80 Clock - 5MHz or 10MHz):
 *    - Synchronously decodes host Z80 I/O accesses for Port 0x70 (Stack) and 0x71 (CMD/Status).
 *    - Manages the 8-bit Stack Pointer (sp) for PUSH, POP, and management updates.
 *    - Drives wired-OR open-drain handshake outputs (wait_n, int_n) to stall/interrupt host.
 *
 * 2. MCLK Domain (Coprocessor High-Speed Clock - 20MHz or 40MHz):
 *    - Instantiates zx50_fpu_mem to manage private SRAM/Flash timing and arbitration.
 *    - Instantiates zx50_fpu_dispatch to execute commands and process management opcodes.
 *    - Performs 4-phase CDC level handshaking across clock domains.
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
    input  wire        z80_m1_n,    // Machine Cycle 1 (~M1, used to mask INTACK cycles)

    // --- Shared Backplane Handshake Lines (Wired-OR Open-Drain) ---
    inout  wire        wait_n,      // Active-LOW CPU Wait Request (0 = Stall Z80, Z = Release)
    inout  wire        int_n,       // Active-LOW CPU Interrupt Request (0 = Assert INT, Z = Release)

    // --- Private Coprocessor Memory Bus (Decoupled from Backplane) ---
    output wire [14:0] ca,          // 15-bit Private Address Bus (32KB active addressing)
    inout  wire [7:0]  cd,          // 8-bit Private Data Bus (SRAM/Flash data)

    // Local SRAM (IS61C256AL - U12) & Flash ROM (SST39SF040 - U13) Controls
    output wire        m_ce_n,      // Private SRAM Chip Enable (~CE)
    output wire        c_oe_n,      // Common private ~OE (SRAM/Flash Output Enable)
    output wire        c_we_n,      // Common private ~WE (SRAM/Flash Write Enable)
    output wire        f_ce_n       // Private Flash Chip Enable (~CE)
);

    // =========================================================================
    // 1. Internal Registers & Signals
    // =========================================================================
    reg [7:0] sp;           // 8-bit Hardware Stack Pointer (Targets SRAM addresses 0x0000 - 0x00FF)
    reg [7:0] opcode_reg;   // Latches command written to Port 0x71 for execution FSM
    reg [7:0] status_reg;   // Status Register [BUSY, ZERO, SIGN, CARRY, OVF, UNF, ERR, 0]
    reg       exec_req;     // Level request signal to dispatcher
    
    // Open-Drain Driver Controls (1 = Drive 0, 0 = High-Z)
    reg       c_wait_req;   // Controls wait_n driver
    reg       c_int_req;    // Controls int_n driver

    // State-locking flags to ensure 1 event per Z80 I/O strobe
    reg       io_wr_busy;   // Locks write handling while ~WR & ~IORQ remain LOW
    reg       io_rd_busy;   // Locks read auto-decrement while ~RD & ~IORQ remain LOW

    // Host-Initiated SRAM Requests (Port 0x70 PUSH/POP in zclk domain)
    reg [7:0] host_sram_wdata;
    reg [7:0] host_sram_addr;
    reg       host_sram_we_req;
    reg       host_sram_oe_req;

    // Coprocessor Engine Memory Signals (from Dispatcher / Mgmt / ALU in mclk domain)
    wire        eng_mem_we_req;
    wire        eng_mem_oe_req;
    wire        eng_sel_flash;
    wire [14:0] eng_mem_addr;
    wire [7:0]  eng_mem_wdata;
    wire [7:0]  mem_rdata;

    // Dispatcher Submodule Handshake Nets
    wire       dispatch_done_ack;
    wire       dispatch_err;
    wire [4:0] dispatch_flags;
    wire [7:0] dispatch_new_sp;
    wire       dispatch_sp_write;

    // CDC Synchronizer: Synchronize done_ack from MCLK domain into ZCLK domain
    reg [1:0] ack_sync;
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) ack_sync <= 2'b00;
        else          ack_sync <= {ack_sync[0], dispatch_done_ack};
    end
    wire dispatch_done_sync = ack_sync[1];

    // =========================================================================
    // 2. Submodule Instantiations
    // =========================================================================
    
    // --- Private Memory Controller (SRAM U12 & Flash U13) ---
    zx50_fpu_mem mem_ctrl (
        .mclk(mclk),
        .reset_n(reset_n),
        .clk_spd(clk_spd),
        .host_we_req(host_sram_we_req),
        .host_oe_req(host_sram_oe_req),
        .host_addr(host_sram_addr),
        .host_wdata(host_sram_wdata),
        .eng_we_req(eng_mem_we_req),
        .eng_oe_req(eng_mem_oe_req),
        .eng_sel_flash(eng_sel_flash),
        .eng_addr(eng_mem_addr),
        .eng_wdata(eng_mem_wdata),
        .mem_rdata(mem_rdata),
        .ca(ca),
        .cd(cd),
        .m_ce_n(m_ce_n),
        .c_oe_n(c_oe_n),
        .c_we_n(c_we_n),
        .f_ce_n(f_ce_n)
    );

    // --- Command Execution Dispatcher ---
    zx50_fpu_dispatch dispatcher (
        .mclk(mclk),
        .reset_n(reset_n),
        .exec_req(exec_req),
        .opcode(opcode_reg),
        .sp_in(sp),
        .done_ack(dispatch_done_ack),
        .err_flag(dispatch_err),
        .status_flags(dispatch_flags),
        .new_sp(dispatch_new_sp),
        .sp_write_en(dispatch_sp_write),
        .disp_sram_we_req(eng_mem_we_req),
        .disp_sram_oe_req(eng_mem_oe_req),
        .disp_sram_wdata(eng_mem_wdata),
        .disp_sram_addr(eng_mem_addr[7:0])
    );

    // Default engine memory routing (SRAM selected, upper address bits zeroed)
    assign eng_sel_flash = 1'b0;
    assign eng_mem_addr[14:8] = 7'b0000000;

    // =========================================================================
    // 3. Host Z80 Bus Decoding Logic
    // =========================================================================
    wire is_io_write = (!z80_iorq_n && !z80_wr_n && z80_m1_n);
    wire is_io_read  = (!z80_iorq_n && !z80_rd_n && z80_m1_n);

    wire port_70_sel = (z80_a[7:0] == 8'h70); // Port 0x70: Data Stack (PUSH/POP)
    wire port_71_sel = (z80_a[7:0] == 8'h71); // Port 0x71: Command Exec / Status Register

    // =========================================================================
    // 4. Host Z80 Interface State Machine (ZCLK Domain)
    // =========================================================================
    always @(posedge zclk or negedge reset_n) begin
        if (!reset_n) begin
            sp               <= 8'h00;
            opcode_reg       <= 8'h00;
            status_reg       <= 8'h00;
            exec_req         <= 1'b0;
            c_wait_req       <= 1'b0;
            c_int_req        <= 1'b0;
            host_sram_we_req <= 1'b0;
            host_sram_oe_req <= 1'b0;
            host_sram_wdata  <= 8'h00;
            host_sram_addr   <= 8'h00;
            io_wr_busy       <= 1'b0;
            io_rd_busy       <= 1'b0;
        end else begin

            // -----------------------------------------------------------------
            // Command Execution Completion Handshake (Level Acknowledge)
            // -----------------------------------------------------------------
            if (dispatch_done_sync && exec_req) begin
                status_reg[7]   <= 1'b0;            // Clear BUSY flag
                status_reg[1]   <= dispatch_err;    // Set/Clear ERR flag
                status_reg[6:2] <= dispatch_flags;  // Update math status flags
                if (dispatch_sp_write) begin
                    sp          <= dispatch_new_sp; // Commit updated SP from management engine
                end
                c_wait_req      <= 1'b0;            // Release wait_n line
                exec_req        <= 1'b0;            // Clear request level
            end

            // -----------------------------------------------------------------
            // HOST I/O WRITE OPERATIONS (~WR Active Low)
            // -----------------------------------------------------------------
            if (is_io_write) begin
                if (!io_wr_busy) begin
                    io_wr_busy <= 1'b1;

                    if (port_70_sel) begin
                        host_sram_wdata  <= z80_d;
                        host_sram_addr   <= sp;
                        host_sram_we_req <= 1'b1;
                        sp               <= sp + 1'b1;
                    end else if (port_71_sel) begin
                        opcode_reg    <= z80_d;
                        status_reg[7] <= 1'b1; // BUSY = 1
                        status_reg[1] <= 1'b0; // ERR = 0
                        exec_req      <= 1'b1; // Raise CDC request level
                        c_wait_req    <= 1'b1; // Pull wait_n LOW
                    end
                end else begin
                    host_sram_we_req <= 1'b0;
                end
            end else begin
                io_wr_busy       <= 1'b0;
                host_sram_we_req <= 1'b0;
            end

            // -----------------------------------------------------------------
            // HOST I/O READ OPERATIONS (~RD Active Low)
            // -----------------------------------------------------------------
            if (is_io_read && port_70_sel) begin
                host_sram_oe_req <= 1'b1;
                if (!io_rd_busy) begin
                    io_rd_busy     <= 1'b1;
                    host_sram_addr <= sp - 1'b1; // Lock target TOS address for entire read cycle
                    sp             <= sp - 1'b1; // Auto-decrement SP
                end
            end else begin
                io_rd_busy       <= 1'b0;
                host_sram_oe_req <= 1'b0;
            end
        end
    end

    // =========================================================================
    // 5. Output Drivers & Tri-State Control Logic
    // =========================================================================
    
    // --- Host Z80 Data Bus Driving ---
    wire z80_drive_status = is_io_read && port_71_sel;
    wire z80_drive_sram   = is_io_read && port_70_sel;

    assign z80_d  = z80_drive_status ? status_reg :
                    (z80_drive_sram   ? mem_rdata  : 8'hzz);

    // --- Shared Open-Drain Handshake Outputs ---
    assign wait_n = c_wait_req ? 1'b0 : 1'bz;
    assign int_n  = c_int_req  ? 1'b0 : 1'bz;

endmodule