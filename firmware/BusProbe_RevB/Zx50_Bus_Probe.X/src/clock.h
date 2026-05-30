/*
 * File:   clock.h
 * Author: Marc Mosko
 *
 * Description: Manages Z80 clock generation for the Zx50 Bus Probe Rev B.
 * Supports two primary modes: a high-speed, free-running hardware PWM clock
 * for passive observation, and a slower, ISR-driven stepped clock for
 * synchronized bus operations.
 */

#ifndef CLOCK_H
#define	CLOCK_H

#ifdef	__cplusplus
extern "C" {
#endif

/**
 * @brief Initializes all clocking hardware (PWMs and Timers) but leaves them disabled.
 */
void Z80_Clock_Init(void);

/**
 * @brief Starts the high-speed, free-running hardware PWM clock (4MHz MCLK, 1MHz ZCLK).
 * This is used for passive bus sniffing or allowing the Z80 to run at full speed.
 */
void Z80_Clock_Start_FreeRun(void);

/**
 * @brief Stops the high-speed hardware PWM clock.
 */
void Z80_Clock_Stop_FreeRun(void);

/**
 * @brief Starts the ISR-driven, synchronized step clock (~1kHz).
 * Each timer tick will dispatch one T-State from the command queue.
 * This is used when the PIC is actively driving the bus.
 */
void Z80_Clock_Start_Synchronized_Step(void);

/**
 * @brief Stops the ISR-driven step clock.
 */
void Z80_Clock_Stop_Synchronized_Step(void);
void Z80_Clock_Manual_Pulse(void);

/**
 * @brief Generates one precise 1MHz ZCLK cycle and four 4MHz MCLK cycles.
 * This is a private helper function used by the command queue dispatcher.
 */
void Z80_Generate_Single_Pulse(void);

#ifdef	__cplusplus
}
#endif

#endif	/* CLOCK_H */