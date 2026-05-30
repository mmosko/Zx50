#include <xc.h>
#include <stdbool.h>
#include "clock.h"
#include "pins.h"
#include "command_queue.h"

static bool synchronized_step_running = false;
static bool free_run_running = false;

// ==========================================
// Initialization
// ==========================================

void Z80_Clock_Init(void) {
    // =====================================================================
    // 1. PPS (PERIPHERAL PIN SELECT) ROUTING
    // =====================================================================

    // This is done when one starts the free-running clock.
    
    // =====================================================================
    // 2. MASTER CLOCK (MCLK) -> PWM1 (4 MHz)
    // =====================================================================
    PWM1CLK = 0x02;       // Clock source = Fosc (64MHz)
    PWM1PR = 15;          // Period = 16 ticks (0 to 15)

    PWM1S1P1 = 0;         // Output goes HIGH at tick 0
    PWM1S1P2 = 8;         // Output goes LOW at tick 8 (50% Duty Cycle)

    PWM1S1CFG = 0x03;     // ?? THE REAL FIX: Variable-Aligned Mode (MODE = 011)
    
    // =====================================================================
    // 3. Z80 CLOCK (ZCLK) -> PWM2 (1 MHz)
    // =====================================================================
    PWM2CLK = 0x02;       // Clock source = Fosc (64MHz)
    PWM2PR = 63;          // Period = 64 ticks (0 to 63)

    // ALIGNMENT MAGIC:
    PWM2S1P1 = 36;        // Output goes HIGH
    PWM2S1P2 = 4;         // Output goes LOW (Aligned with MCLK falling edge)

    PWM2S1CFG = 0x03;     // ?? THE REAL FIX: Variable-Aligned Mode (MODE = 011)
    // =====================================================================
    // 4. STEPPED CLOCK (Timer 0)
    // =====================================================================
    // Turn on Timer 0 @ 1KHz permanently.  We use for the SYNC clock
    // and for our heartbeat timer.
    T0CON0 = 0x90;
    T0CON1 = 0x43;
    TMR0H = 0xF8;
    TMR0L = 0x30;
    
    // Q43 uses PIR3 for TMR0
    PIR3bits.TMR0IF = 0;
    PIE3bits.TMR0IE = 1;
    INTCON0bits.GIE = 1;
}

// ==========================================
// Public Clock Control API
// ==========================================

void Z80_Clock_Start_FreeRun(void) {
    Z80_Clock_Stop_Synchronized_Step();
    free_run_running = true;

    // Ensure pins are outputs
    TRISCbits.TRISC1 = 0;
    TRISCbits.TRISC2 = 0;

    // Reconnect the pins to the PWM hardware
    RC2PPS = 0x18; // PWM1
    RC1PPS = 0x1A; // PWM2

    // Enable the PWM Modules
    PWM1CONbits.EN = 1;
    PWM2CONbits.EN = 1;
}

void Z80_Clock_Stop_FreeRun(void) {
    free_run_running = false;

    // Disable the PWM Modules
    PWM1CONbits.EN = 0;
    PWM2CONbits.EN = 0;

    // Disconnect the PWMs so the LAT registers work again!
    RC1PPS = 0x00; 
    RC2PPS = 0x00; 

    // Revert pins to normal GPIO and hold them LOW
    TRISCbits.TRISC1 = 0;
    TRISCbits.TRISC2 = 0;
    Z80_CLK_LAT = 0;
    Z80_MCLK_LAT = 0;
}

void Z80_Clock_Start_Synchronized_Step(void) {
    Z80_Clock_Stop_FreeRun();
    synchronized_step_running = true;
}

void Z80_Clock_Stop_Synchronized_Step(void) {
    synchronized_step_running = false;
}

void Z80_Clock_Manual_Pulse(void) {
    CQ_Dispatch_Cycle();
}

void Z80_Generate_Single_Pulse(void) {
    Z80_MCLK_LAT = 1; NOP();
    Z80_MCLK_LAT = 0; NOP();
    Z80_CLK_LAT = 1;

    Z80_MCLK_LAT = 1; NOP();
    Z80_MCLK_LAT = 0; NOP();

    Z80_MCLK_LAT = 1; NOP();
    Z80_MCLK_LAT = 0; NOP();
    Z80_CLK_LAT = 0;

    Z80_MCLK_LAT = 1; NOP();
    Z80_MCLK_LAT = 0; NOP();
}

// ==========================================
// Interrupt Service Routine
// ==========================================
void __interrupt() System_ISR(void) {
    static uint16_t heartbeat_ms = 0;

    if (PIR3bits.TMR0IF) {
        PIR3bits.TMR0IF = 0;
        TMR0H = 0xF8;
        TMR0L = 0x30;

        // 1. Z80 Clock Management
        if (synchronized_step_running) {
            CQ_Dispatch_Cycle();
        }

        // 2. Heartbeat LED Management
        if (free_run_running || synchronized_step_running) {
            heartbeat_ms++;

            // 1000ms toggle gives a true 2-second period (1 sec ON, 1 sec OFF)
            if (heartbeat_ms >= 1000) {
                heartbeat_ms = 0;
                LATBbits.LATB5 = ~LATBbits.LATB5; // Toggle the LED
            }
        } else {
            // Bus is idle: Reset counter and force LED OFF (Active Low = 1)
            heartbeat_ms = 0;
            LATBbits.LATB5 = 1;
        }
    }
}