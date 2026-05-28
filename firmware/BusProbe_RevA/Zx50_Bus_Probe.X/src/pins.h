/* 
 * File:   pins.h
 * Author: Marc Mosko
 * Description: Hardware Abstraction Layer for Zx50 Bus Probe Rev A.
 * Defines meaningful names for all PIC18F4620 I/O pins based on schematic nets.
 */

#ifndef PINS_H
#define	PINS_H

#include <xc.h>

// ==========================================
// Z80 DATA BUS (Transceiver U6)
// ==========================================
// Directly connected to PORTD
// Control the DIRection, the LATch, and the VALue
#define Z80_DATA_DIR       TRISD
#define Z80_DATA_LAT       LATD
#define Z80_DATA_VAL       PORTD

// ==========================================
// TRANSCEIVER CONTROLS (U6 Data, U7 Control)
// ==========================================
// U7 Control Transceiver
#define XCVR_CTRL_OE_DIR   TRISAbits.TRISA0
#define XCVR_CTRL_OE_LAT   LATAbits.LATA0
#define XCVR_CTRL_DIR_DIR  TRISAbits.TRISA1
#define XCVR_CTRL_DIR_LAT  LATAbits.LATA1

// U6 Data Transceiver
#define XCVR_DATA_OE_DIR   TRISAbits.TRISA2
#define XCVR_DATA_OE_LAT   LATAbits.LATA2
#define XCVR_DATA_DIR_DIR  TRISAbits.TRISA3
#define XCVR_DATA_DIR_LAT  LATAbits.LATA3

// ==========================================
// Z80 CONTROL BUS (Via U7 Transceiver)
// ==========================================
#define Z80_RD_DIR         TRISBbits.TRISB5
#define Z80_RD_LAT         LATBbits.LATB5

#define Z80_WR_DIR         TRISEbits.TRISE0
#define Z80_WR_LAT         LATEbits.LATE0

#define Z80_MREQ_DIR       TRISBbits.TRISB3
#define Z80_MREQ_LAT       LATBbits.LATB3

#define Z80_IORQ_DIR       TRISBbits.TRISB4
#define Z80_IORQ_LAT       LATBbits.LATB4

#define Z80_M1_DIR         TRISEbits.TRISE1
#define Z80_M1_LAT         LATEbits.LATE1

#define Z80_RESET_DIR      TRISEbits.TRISE2
#define Z80_RESET_LAT      LATEbits.LATE2

// ==========================================
// Z80 DIRECT INPUTS (Bypassing Transceivers)
// ==========================================
#define Z80_INT_DIR        TRISBbits.TRISB0
#define Z80_INT_VAL        PORTBbits.RB0

#define Z80_WAIT_DIR       TRISBbits.TRISB1
#define Z80_WAIT_VAL       PORTBbits.RB1
#define Z80_WAIT_LAT       LATBbits.LATB1

// ==========================================
// SPI & EXPANDER CONTROLS (U1, U13)
// ==========================================
#define EXP_RESET_DIR      TRISAbits.TRISA4
#define EXP_RESET_LAT      LATAbits.LATA4

#define SPI_CS_DIR         TRISAbits.TRISA5
#define SPI_CS_LAT         LATAbits.LATA5

// SPI Hardware Pins (Managed by SSP Module, but good to define)
#define SPI_SCK_DIR        TRISCbits.TRISC3
#define SPI_SDI_DIR        TRISCbits.TRISC4
#define SPI_SDO_DIR        TRISCbits.TRISC5

// ==========================================
// UART COMMUNICATON
// ==========================================
// UART Hardware Pins (Managed by EUSART Module)
#define UART_TX_DIR        TRISCbits.TRISC6
#define UART_RX_DIR        TRISCbits.TRISC7

// ==========================================
// CLOCKS & AUXILIARY
// ==========================================
#define AUX_PIN_DIR        TRISCbits.TRISC0
#define AUX_PIN_LAT        LATCbits.LATC0
#define AUX_PIN_VAL        PORTCbits.RC0

#define MCLK_PIN_DIR       TRISCbits.TRISC1
#define MCLK_PIN_LAT       LATCbits.LATC1

#define CLK_PIN_DIR        TRISCbits.TRISC2
#define CLK_PIN_LAT        LATCbits.LATC2

// ==========================================
// SHADOW RAM CONTROLS
// ==========================================
#define SHADOW_BUSY_DIR    TRISBbits.TRISB2
#define SHADOW_BUSY_VAL    PORTBbits.RB2
#define SHADOW_BUSY_LAT    PORTBbits.LATB2

#endif	/* PINS_H */