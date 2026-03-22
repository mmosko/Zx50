#include <xc.h>
#include "clock.h"
#include "pins.h"

void Z80_Clock_Init(void) {
    // Initialize with PWM off and the clock pin driven LOW
    CCP1CONbits.CCP1M = 0x00; // Disable PWM module
    CLK_PIN_DIR = 0;          // Set RC2 as an output
    CLK_PIN_LAT = 0;          // Idle low
}

void Z80_Clock_Start_PWM(void) {
    CLK_PIN_DIR = 0; 
    PR2 = 7;
    CCPR1L = 4;           
    CCP1CONbits.DC1B = 0; 
    
    // Enable CCP1 in PWM Mode (Takes over RC2)
    CCP1CONbits.CCP1M = 0x0C; 
    
    // Turn on Timer2
    T2CON = 0x04; 
}

void Z80_Clock_Stop_PWM(void) {
    // Setting CCP1M to 0 disables the PWM module.
    // Control of RC2 is instantly handed back to the LATC2 register!
    CCP1CONbits.CCP1M = 0x00; 
    
    // Ensure the clock parks in a low, idle state
    CLK_PIN_DIR = 0;
    CLK_PIN_LAT = 0;
}

void Z80_Clock_Pulse(void) {
    // This ONLY works if Z80_Clock_Stop_PWM() was called first.
    CLK_PIN_LAT = 1;
    NOP(); // Add more NOPs if the Z80 needs a wider clock pulse
    CLK_PIN_LAT = 0;
}

void Z80_Clock_High(void) {
    CLK_PIN_LAT = 1;
}

void Z80_Clock_Low(void) {
    CLK_PIN_LAT = 0;
}