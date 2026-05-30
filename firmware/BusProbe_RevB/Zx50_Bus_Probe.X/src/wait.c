#include <stdbool.h>
#include "hal.h"
#include "pins.h"
#include "wait.h"

void WAIT_Init(void) {
    // 1. Enable Open-Drain mode for RB1 (~WAIT)
    // This allows the PIC to pull the line low safely, and float it high.
    ODCONBbits.ODCB1 = 1;

    // 2. Set the latch to 1 (float / de-assert) BEFORE making it an output
    Z80_WAIT_LAT = 1;

    // 3. Enable the output driver
    Z80_WAIT_DIR = 0;
}

void WAIT_Assert(void) {
    // Drive the ~WAIT pin low to pause the Z80
    Z80_WAIT_LAT = 0;
}

void WAIT_Deassert(void) {
    // Drive the ~WAIT pin high to allow the Z80 to run
    Z80_WAIT_LAT = 1;
}

bool WAIT_Is_Asserted(void) {
    // The pin is an output, so we read the LATCH value, not the PORT value.
    // The signal is active-low, so return true if the latch is 0.
    return (Z80_WAIT_LAT == 0);
}
