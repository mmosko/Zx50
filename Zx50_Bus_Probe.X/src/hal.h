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

// ==========================================
// Peripheral Prototypes
// ==========================================
void UART_Write(uint8_t data);
uint8_t UART_Read(void);

uint8_t SPI_Transfer(uint8_t data);
void Expander_Write(uint8_t hw_addr, uint8_t reg_addr, uint8_t data);
uint8_t Expander_Read(uint8_t hw_addr, uint8_t reg_addr);

#ifdef	__cplusplus
}
#endif

#endif	/* HAL_H */