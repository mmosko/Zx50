/* 
 * File:   pins.h
 * Author: Marc Mosko
 * Description: Hardware Abstraction Layer for Zx50 Bus Probe Rev B.
 * Defines meaningful names for all PIC18F27Q43 I/O pins and the
 * three MCP23S17 I/O expanders based on the schematic.
 */

#ifndef PINS_H
#define	PINS_H

#include <xc.h>

// ==========================================
// PIC18F27Q43 Direct Pin Definitions
// ==========================================

// --- SPI Bus to I/O Expanders ---
#define SPI_SCK_DIR         TRISCbits.TRISC3
#define SPI_SDO_DIR         TRISCbits.TRISC5
#define SPI_SDI_DIR         TRISCbits.TRISC4

// --- I/O Expander Chip Selects ---
#define EXP_ADDR_CS_DIR     TRISAbits.TRISA5
#define EXP_ADDR_CS_LAT     LATAbits.LATA5

#define EXP_DATA_CS_DIR     TRISAbits.TRISA4
#define EXP_DATA_CS_LAT     LATAbits.LATA4

#define EXP_SHADOW_CS_DIR   TRISAbits.TRISA3
#define EXP_SHADOW_CS_LAT   LATAbits.LATA3

// --- I/O Expander Reset ---
#define EXP_RESET_DIR       TRISAbits.TRISA2
#define EXP_RESET_LAT       LATAbits.LATA2

// --- Communication with Raspberry Pi Pico ---
#define PICO_TX_DIR         TRISCbits.TRISC6 // PIC's TX pin (connects to Pico's RX)
#define PICO_RX_DIR         TRISCbits.TRISC7 // PIC's RX pin (connects to Pico's TX)
#define PICO_INT_DIR        TRISCbits.TRISC0 // Interrupt pin to signal the Pico
#define PICO_INT_LAT        LATCbits.LATC0

// --- Z80 Bus Control (Directly from PIC) ---
#define Z80_BUSRQ_DIR       TRISBbits.TRISB3
#define Z80_BUSRQ_LAT       LATBbits.LATB3

#define Z80_WAIT_DIR        TRISBbits.TRISB1
#define Z80_WAIT_LAT        LATBbits.LATB1
#define Z80_WAIT_VAL        PORTBbits.RB1

#define Z80_INT_DIR         TRISBbits.TRISB0
#define Z80_INT_LAT         LATBbits.LATB0
#define Z80_INT_VAL         PORTBbits.RB0

#define AUX_PIN_VAL         PORTBbits.RB4

// --- Clock Generation ---
#define Z80_CLK_DIR         TRISCbits.TRISC1 // Output for the Z80 clock signal
#define Z80_CLK_LAT         LATCbits.LATC1
#define Z80_MCLK_DIR        TRISCbits.TRISC2 // Output for the master clock
#define Z80_MCLK_LAT        LATCbits.LATC2

// --- Programming Pins ---
#define PGC_DIR             TRISBbits.TRISB6
#define PGD_DIR             TRISBbits.TRISB7
#define MCLR_PIN            RE3

// ==========================================
// MCP23S17 I/O Expander Pin Definitions
// These are not physical PIC pins, but rather the port pins on the expanders.
// The firmware will access these via SPI commands.
// ==========================================

// --- U1: Z80 Address Bus (A0-A15) ---
// GPA for A0-A7, GPB for A8-A15
#define EXP_ADDR_PORTA      GPIOA
#define EXP_ADDR_PORTB      GPIOB

// --- U21: Z80 Data Bus (D0-D7) & Control Signals ---
// GPA for D0-D7
#define EXP_DATA_PORTA      GPIOA
// GPB for control signals
#define EXP_DATA_PORTB      GPIOB
#define Z80_RD_N_PIN        0 // GPB0
#define Z80_WR_N_PIN        1 // GPB1
#define Z80_MREQ_N_PIN      2 // GPB2
#define Z80_IORQ_N_PIN      3 // GPB3
#define Z80_M1_N_PIN        4 // GPB4
#define Z80_RESET_N_PIN     5 // GPB5
#define Z80_BUSAK_N_PIN     6 // GPB6
#define Z80_RFSH_N_PIN      7 // GPB7

// --- U13: Shadow Bus (SD0-SD7) & Control Signals ---
// GPA for SD0-SD7
#define EXP_SHADOW_DATAPORT GPIOA
// GPB for shadow control signals
#define EXP_SHADOW_CTRLPORT GPIOB
#define SH_STB_N_PIN        0 // GPB0
#define SH_INC_N_PIN        1 // GPB1
#define SH_EN_N_PIN         2 // GPB2
#define SH_RW_PIN           3 // GPB3
#define SH_DONE_N_PIN       4 // GPB4
#define SH_BUSY_N_PIN       5 // GPB5

#endif	/* PINS_H */
