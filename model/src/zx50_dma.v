`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_dma (12-Bit Adder Optimization)
 * =====================================================================================
 * DESCRIPTION:
 * Universal Shadow Bus Node. Acts as a highly specialized Block DMA controller 
 * that negotiates transfers across a shared physical backplane.
 *
 * CPLD FITTING OPTIMIZATION (THE 4K PAGE LIMIT):
 * To fit within the tight routing constraints of a 128-macrocell CPLD, the 20-bit 
 * address counter has been split. It uses a static 8-bit upper address latch (A19-A12) 
 * and a fast 12-bit lower address counter (A11-A0). 
 *
 * SOFTWARE RULE: 
 * DMA transfers will smoothly increment up to 4,096 bytes, but will wrap around 
 * physical 4KB boundaries (A12). The Z80 programmer must manually chunk transfers 
 * that cross MMU logical page boundaries.
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
    
    wire opcode         = z80_addr[15];
    wire [14:0] operand = {z80_addr[14:8], z80_data_in[7:0]};

    // --- OPTIMIZED REGISTERS ---
    reg [7:0]  phys_addr_hi; // Static upper latch (A19-A12)
    reg [11:0] phys_addr_lo; // Fast lower counter (A11-A0)
    
    reg [7:0]  byte_count;
    reg is_master;
    reg dir_from_bus; 
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
            phys_addr_hi   <= 8'h00;
            phys_addr_lo   <= 12'h000;
            byte_count     <= 8'h00;
            is_master      <= 1'b0;
            dir_from_bus   <= 1'b0;
            transfer_armed <= 1'b0;
            arm_req        <= 1'b0;
        end else if (z80_io_write) begin
            if (opcode == 1'b0) begin
                // OPCODE 0: Setup
                is_master         <= operand[14];
                dir_from_bus      <= operand[13];
                phys_addr_lo      <= operand[11:0]; // Load 4K offset (A11-A0)
                phys_addr_hi[0]   <= operand[12];   // Load A12
            end else begin
                // OPCODE 1: Arm & High Address
                byte_count        <= operand[14:7];
                phys_addr_hi[7:1] <= operand[6:0];  // Load A19-A13
                arm_req           <= 1'b1;
            end
        end else if (arm_req && z80_iorq_n) begin
            transfer_armed <= 1'b1;
            arm_req        <= 1'b0;
        end else if (local_inc) begin
            // OPTIMIZATION: Only the 12-bit register participates in the math!
            phys_addr_lo <= phys_addr_lo + 1'b1;
            byte_count   <= byte_count - 1'b1;
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

    // Concatenate the static high bits and the fast 4K counter for the local address
    assign dma_phys_addr = {phys_addr_hi, phys_addr_lo}; 
    
    assign dma_data_out  = dma_data_in; 
    
    assign dma_local_oe_n = (dma_active && dir_from_bus == 1'b0) ? 1'b0 : 1'b1;
    assign dma_local_we_n = (dma_active && dir_from_bus == 1'b1) ? int_sh_stb_n : 1'b1;

endmodule