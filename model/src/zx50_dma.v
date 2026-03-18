`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_dma
 * DESCRIPTION: Universal Shadow Bus Node
 * This module acts as a highly specialized Block DMA controller that negotiates 
 * transfers across a shared physical backplane without Z80 CPU intervention.
 * It decodes a bit-packed 24-bit instruction set mapped to a dynamic I/O port,
 * bypassing the local MMU to generate a full 20-bit physical address.
 *
 * CYCLE STEALING (NEW): If the Z80 requests the bus during an active burst, 
 * this module will gracefully finish its current byte, enter a safe `M_WAIT` 
 * state, drop its `dma_active` flag to yield to the Z80, and seamlessly resume.
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
    // Base port is 0x40. We logically OR the card's physical dip-switch ID 
    // to ensure Card 0 listens to 0x40 and Card 1 listens to 0x41.
    wire [7:0] dma_port = 8'h40 | {4'h0, card_id};

    // Detect an I/O write specifically targeted at this card's DMA port
    wire z80_io_write = (!z80_iorq_n && !z80_wr_n && (z80_addr[7:0] == dma_port));
    
    // The Z80 `OUT (C), A` instruction blasts 24 bits of data across the bus:
    // A[15] acts as our Opcode (0 = Setup Address, 1 = Setup Count & Arm)
    // A[14:8] and D[7:0] are combined into a 15-bit operand payload.
    wire opcode       = z80_addr[15];
    wire [14:0] operand = {z80_addr[14:8], z80_data_in[7:0]};

    //reg [19:0] phys_addr;
    reg [10:0] phys_addr_low;
    reg [19:15] phys_addr_high;

    reg [7:0]  byte_count;
    reg is_master;
    reg dir_to_bus;     
    reg transfer_armed;
    reg arm_req; // DEFERRED ARMING QUEUE

    assign dma_dir_to_bus = dir_to_bus;
    assign dma_is_master  = is_master;

    // ==========================================
    // 2. CONFIGURATION REGISTER LATCHING
    // ==========================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
//            phys_addr      <= 20'h00000;
            phys_addr_low  <= 11'h000;
            phys_addr_high <= 5'h00;
            byte_count     <= 8'h00;
            is_master      <= 1'b0;
            dir_to_bus     <= 1'b0;
            transfer_armed <= 1'b0;
            arm_req        <= 1'b0;
        end else if (z80_io_write) begin
//            if (opcode == 1'b0) begin
//                // OPCODE 0: Define Role and Lower Address
//                is_master        <= operand[14];
//                dir_to_bus       <= operand[13];
//                phys_addr[12:0]  <= operand[12:0];
//            end else begin
//                // OPCODE 1: Define Upper Address, Count, and queue the Arm Request
//                byte_count       <= operand[14:7];
//                phys_addr[19:13] <= operand[6:0]; 
//                arm_req          <= 1'b1;         
//            end
	if (opcode == 1'b0) begin
	    is_master           <= operand[14];
	    dir_to_bus          <= operand[13];
	    phys_addr_low[10:0] <= operand[10:0]; // Only store the used lower bits
	end else begin
	    byte_count          <= operand[14:7];
	    phys_addr_high      <= operand[4:0];  // Only store the top 5 page bits
	    arm_req             <= 1'b1;
	end


        end else if (arm_req && z80_iorq_n) begin
            // THE SHIELD: Safely commit the armed flag ONLY after the Z80 has 
            // completely finished the OUT instruction (IORQ goes high).
            transfer_armed <= 1'b1;
            arm_req        <= 1'b0;
        end else if (local_inc) begin
            // Hardware auto-increment while the DMA burst is running
            // phys_addr  <= phys_addr + 1'b1;
            // byte_count <= byte_count - 1'b1;
            // Hardware auto-increment while the DMA burst is running
            //phys_addr[7:0] <= phys_addr[7:0] + 1'b1;
            //byte_count     <= byte_count - 1'b1;
	    phys_addr_low[7:0] <= phys_addr_low[7:0] + 1'b1;
            byte_count         <= byte_count - 1'b1;

        end else if (local_done) begin
            // Clear the armed flag when the transfer fully completes
            transfer_armed <= 1'b0;
        end
    end

    // ==========================================
    // 3. CYCLE STEALING: HIERARCHICAL YIELD LOGIC
    // ==========================================
    // Because we defer arming until the setup instruction ends, dma_go no longer 
    // needs to check z80_iorq_n. It is completely immune to mid-burst Z80 I/O noise!
    wire dma_go = transfer_armed;
    
    // If the Z80 targets any card on the backplane, the CPLD pulls sh_busy_n low.
    wire yield_req = (sh_busy_n == 1'b0);
    
    // ORCHESTRATED HANDOFF: To prevent desynchronization, the Master acts as the 
    // sole orchestrator. The Master decides when it is safe to pause (M_WAIT). 
    // When it pauses, it drops dma_active, which floats the sh_en_n backplane line.
    // The Slave ONLY yields when it explicitly sees the Master release the bus!
    wire safe_to_yield = is_master ? (m_state == M_IDLE || m_state == M_WAIT || m_state == M_DONE) 
                                   : (sh_en_n !== 1'b0);

    reg yielding;
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) yielding <= 1'b0;
        else if (yield_req && safe_to_yield) yielding <= 1'b1;
        else if (!yield_req) yielding <= 1'b0;
    end

    // The DMA is only "active" (controlling local buses) if it is armed, 
    // past the setup phase, and NOT currently yielding to the Z80.
    assign dma_active = dma_go && !yielding;

    // ==========================================
    // 4. MASTER STATE MACHINE
    // ==========================================
    // If programmed as Master, this node generates the clocking strokes (sh_stb_n)
    // and controls the shadow bus direction lines.
    localparam M_IDLE   = 3'd0;
    localparam M_START  = 3'd1;
    localparam M_STROBE = 3'd2;
    localparam M_INC    = 3'd3;
    localparam M_WAIT   = 3'd4; // Safe resting state to park the state machine during a yield
    localparam M_DONE   = 3'd5;

    reg [2:0] m_state;

    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            m_state <= M_IDLE;
            int_pending <= 1'b0;
        end else begin
            // Z80 INTACK cycle auto-clears the interrupt flag
            if (intack_clear) int_pending <= 1'b0;

            if (is_master) begin
                case (m_state)
                    // LOOKAHEAD SHIELD: Do not step out of safe states if a yield is requested!
                    M_IDLE:   if (dma_go && !yielding && !yield_req) m_state <= M_START; 
                    M_START:  m_state <= M_STROBE;
                    M_STROBE: m_state <= (byte_count == 8'h00) ? M_DONE : M_INC;
                    M_INC:    m_state <= M_WAIT; // M_INC is now exactly 1 clock cycle long
                    
                    // LOOKAHEAD SHIELD: Prevent tearing if sh_busy_n drops asynchronously
                    M_WAIT:   if (!yielding && !yield_req) m_state <= M_STROBE; 
                    
                    M_DONE:   begin
                        int_pending <= 1'b1; // Trigger Z80 Interrupt upon finishing!
                        m_state <= M_IDLE;
                    end
                    default:  m_state <= M_IDLE;
                endcase
            end
        end
    end

    // ==========================================
    // 5. SLAVE TRACKING LOGIC
    // ==========================================
    // PERFECT SYNCHRONIZATION: Because MCLK is shared across the backplane, 
    // we do not need a multi-stage synchronizer that introduces lag. By evaluating 
    // the active-low signals directly, the Slave increments its address on the 
    // exact same clock edge as the Master!
    wire local_inc  = is_master ? (m_state == M_INC)  : (!is_master && dma_go && !sh_inc_n);
    wire local_done = is_master ? (m_state == M_DONE) : (!is_master && dma_go && !sh_done_n);

    // ==========================================
    // 6. PHYSICAL TRANSCEIVER AND BUS ROUTING
    // ==========================================
    // PHYSICAL A/B WIRING RULE FOR 74ABT245:
    // A-Side is connected to the Backplane. B-Side is connected to the CPLD.
    // DIR = 0 : Data flows from B to A (Drive out to Backplane)
    // DIR = 1 : Data flows from A to B (Listen to Backplane)
    assign sh_c_dir  = !is_master; 

    // Master dynamically pulses the strobe. Slave just passes the incoming strobe down.
    // Decouple the generation from the bus reading to satisfy Yosys static analysis
    wire generated_stb_n = !(m_state == M_STROBE);
    wire int_sh_stb_n    = is_master ? generated_stb_n : sh_stb_n;

    // By qualifying the shadow controls with dma_active, the Master cleanly floats 
    // the backplane the exact nanosecond it enters a yield, signaling the Slave.
    assign sh_en_n   = (is_master && dma_active && m_state != M_IDLE) ? 1'b0 : 1'bz; 
    assign sh_rw_n   = (is_master && dma_active && m_state != M_IDLE) ? dir_to_bus : 1'bz;
    assign sh_stb_n  = (is_master && dma_active && m_state != M_IDLE) ? generated_stb_n : 1'bz;

    // Only pulse INC low during the 1-cycle M_INC state. Keep it high during M_WAIT.
    assign sh_inc_n  = (is_master && dma_active && m_state == M_INC) ? 1'b0 : 1'bz;
    assign sh_done_n = (is_master && dma_active && m_state == M_DONE) ? 1'b0 : 1'bz;

    // Local Memory logic:
    //assign dma_phys_addr = phys_addr;
    assign dma_phys_addr = {phys_addr_high, 4'b0000, phys_addr_low};

    assign dma_data_out  = dma_data_in; 
    
    // Read local RAM if dir_to_bus == 0. Write local RAM if dir_to_bus == 1.
    assign dma_local_oe_n = (dma_active && dir_to_bus == 1'b0) ? 1'b0 : 1'b1;
    assign dma_local_we_n = (dma_active && dir_to_bus == 1'b1) ? int_sh_stb_n : 1'b1;


    // ==========================================
    // 6. PHYSICAL TRANSCEIVER AND BUS ROUTING
    // ==========================================

    // By qualifying the shadow controls with dma_active, the Master cleanly floats 
    // the backplane the exact nanosecond it enters a yield, signaling the Slave.

endmodule
