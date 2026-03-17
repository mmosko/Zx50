# Zx50 Project Architecture Context

## Overview

The Zx50 is a custom 8-slot, passive backplane Z80 computer. It uses a "Shadow Bus" architecture where a Raspberry Pi Pico can take over the bus via DMA (~BUSRQ / ~BUSAK) to load RAM, debug, and monitor the system.

## Core Rules & Hardware

* Backplane: 8 slots. Fully terminated with 10K SIP pull-up resistors on Address, Data, and Control lines. Includes an ~IEI/~IEO interrupt daisy chain and heavy bulk capacitance (1000µF).

* CPU: Z80 running at 8 to 10 MHz.

* Clock System: A dedicated Clock Mezzanine board that generates a 40 MHz Master Clock (MCLK) for the Pi Picos, and uses a 74HC393 to divide it down to a 10 MHz ZCLK for the Z80. It uses an async-request latch system (1G79, 1G08, 1G32) to perfectly sync the CPU clock stopping/stepping with the Pi Pico's requests, ensuring no runt pulses.

* Logic Families: * 74AHCT (specifically 74AHCT244 and 74AHCT245) are used for bus transceivers to provide the strong ±8mA current needed to drive the backplane.

* Standard 74HC / 74AHC logic is used for local onboard glue logic.

* System Reset: Handled by an MCP1316M-46LE/OT Open-Drain Supervisor IC on the CPU card. It provides a ~200ms reset timeout to allow the backplane capacitors to charge and the Pi Pico bootloaders to initialize before the Z80 wakes up.



