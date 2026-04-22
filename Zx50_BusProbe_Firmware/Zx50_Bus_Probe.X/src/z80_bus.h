/* * File:   z80_bus.h
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

// Add semicolons to finish the prototypes
void Z80_Mem_Write(uint16_t address, uint8_t data);
uint8_t Z80_Mem_Read(uint16_t address);
void Z80_IO_Write(uint16_t port_and_ah, uint8_t data);
uint8_t Z80_IO_Read(uint16_t port_and_ah);
void Z80_Bus_Snapshot(void);
        
void Z80_Boot_Sequence(void);

#ifdef	__cplusplus
}
#endif

#endif	/* Z80_BUS_H */