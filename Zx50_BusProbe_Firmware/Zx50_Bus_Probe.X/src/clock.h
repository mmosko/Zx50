/* * File:   clock.h
 * Author: Marc Mosko
 * Description: Hardware clock generation for Z80 CLK and MCLK.
 */

#ifndef CLOCK_H
#define	CLOCK_H

#include <stdint.h>

#ifdef	__cplusplus
extern "C" {
#endif

extern uint8_t use_dual_clock; // Flag for x4 MCLK mode

// ==========================================
// Initialization
// ==========================================
void Z80_Clock_Init(void);

// ==========================================
// Free-Running Mode (Hardware PWM)
// ==========================================
void Z80_Clock_Start_PWM(void);
void Z80_Clock_Stop_PWM(void);

// ==========================================
// Bit-Banged Mode (Manual T-States)
// ==========================================
void Z80_Clock_Pulse(void);
void Z80_Clock_High(void);
void Z80_Clock_Low(void);

#ifdef	__cplusplus
}
#endif

#endif	/* CLOCK_H */