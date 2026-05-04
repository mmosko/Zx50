/* * File:   hal.h
 * Author: Marc
 */

#ifndef HAL_H
#define	HAL_H

#include <stdint.h>

#ifdef	__cplusplus
extern "C" {
#endif

// ==========================================
// MCP23S17 Constants
// ==========================================
// Hardware Addresses (based on A0, A1, A2 pins)
#define U1_ADDR   0x00  // Address/Control Expander
#define U13_ADDR  0x01  // Shadow/Control Expander

// Register Map (Assuming BANK = 0 default)
#define REG_IODIRA 0x00 // Data Direction A (1=Input, 0=Output)
#define REG_IODIRB 0x01 // Data Direction B
#define REG_IOCON  0x0A // Configuration Register
#define REG_GPIOA  0x12 // Port A Value
#define REG_GPIOB  0x13 // Port B Value

// ==========================================
// Initialization Prototypes
// ==========================================
void System_Init(void);
void Clock_Init(void);
void GPIO_Init(void);
void UART_Init(void);
void SPI_Init(void);
void Expander_Init(void);
void Z80_Clock_Init(void);

// ==========================================
// Bus Control
// ==========================================
void Ghost(uint8_t param);

/*
 * Set RD WR, MREQ, IORQ all inactive
 */
void HAL_Control_Inactive();

// ==========================================
// Peripheral Prototypes
// ==========================================
void UART_Write(uint8_t data);

/**
 * @brief Reads a single byte from the UART hardware FIFO with strict safety guarantees.
 * * This function implements three critical safety mechanisms to prevent the PIC 
 * from deadlocking if the high-speed (1 Mbps) serial link drops bytes:
 * * 1. OERR Recovery: If the PIC is busy in an ISR and the hardware FIFO overflows, 
 * the UART hardware physically shuts down. This detects the error and resurrects it.
 * 2. Temporal Framing (Timeout): The Pico transmits 5-byte packets contiguously (zero gap). 
 * If the PIC accidentally locks onto a false 'SYNC' byte from a broken packet, 
 * it will wait forever for bytes that aren't coming. The timeout breaks this deadlock.
 * 3. FERR Recovery: Detects and discards electrically corrupted bytes (missing stop bit).
 * * @param output Pointer to store the successfully read byte.
 * @return int 0 on SUCCESS, 1 on ERROR (Overrun, Framing, or Timeout).
 */
int UART_Read(uint8_t *output);
uint8_t UART_Data_Available(void);

uint8_t SPI_Transfer(uint8_t data);

void Expander_Set_Input(uint8_t hw_addr, uint8_t reg_addr);
void Expander_Set_Output(uint8_t hw_addr, uint8_t reg_addr);

void Expander_Write(uint8_t hw_addr, uint8_t reg_addr, uint8_t data);
uint8_t Expander_Read(uint8_t hw_addr, uint8_t reg_addr);

#ifdef	__cplusplus
}
#endif

#endif	/* HAL_H */