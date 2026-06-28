/*
 * File:   hal.h
 * Author: Marc Mosko
 * Description: Hardware Abstraction Layer for Zx50 Bus Probe Rev B.
 * Provides an interface to the PIC18F27Q43 microcontroller and its peripherals,
 * including the three MCP23S17 SPI I/O expanders.
 */

#ifndef HAL_H
#define	HAL_H

#include <stdint.h>
#include "pins.h"

#ifdef	__cplusplus
extern "C" {
#endif

#define _XTAL_FREQ 64000000

// ==========================================
// MCP23S17 I/O Expander Constants
// ==========================================

// --- Hardware Addresses ---
// These are set by the A0, A1, A2 pins on the schematic.
#define EXP_ADDR_HW_ADDR   0x00  // U1: Z80 Address Bus (A0-A15)
#define EXP_DATA_HW_ADDR   0x02  // U21: Z80 Data Bus (D0-D7) & Control
#define EXP_SHADOW_HW_ADDR 0x01  // U13: Shadow Bus (SD0-SD7) & Control

// --- Register Map (with BANK=0) ---
#define REG_IODIRA 0x00 // Data Direction Port A (1=Input, 0=Output)
#define REG_IODIRB 0x01 // Data Direction Port B
#define REG_IPOLA  0x02 // Input Polarity Port A
#define REG_IPOLB  0x03 // Input Polarity Port B
#define REG_GPINTENA 0x04 // Interrupt-on-Change Enable Port A
#define REG_GPINTENB 0x05 // Interrupt-on-Change Enable Port B
#define REG_DEFVALA 0x06 // Default Value for Interrupt-on-Change Port A
#define REG_DEFVALB 0x07 // Default Value for Interrupt-on-Change Port B
#define REG_INTCONA 0x08 // Interrupt Control Port A
#define REG_INTCONB 0x09 // Interrupt Control Port B
#define REG_IOCON  0x0A // Configuration Register
#define REG_GPPUA  0x0C // Pull-Up Resistor Enable Port A
#define REG_GPPUB  0x0D // Pull-Up Resistor Enable Port B
#define REG_INTFA  0x0E // Interrupt Flag Port A
#define REG_INTFB  0x0F // Interrupt Flag Port B
#define REG_INTCAPA 0x10 // Interrupt Captured Value Port A
#define REG_INTCAPB 0x11 // Interrupt Captured Value Port B
#define REG_GPIOA  0x12 // Port A Value
#define REG_GPIOB  0x13 // Port B Value
#define REG_OLATA  0x14 // Output Latch Port A
#define REG_OLATB  0x15 // Output Latch Port B

// ==========================================
// System & Peripheral Initialization
// ==========================================
void System_Init(void);

// ==========================================
// UART Communication
// ==========================================
void UART_Write(uint8_t data);
int UART_Read(uint8_t *output);
uint8_t UART_Data_Available(void);

// ==========================================
// SPI & I/O Expander Communication
// ==========================================
uint8_t SPI_Transfer(uint8_t data);

void Expander_Write(uint8_t hw_addr, uint8_t reg_addr, uint8_t data);
uint8_t Expander_Read(uint8_t hw_addr, uint8_t reg_addr);

#ifdef	__cplusplus
}
#endif

#endif	/* HAL_H */
