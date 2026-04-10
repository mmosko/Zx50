`timescale 1ns/1ps

/***************************************************************************************
 * MODULE: zx50_mmu_sram (Optimized: Fitter-Safe Async Reset & Direct Muxing)
 ***************************************************************************************/

module zx50_mmu_sram (
    input wire mclk,              
    input wire reset_n,           
    input wire boot_en_n,         
    
    input wire [7:0] z80_addr_hi,   
    
    input wire mmu_snoop_wr,      
    input wire mmu_direct_wr, 
    
    input wire z80_mreq_n, 

    output wire [3:0] atl_addr,   
    output wire atl_we_n,         
    output wire atl_oe_n,         
    
    output wire active,           
    output wire z80_card_hit,     
    output wire is_busy,          
 
    output wire cpu_updating,     

    output wire is_rom_enabled    
);
    
    reg [15:0] page_ownership;
    reg        sync_we;
    reg        rom_enabled;
    reg        is_booted;

    assign is_rom_enabled = rom_enabled;

    // FITTER OPTIMIZATION: We must use a pure, static async reset (0) so Yosys maps 
    // these to standard DFFAR cells, avoiding the illegal $_ALDFFE_PNP_ cell.
    always @(posedge mclk or negedge reset_n) begin
        if (!reset_n) begin
            page_ownership  <= 16'h0000;
            sync_we         <= 1'b0;
            rom_enabled     <= 1'b0;
            is_booted       <= 1'b0; // Start un-booted
        end else begin
            
            // On the very first clock cycle after reset, we dynamically load the boot configuration.
            if (!is_booted) begin
                rom_enabled     <= !boot_en_n;
                page_ownership  <= (!boot_en_n) ? 16'h00FF : 16'h0000;
                is_booted       <= 1'b1;
            end else begin
                // Normal Operation
                if (mmu_snoop_wr) begin
                    if (mmu_direct_wr) begin
                        page_ownership[z80_addr_hi[3:0]] <= 1'b1;
                        if (z80_addr_hi[3] == 1'b0) begin 
                            rom_enabled <= 1'b0;
                        end
                    end else begin
                        page_ownership[z80_addr_hi[3:0]] <= 1'b0;
                    end
                end
                sync_we <= mmu_direct_wr;
            end
        end
    end

    assign cpu_updating = mmu_direct_wr;
    assign atl_addr = mmu_direct_wr ? z80_addr_hi[3:0] : z80_addr_hi[7:4];
    assign atl_we_n = !sync_we;
    assign atl_oe_n = mmu_direct_wr ? 1'b1 : 1'b0;

    // FITTER OPTIMIZATION:
    // Replaced the barrel shifter (16'b1 << addr) and reduction OR.
    // Direct indexing creates a clean, low fan-in 16:1 multiplexer in the routing pool.
    wire current_page_owned = page_ownership[z80_addr_hi[7:4]];
    
    // Do not assert active until the 1-cycle boot logic finishes!
    assign active = (is_booted && !z80_mreq_n && current_page_owned);
    assign z80_card_hit = active || mmu_direct_wr;
    assign is_busy = mmu_direct_wr || !is_booted;

endmodule

