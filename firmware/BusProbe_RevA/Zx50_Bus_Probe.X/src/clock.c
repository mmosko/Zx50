#include <xc.h>
#include "clock.h"
#include "pins.h"
#include "command_queue.h"

/* * FLAG: use_dual_clock
 * --------------------
 * When set to 1, the bit-banged clock functions will generate a 4x MCLK 
 * signal on RC1 alongside the standard ZCLK signal on RC2. 
 * This is required for the Zx50 Memory Card's CPLD, which relies on 
 * a continuous MCLK to run its internal state machines (MMU, DMA, Arbiter) 
 * even when the Z80 bus is being stepped slowly.
 */
uint8_t use_dual_clock = 1; 

// Flag to track if auto-clocking is running
static uint8_t auto_clock_enabled = 0;

void Z80_Clock_Init(void) {
    // 1. Disable the hardware PWM modules so we have direct control over the pins
    CCP1CONbits.CCP1M = 0x00; // Disable CCP1 (used for ZCLK on RC2)
    CCP2CONbits.CCP2M = 0x00; // Disable CCP2 (used for MCLK on RC1)
    
    // 2. Initialize ZCLK (RC2) as an output and park it LOW
    CLK_PIN_DIR = 0;          
    CLK_PIN_LAT = 0;          
    
    // 3. Initialize MCLK (RC1) as an output and park it LOW
    MCLK_PIN_DIR = 0;         
    MCLK_PIN_LAT = 0;         
}

void Z80_Clock_Start_PWM(void) {
    /*
     * HARDWARE LIMITATION NOTE:
     * The PIC18F4620 has two PWM modules (CCP1 and CCP2), but they both 
     * share a single timebase (Timer2). Because of this, we cannot easily 
     * use hardware PWM to generate MCLK at 4x the frequency of ZCLK.
     * * This function currently only starts the ZCLK hardware PWM. 
     * If free-running MCLK is required in the future, an external clock 
     * divider or a tight assembly loop will be needed.
     */
    
    CLK_PIN_DIR = 0; 
    
    // Configure Timer2 for the desired ZCLK frequency
    PR2 = 7;
    CCPR1L = 4;           
    CCP1CONbits.DC1B = 0; 
    
    // Enable CCP1 in PWM Mode (This takes physical control of the RC2 pin)
    CCP1CONbits.CCP1M = 0x0C; 
    
    // Turn on Timer2 to start the clock output
    T2CON = 0x04; 
}

void Z80_Clock_Stop_PWM(void) {
    // Setting CCP1M to 0 disables the PWM module.
    // Physical control of the RC2 pin is instantly handed back to the LATC2 register.
    CCP1CONbits.CCP1M = 0x00; 
    
    // Ensure both clocks park in a safe, known LOW state
    CLK_PIN_DIR = 0;
    CLK_PIN_LAT = 0;
    
    MCLK_PIN_DIR = 0;
    MCLK_PIN_LAT = 0;
}

void Z80_Clock_High(void) {
    if (use_dual_clock) {
        /*
         * PHASE ALIGNMENT STRATEGY (T1/T3):
         * The CPLD samples Z80 control signals on the rising edge of MCLK 
         * (always @(posedge mclk)). To prevent race conditions, ZCLK must 
         * transition *between* MCLK rising edges. 
         * * We achieve this by toggling ZCLK immediately after MCLK falls.
         */
        
        // --- MCLK Cycle 1 ---
        MCLK_PIN_LAT = 1; NOP();
        MCLK_PIN_LAT = 0; NOP();
        
        // --- ZCLK Rising Edge ---
        // ZCLK goes HIGH. Because MCLK is currently LOW, ZCLK will be fully 
        // stable by the time the next MCLK rising edge hits the CPLD.
        CLK_PIN_LAT = 1;  
        
        // --- MCLK Cycle 2 ---
        MCLK_PIN_LAT = 1; NOP();
        MCLK_PIN_LAT = 0; NOP();
    } else {
        // Legacy single-clock mode
        CLK_PIN_LAT = 1;
    }
}

void Z80_Clock_Low(void) {
    if (use_dual_clock) {
        /*
         * PHASE ALIGNMENT STRATEGY (T2/T4):
         * Similar to the High phase, we generate 2 MCLK pulses, but we drop 
         * ZCLK LOW in the middle to maintain the 4x frequency ratio and 
         * proper edge trailing.
         */
         
        // --- MCLK Cycle 3 ---
        MCLK_PIN_LAT = 1; NOP();
        MCLK_PIN_LAT = 0; NOP();
        
        // --- ZCLK Falling Edge ---
        // ZCLK goes LOW. It is safely trailing the MCLK falling edge.
        CLK_PIN_LAT = 0;  
        
        // --- MCLK Cycle 4 ---
        MCLK_PIN_LAT = 1; NOP();
        MCLK_PIN_LAT = 0; NOP();
    } else {
        // Legacy single-clock mode
        CLK_PIN_LAT = 0;
    }
}

/* Convenience function to execute one complete Z80 T-State.
 * In dual-clock mode, this will output 1 full ZCLK cycle and 
 * 4 full MCLK cycles, properly interleaved.
 * 
 * This runs MCLK at about 110 KHz with a 4-cycle and about 45 Khz
 * between cycles (i.e. ZCLK is about 45 KHz).  It is not a regular
 * clock, there's a gap.
 */
void Z80_Clock_Pulse(void) {
    Z80_Clock_High();
    Z80_Clock_Low();
}

// ===================================
// Uses timer interrupt for 1KHz clock
// ===================================

void Z80_Clock_Start_Auto(void) {
    T0CON = 0x02;          // 16-bit mode, Prescaler 1:8, Timer OFF
    TMR0H = 0xFC;          // Write High byte first!
    TMR0L = 0x18;          // Write Low byte
    
    INTCONbits.TMR0IF = 0; // Clear the interrupt flag
    INTCONbits.TMR0IE = 1; // ENABLE Timer0 Interrupt
    INTCONbits.PEIE   = 1; // Enable Peripheral Interrupts
    INTCONbits.GIE    = 1; // ENABLE Global Interrupts
    
    auto_clock_enabled = 1;
    T0CONbits.TMR0ON = 1;  // Turn the timer ON
}

void Z80_Clock_Stop_Auto(void) {
    T0CONbits.TMR0ON = 0;  // Turn the timer OFF
    INTCONbits.TMR0IE = 0; // Disable the interrupt
    auto_clock_enabled = 0;
}

// ==========================================
// THE HIGH-PRIORITY INTERRUPT VECTOR
// ==========================================
void __interrupt() System_ISR(void) {
    
    // Check if Timer0 caused the interrupt
    if (INTCONbits.TMR0IE && INTCONbits.TMR0IF) {
        // 1. Clear the hardware flag immediately
        INTCONbits.TMR0IF = 0; 
        
        // 2. Reload the timer for the next 1kHz tick
        TMR0H = 0xFC;
        TMR0L = 0x18;
        
        // 3. Fire the clock pulse
        if (auto_clock_enabled) {
            CQ_Dispatch_Cycle();
        }
    }
}
