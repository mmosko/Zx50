`timescale 1ns/1ps

module zx50_clock (
    output reg mclk,
    output reg zclk
);
    // --- Global Frequency Definitions ---
    // Defined as half-periods in nanoseconds.
    // MCLK = 36 MHz -> Period = 27.77ns -> Half = 13.88ns
    // ZCLK = 8 MHz  -> Period = 125.0ns -> Half = 62.5ns
    
    parameter MCLK_HALF_PERIOD = 13.88; 
    parameter ZCLK_HALF_PERIOD = 62.5;  

    initial begin
        mclk = 0;
        zclk = 0;
    end

    // Auto-generate the clocks
    always #MCLK_HALF_PERIOD mclk = ~mclk;
    always #ZCLK_HALF_PERIOD zclk = ~zclk;

    // ==========================================
    // Timing Utility Tasks
    // ==========================================
    
    // Usage: clk_gen.wait_mclk(5);
    task wait_mclk(input integer cycles);
        integer i;
        begin
            for (i = 0; i < cycles; i = i + 1) begin
                @(posedge mclk);
            end
        end
    endtask

    // Usage: clk_gen.wait_zclk(10);
    task wait_zclk(input integer cycles);
        integer i;
        begin
            for (i = 0; i < cycles; i = i + 1) begin
                @(posedge zclk);
            end
        end
    endtask

endmodule