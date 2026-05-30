/*
 * File:   z80_bus.h
 * Author: Marc Mosko
 *
 * Created on March 21, 2026, 11:18 AM
 */

#ifndef Z80_BUS_H
#define	Z80_BUS_H

#include <stdint.h> // Required for uint8_t and uint16_t

#ifdef	__cplusplus
extern "C" {
#endif

typedef enum {
    CYCLE_T1 = 1,
    CYCLE_T2,
    CYCLE_T3,
    CYCLE_T4
} t_cycle_t;

/**
 * @brief Initializes the Z80 bus to a safe, high-impedance state.
 */
void Z80_Bus_Init(void);

/**
 * @brief Controls the bus transceivers to either listen or drive the bus.
 * @param enable 1 to enter "Ghost" mode (listen), 0 to take control (drive).
 */
void Ghost(uint8_t enable);

void Z80_Mem_Write(uint16_t address, uint8_t data, t_cycle_t cycle);
uint8_t Z80_Mem_Read(uint16_t address, t_cycle_t cycle);
void Z80_IO_Write(uint16_t port_and_ah, uint8_t data, t_cycle_t cycle);
uint8_t Z80_IO_Read(uint16_t port_and_ah, t_cycle_t cycle);

void Z80_Bus_Snapshot(void);
void Z80_Boot_Sequence(void);

#ifdef	__cplusplus
}
#endif

#endif	/* Z80_BUS_H */