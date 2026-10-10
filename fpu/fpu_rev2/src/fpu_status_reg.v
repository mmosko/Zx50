`timescale 1ns/1ps

/***************************************************************************************
* MODULE: fpu_status_reg
* DESCRIPTION:
* Masked Status Register Module for Zx50 FPU Rev 2.
*
* 8-Bit STATUS Register Field Definitions:
*   Bit 7: BSY - Engine Busy Flag
*   Bit 6: D   - Difference Sign Flag (sign_A ^ sign_B)
*   Bit 5: S   - Sign Flag (1 = Negative, 0 = Positive)
*   Bit 4: C   - Unsigned Carry / Borrow Flag
*   Bit 3: V   - Signed Two's-Complement Overflow Flag
*   Bit 2: U   - Exponent / Stack Underflow Flag
*   Bit 1: ERR - Error Flag (e.g., Divide-by-Zero / Stack Overflow)
*   Bit 0: Z   - Zero Flag
*
* Masked Write Functionality:
* On posedge fclk when 'we' is asserted, each bit [i] of status_out updates to
* status_in[i] IF AND ONLY IF write_mask[i] == 1. Unmasked bits remain unchanged.
***************************************************************************************/

module fpu_status_reg (
    input  wire        fclk,          // FPU core high-speed clock
    input  wire        fpu_reset_n,   // Active-LOW core reset

    input  wire [7:0]  status_in,     // Candidate status bits (RES_STATUS)
    input  wire [7:0]  write_mask,    // Bit-wise write mask (STATUS_WR_SEL)
    input  wire        we,            // Global status write enable pulse (EXEC_WB)

    output reg  [7:0]  status_out,    // Full 8-bit STATUS byte

    // Individual flag output taps for direct branch condition routing
    // output wire        flag_bsy,      // Bit 7
    // output wire        flag_d,        // Bit 6
    // output wire        flag_s,        // Bit 5
    // output wire        flag_c,        // Bit 4
    // output wire        flag_v,        // Bit 3
    // output wire        flag_u,        // Bit 2
    // output wire        flag_err,      // Bit 1
    // output wire        flag_z         // Bit 0
);

    // Individual flag convenience breakouts
    // assign flag_bsy = status_out[7];
    // assign flag_d   = status_out[6];
    // assign flag_s   = status_out[5];
    // assign flag_c   = status_out[4];
    // assign flag_v   = status_out[3];
    // assign flag_u   = status_out[2];
    // assign flag_err = status_out[1];
    // assign flag_z   = status_out[0];

    // Synchronous Bit-Masked Write Logic
    always @(posedge fclk or negedge fpu_reset_n) begin
        if (!fpu_reset_n) begin
            status_out <= 8'h00;
        end else if (we) begin
            // Bitwise multiplex: (Current_Bit & ~Mask) | (New_Bit & Mask)
            status_out <= (status_out & ~write_mask) | (status_in & write_mask);
        end
    end

endmodule
