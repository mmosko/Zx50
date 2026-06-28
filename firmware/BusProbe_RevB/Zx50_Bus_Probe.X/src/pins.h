/* * File:   pins.h
 * Author: Marc Mosko
 * Description: Hardware Abstraction Layer for Zx50 Bus Probe Rev B.
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

// --- Expander SPI Chip Select (Shared) ---
#define EXP_CS_DIR          TRISAbits.TRISA5
#define EXP_CS_LAT          LATAbits.LATA5

// --- Expander Reset (Shared) ---
#define EXP_RESET_DIR       TRISAbits.TRISA4
#define EXP_RESET_LAT       LATAbits.LATA4

// --- Transceiver Controls (74ABT245) ---
// Data Bus Transceiver (U6)
#define DATA_XCVR_OE_DIR    TRISAbits.TRISA0
#define DATA_XCVR_OE_LAT    LATAbits.LATA0
#define DATA_XCVR_DIR_DIR   TRISAbits.TRISA1
#define DATA_XCVR_DIR_LAT   LATAbits.LATA1

// Address & Control Bus Transceivers (U7, U17, U19)
#define ADDR_XCVR_OE_DIR    TRISAbits.TRISA2
#define ADDR_XCVR_OE_LAT    LATAbits.LATA2
#define ADDR_XCVR_DIR_DIR   TRISAbits.TRISA3
#define ADDR_XCVR_DIR_LAT   LATAbits.LATA3

// Shadow Bus Transceivers (U22, U23)
#define SHADOW_XCVR_OE_DIR  TRISAbits.TRISA6
#define SHADOW_XCVR_OE_LAT  LATAbits.LATA6
#define SHADOW_XCVR_DIR_DIR TRISAbits.TRISA7
#define SHADOW_XCVR_DIR_LAT LATAbits.LATA7

// --- Communication with Raspberry Pi Pico ---
#define PICO_TX_DIR         TRISCbits.TRISC6 
#define PICO_RX_DIR         TRISCbits.TRISC7 
#define PICO_INT_DIR        TRISCbits.TRISC0 
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
#define Z80_CLK_DIR         TRISCbits.TRISC1 
#define Z80_CLK_LAT         LATCbits.LATC1
#define Z80_MCLK_DIR        TRISCbits.TRISC2 
#define Z80_MCLK_LAT        LATCbits.LATC2

// --- Programming Pins ---
#define PGC_DIR             TRISBbits.TRISB6
#define PGD_DIR             TRISBbits.TRISB7
#define MCLR_PIN            RE3

// ==========================================
// MCP23S17 I/O Expander Register Mapping
// ==========================================

// --- U1: Z80 Address Bus (A0-A15) ---
#define EXP_ADDR_PORTA      GPIOA
#define EXP_ADDR_PORTB      GPIOB

// --- U21: Z80 Data Bus (D0-D7) & Control Signals ---
#define EXP_DATA_PORTA      GPIOA
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
#define EXP_SHADOW_DATAPORT GPIOA
#define EXP_SHADOW_CTRLPORT GPIOB
#define SH_STB_N_PIN        0 // GPB0
#define SH_INC_N_PIN        1 // GPB1
#define SH_EN_N_PIN         2 // GPB2
#define SH_RW_PIN           3 // GPB3
#define SH_DONE_N_PIN       4 // GPB4
#define SH_BUSY_N_PIN       5 // GPB5

#endif	/* PINS_H */