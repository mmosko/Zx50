`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_dma
 * DESCRIPTION: Universal Shadow Bus Node
 * This module acts as a highly specialized Block DMA controller that negotiates 
 * transfers across a shared physical backplane without Z80 CPU intervention.
 * It decodes a bit-packed 24-bit instruction set mapped to a dynamic I/O port,
 * bypassing the local MMU to generate a full 20-bit physical address.
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
    inout  wire shd_en_n,
    inout  wire shd_rw_n,
    inout  wire shd_inc_n,
    inout  wire shd_stb_n,
    inout  wire shd_done_n,

    // --- Internal Status & Interrupts ---
    output wire dma_active, 
    output wire shd_c_dir,
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
    wire opcode         = z80_addr[15];
    wire [14:0] operand = {z80_addr[14:8], z80_data_in[7:0]};

    reg [19:0] phys_addr;
    reg [7:0]  byte_count;
    reg is_master;
    reg dir_to_bus;     
    reg transfer_armed;

    assign dma_dir_to_bus = dir_to_bus;
    assign dma_is_master  = is_master;

    // ==========================================
    // 2. CONFIGURATION REGISTER LATCHING
    // ==========================================
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            phys_addr      <= 20'h00000;
            byte_count     <= 8'h00;
            is_master      <= 1'b0;
            dir_to_bus     <= 1'b0;
            transfer_armed <= 1'b0;
        end else if (z80_io_write) begin
            if (opcode == 1'b0) begin
                // OPCODE 0: Define Role and Lower Address
                is_master        <= operand[14];
                dir_to_bus       <= operand[13];
                phys_addr[12:0]  <= operand[12:0];
            end else begin
                // OPCODE 1: Define Upper Address, Count, and Arm the transfer
                byte_count       <= operand[14:7];
                phys_addr[19:13] <= operand[6:0]; 
                transfer_armed   <= 1'b1;         
            end
        end else if (local_inc) begin
            // Hardware auto-increment while the DMA burst is running
            phys_addr  <= phys_addr + 1'b1;
            byte_count <= byte_count - 1'b1;
        end else if (local_done) begin
            // Clear the armed flag when the transfer fully completes
            transfer_armed <= 1'b0;
        end
    end

    // ==========================================
    // 3. THE "ARM AND WAIT" SYNCHRONIZER
    // ==========================================
    // CRITICAL: We cannot let the DMA hijack the bus while the Z80 is still 
    // actively holding IORQ low from the Opcode 1 write. If we do, the CPLD 
    // transceivers will instantly reverse and fight the Z80 data bus!
    // We wait for z80_iorq_n to return to HIGH (1) before we assert dma_active.
    wire dma_go = transfer_armed && z80_iorq_n;
    assign dma_active = dma_go;

    // ==========================================
    // 4. MASTER STATE MACHINE
    // ==========================================
    // If programmed as Master, this node generates the clocking strokes (shd_stb_n)
    // and controls the shadow bus direction lines.
    localparam M_IDLE   = 3'd0;
    localparam M_START  = 3'd1;
    localparam M_STROBE = 3'd2;
    localparam M_INC    = 3'd3;
    localparam M_DONE   = 3'd4;

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
                    M_IDLE:   if (dma_go) m_state <= M_START; 
                    M_START:  m_state <= M_STROBE;
                    M_STROBE: m_state <= (byte_count == 8'h00) ? M_DONE : M_INC;
                    M_INC:    m_state <= M_STROBE;
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
    // If programmed as Slave, this node listens to the backplane. Because backplane 
    // signals are asynchronous to our local MCLK, we use a 2-stage shift register 
    // to safely detect the falling edges of the incoming strobe lines.
    reg [1:0] sync_inc, sync_done;
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            sync_inc  <= 2'b11; sync_done <= 2'b11;
        end else begin
            sync_inc  <= {sync_inc[0], shd_inc_n};
            sync_done <= {sync_done[0], shd_done_n};
        end
    end

    wire slave_inc_edge  = (sync_inc == 2'b10);  
    wire slave_done_edge = (sync_done == 2'b10); 

    // ==========================================
    // 5. SLAVE TRACKING LOGIC
    // ==========================================
    // Because MCLK is shared across the backplane, 
    // we do not need a multi-stage synchronizer that introduces lag. By evaluating 
    // the active-low signals directly, the Slave increments its address on the 
    // exact same clock edge as the Master!
    wire local_inc  = is_master ? (m_state == M_INC)  : (!is_master && dma_go && !shd_inc_n);
    wire local_done = is_master ? (m_state == M_DONE) : (!is_master && dma_go && !shd_done_n);


    // ==========================================
    // 6. PHYSICAL TRANSCEIVER AND BUS ROUTING
    // ==========================================
    
    // PHYSICAL A/B WIRING RULE FOR 74ABT245:
    // A-Side is connected to the Backplane. B-Side is connected to the CPLD.
    // DIR = 0 : Data flows from B to A (Drive out to Backplane)
    // DIR = 1 : Data flows from A to B (Listen to Backplane)
    // Therefore, the Master must drive (0), and the Slave must listen (1).
    assign shd_c_dir  = !is_master; 

    // Master dynamically pulses the strobe. Slave just passes the incoming strobe down.
    wire int_shd_stb_n = is_master ? !(m_state == M_STROBE) : shd_stb_n;

    // Master strictly drives the shadow bus control lines. Slave floats them (1'bz).
    assign shd_en_n   = (is_master && m_state != M_IDLE) ? 1'b0 : 1'bz;
    assign shd_rw_n   = (is_master && m_state != M_IDLE) ? dir_to_bus : 1'bz;
    assign shd_stb_n  = (is_master && m_state != M_IDLE) ? int_shd_stb_n : 1'bz;
    assign shd_inc_n  = (is_master && m_state == M_INC) ? 1'b0 : 1'bz;
    assign shd_done_n = (is_master && m_state == M_DONE) ? 1'b0 : 1'bz;

    // Local Memory logic:
    assign dma_phys_addr = phys_addr;
    assign dma_data_out  = dma_data_in; 
    
    // Read local RAM if dir_to_bus == 0. Write local RAM if dir_to_bus == 1.
    // CRITICAL: We bind the local RAM write-enable tightly to the shadow strobe 
    // so the physical SRAM chips latch the data exactly when it is valid.
    assign dma_local_oe_n = (dma_active && dir_to_bus == 1'b0) ? 1'b0 : 1'b1;
    assign dma_local_we_n = (dma_active && dir_to_bus == 1'b1) ? int_shd_stb_n : 1'b1;

endmodule