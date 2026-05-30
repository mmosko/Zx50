/*
 * File:   wait.h
 * Author: Marc Mosko
 *
 * Created on May 12, 2024
 * Description: Manages the Z80 ~WAIT signal.
 */

#ifndef WAIT_H
#define	WAIT_H

#include <stdbool.h> // For bool type

#ifdef	__cplusplus
extern "C" {
#endif

/**
 * @brief Initializes the ~WAIT pin to a safe, inactive (high) state.
 */
void WAIT_Init(void);

/**
 * @brief Asserts the ~WAIT signal, pausing the Z80 CPU.
 */
void WAIT_Assert(void);

/**
 * @brief De-asserts the ~WAIT signal, allowing the Z80 CPU to resume.
 */
void WAIT_Deassert(void);

/**
 * @brief Checks if the ~WAIT signal is currently asserted.
 * @return True if the Z80 is being held in a wait state, false otherwise.
 */
bool WAIT_Is_Asserted(void);

#ifdef	__cplusplus
}
#endif

#endif	/* WAIT_H */
