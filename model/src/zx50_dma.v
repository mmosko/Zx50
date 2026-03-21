`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_dma
 * =====================================================================================
 * DESCRIPTION:
 * This module acts as a Universal Shadow Bus Node. It is a highly specialized Block 
 * DMA controller that negotiates high-speed transfers across a shared physical 
 * backplane without Z80 CPU intervention.
 *
 * I/O BIT-PACKING PROTOCOL (24-bit Instruction Set via `OUT (C), A`):
 * The Z80 configures this module by executing two successive I/O writes to the card's 
 * base port (0x40 | Card_ID). The Z80 places the high 8 bits of the configuration on 
 * the B register (A[15:8]), the port on the C register (A[7:0]), and the low 8 bits 
 * on the accumulator (D[7:0]).
 *
 * OPCODE 0 (Setup):
 * A[15]    = 0 (Opcode 0)
 * A[14]    = Master/Slave (1 = Master, 0 = Slave)
 * A[13]    = Direction (0 = To Bus/Read RAM, 1 = From Bus/Write RAM)
 * A[12:8]  = PhysicalAddress[12:8]
 * D[7:0]   = PhysicalAddress[7:0]
 *
 * OPCODE 1 (Arm & Execute):
 * A[15]    = 1 (Opcode 1)
 * A[14:8]  = ByteCount[7:1] (Number of bytes to transfer minus 1)
 * D[7]     = ByteCount[0]
 * D[6:0]   = PhysicalAddress[19:13]
 *
 * CYCLE STEALING (YIELD LOGIC):
 * If the Z80 (or another higher-priority master) requests the bus during an active 
 * burst, this module will gracefully finish its current byte, enter a safe `M_WAIT` 
 * state, drop its transceivers to yield the bus, and seamlessly resume once clear.
 ***************************************************************************************/

module zx50_dma (
    input  wire mclk,
    input  wire reset_n,
    input  wire [3:0] card_id, 

    // --- Z80 Configuration Interface ---
    input  wire [15:0] z80_addr,
    input  wire [7:0]  z80_data_in,
    input  wire z80_iorq_n,
    input  wire z80_wr_n,

    // --- DMA Local Bus Master Output ---
    output wire [19:0] dma_phys_addr, 
    output wire [7:0]  dma_data_out,
    input  wire [7:0]  dma_data_in,
    output wire dma_local_we_n,       
    output wire dma_local_oe_n,       

    // --- Shadow Bus Controls ---
    inout  wire sh_en_n,
    inout  wire sh_rw_n,
    inout  wire sh_inc_n,
    inout  wire sh_stb_n,
    inout  wire sh_done_n,
    input  wire sh_busy_n,

    // --- Internal Status & Interrupts ---
    output wire dma_active, 
    output wire sh_c_dir,
    output wire dma_dir_to_bus,
    output wire dma_is_master, 
    
    output reg  int_pending,
    input  wire intack_clear
);
    // ==========================================
    // 1. DYNAMIC PORT DECODING & BIT-UNPACKING
    // ==========================================
    wire [7:0] dma_port = 8'h40 | {4'h0, card_id};
    wire z80_io_write = (!z80_iorq_n && !z80_wr_n && (z80_addr[7:0] == dma_port));
    
    // Decode the Z80 Bus directly into our logical operands
    wire opcode         = z80_addr[15];
    wire [14:0] operand = {z80_addr[14:8], z80_data_in[7:0]};

    // Clean contiguous 20-bit physical address register
    reg [19:0] phys_addr;
    reg [7:0]  byte_count;
    reg is_master;
    reg dir_from_bus; // 0 = To Bus (Read RAM), 1 = From Bus (Write RAM)    
    reg transfer_armed;
    reg arm_req;

    assign dma_dir_to_bus = !dir_from_bus;
    assign dma_is_master  = is_master;

    // ==========================================
    // 2. STATE MACHINE DECLARATIONS
    // ==========================================
    wire dma_go = transfer_armed;
    localparam M_IDLE   = 3'd0;
    localparam M_START  = 3'd1;
    localparam M_STROBE = 3'd2;
    localparam M_INC    = 3'd3;
    localparam M_WAIT   = 3'd4;
    localparam M_DONE   = 3'd5;
    reg [2:0] m_state;

    wire local_inc  = is_master ? (m_state == M_INC)  : (!is_master && dma_go && !sh_inc_n);
    wire local_done = is_master ? (m_state == M_DONE) : (!is_master && dma_go && !sh_done_n);
    
    // ==========================================
    // 3. CONFIGURATION REGISTER LATCHING
    // ==========================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            phys_addr      <= 20'h00000;
            byte_count     <= 8'h00;
            is_master      <= 1'b0;
            dir_from_bus   <= 1'b0;
            transfer_armed <= 1'b0;
            arm_req        <= 1'b0;
        end else if (z80_io_write) begin
            if (opcode == 1'b0) begin
                // OPCODE 0: Setup (Loads PA[12:0])
                is_master       <= operand[14];
                dir_from_bus    <= operand[13];
                phys_addr[12:0] <= operand[12:0];
            end else begin
                // OPCODE 1: Arm & High Address (Loads PA[19:13])
                byte_count      <= operand[14:7];
                phys_addr[19:13]<= operand[6:0];  
                arm_req         <= 1'b1;
            end
        end else if (arm_req && z80_iorq_n) begin
            // Wait for the Z80 I/O cycle to fully complete before asserting the bus
            transfer_armed <= 1'b1;
            arm_req        <= 1'b0;
        end else if (local_inc) begin
            // Beautiful contiguous increment. Smoothly rolls over 4K boundaries!
            phys_addr  <= phys_addr + 1'b1;
            byte_count <= byte_count - 1'b1;
        end else if (local_done) begin
            transfer_armed <= 1'b0;
        end
    end

    // ==========================================
    // 4. CYCLE STEALING: HIERARCHICAL YIELD LOGIC
    // ==========================================
    wire yield_req = (sh_busy_n == 1'b0);
    wire safe_to_yield = is_master ?
        (m_state == M_IDLE || m_state == M_WAIT || m_state == M_DONE) 
        : (sh_en_n !== 1'b0);
    reg yielding;
    
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) yielding <= 1'b0;
        else if (yield_req && safe_to_yield) yielding <= 1'b1;
        else if (!yield_req) yielding <= 1'b0;
    end

    assign dma_active = dma_go && !yielding;
    
    // ==========================================
    // 5. MASTER STATE MACHINE
    // ==========================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            m_state <= M_IDLE;
            int_pending <= 1'b0;
        end else begin
            if (intack_clear) int_pending <= 1'b0;
            
            if (is_master) begin
                case (m_state)
                    M_IDLE:   if (dma_go && !yielding && !yield_req) m_state <= M_START;
                    M_START:  m_state <= M_STROBE;
                    M_STROBE: m_state <= (byte_count == 8'h00) ? M_DONE : M_INC;
                    M_INC:    m_state <= M_WAIT;
                    M_WAIT:   if (!yielding && !yield_req) m_state <= M_STROBE;
                    M_DONE:   begin
                        int_pending <= 1'b1;
                        m_state <= M_IDLE;
                    end
                    default:  m_state <= M_IDLE;
                endcase
            end
        end
    end

    // ==========================================
    // 6. PHYSICAL TRANSCEIVER AND BUS ROUTING
    // ==========================================
    assign sh_c_dir  = !dir_from_bus;
    
    wire generated_stb_n = !(m_state == M_STROBE);
    wire int_sh_stb_n    = is_master ? generated_stb_n : sh_stb_n;
    
    assign sh_en_n   = (is_master && dma_active && m_state != M_IDLE) ? 1'b0 : 1'bz;
    assign sh_rw_n   = (is_master && dma_active && m_state != M_IDLE) ? dir_from_bus : 1'bz;
    assign sh_stb_n  = (is_master && dma_active && m_state != M_IDLE) ? generated_stb_n : 1'bz;
    assign sh_inc_n  = (is_master && dma_active && m_state == M_INC) ? 1'b0 : 1'bz;
    assign sh_done_n = (is_master && dma_active && m_state == M_DONE) ? 1'b0 : 1'bz;

    assign dma_phys_addr = phys_addr; 
    assign dma_data_out  = dma_data_in; 
    
    assign dma_local_oe_n = (dma_active && dir_from_bus == 1'b0) ? 1'b0 : 1'b1;
    assign dma_local_we_n = (dma_active && dir_from_bus == 1'b1) ? int_sh_stb_n : 1'b1;

endmodule