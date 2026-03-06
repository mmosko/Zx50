`timescale 1ns/1ps

module zx50_dma (
    input  wire mclk,
    input  wire reset_n,

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
    
    // NEW INTERRUPT SIGNALS:
    output reg  int_pending,
    input  wire intack_clear
);

    localparam DMA_PORT = 8'h40; 

    wire z80_io_write = (!z80_iorq_n && !z80_wr_n && (z80_addr[7:0] == DMA_PORT));
    wire opcode       = z80_addr[15];
    wire [14:0] operand = {z80_addr[14:8], z80_data_in[7:0]};

    reg [19:0] phys_addr;
    reg [7:0]  byte_count;
    reg is_master;
    reg dir_to_bus;     
    reg transfer_armed;

    assign dma_dir_to_bus = dir_to_bus;

    // --- Register Configuration ---
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            phys_addr      <= 20'h00000;
            byte_count     <= 8'h00;
            is_master      <= 1'b0;
            dir_to_bus     <= 1'b0;
            transfer_armed <= 1'b0;
        end else if (z80_io_write) begin
            if (opcode == 1'b0) begin
                is_master        <= operand[14];
                dir_to_bus       <= operand[13];
                phys_addr[12:0]  <= operand[12:0];
            end else begin
                byte_count       <= operand[14:7];
                phys_addr[19:13] <= operand[6:0]; 
                transfer_armed   <= 1'b1;         
            end
        end else if (local_inc) begin
            phys_addr  <= phys_addr + 1'b1;
            byte_count <= byte_count - 1'b1;
        end else if (local_done) begin
            transfer_armed <= 1'b0;
        end
    end

    // --- MASTER State Machine & Interrupt generation ---
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
            // Handle clearing the interrupt from the Z80 INTACK cycle
            if (intack_clear) int_pending <= 1'b0;

            if (is_master) begin
                case (m_state)
                    M_IDLE:   if (transfer_armed) m_state <= M_START;
                    M_START:  m_state <= M_STROBE;
                    M_STROBE: m_state <= (byte_count == 8'h00) ? M_DONE : M_INC;
                    M_INC:    m_state <= M_STROBE;
                    M_DONE:   begin
                        int_pending <= 1'b1; // Raise Z80 Interrupt upon finishing!
                        m_state <= M_IDLE;
                    end
                    default:  m_state <= M_IDLE;
                endcase
            end
        end
    end

    // ... (SLAVE Tracking and Tristate logic remain identical to previous version) ...
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

    wire local_inc  = is_master ? (m_state == M_INC)  : (!is_master && transfer_armed && slave_inc_edge);
    wire local_done = is_master ? (m_state == M_DONE) : (!is_master && transfer_armed && slave_done_edge);

    assign shd_c_dir  = !is_master; 
    assign dma_active = transfer_armed; 

    wire int_shd_stb_n = is_master ? !(m_state == M_STROBE) : shd_stb_n;

    assign shd_en_n   = (is_master && m_state != M_IDLE) ? 1'b0 : 1'bz;
    assign shd_rw_n   = (is_master && m_state != M_IDLE) ? dir_to_bus : 1'bz;
    assign shd_stb_n  = (is_master && m_state != M_IDLE) ? int_shd_stb_n : 1'bz;
    assign shd_inc_n  = (is_master && m_state == M_INC) ? 1'b0 : 1'bz;
    assign shd_done_n = (is_master && m_state == M_DONE) ? 1'b0 : 1'bz;

    assign dma_phys_addr = phys_addr;
    assign dma_data_out  = dma_data_in; 
    assign dma_local_oe_n = (dma_active && dir_to_bus == 1'b0) ? 1'b0 : 1'b1;
    assign dma_local_we_n = (dma_active && dir_to_bus == 1'b1) ? int_shd_stb_n : 1'b1;

endmodule