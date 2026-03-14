# Zx50 Front Panel Card

This card drives the flashy front panel.  The front panel will have LEDs for bus state
plus a programmable LCD display (e.g. EA DIP205G-4NLED SPI).  It will also have
some system control switches.

## Physical Interface

- LCD Display: Driven by a Pi PICO on the front panel card, it can display messages
from the Pico or the Z80.

- LEDs
  - Z80 Address [0:15]
  - Z80 Data [0:8]
  - Z80 Control (about 12 of them)
  - Shadow Bus data [0:8]
  - Shadow Bus control (8 lines)
  - Power
  - Some of these could be hex digit mult-segment

- Switches
  - Power switch (e.g. SPST to turn on power supply)
  - Run/Stop (SPST pulls line low)
  - Step (momentary, pulls line low)

## Pico Interface

The Pico controls multple tri-state buffers (e.g. '244) attached to the different
8-bit buses (address hi, address low, data, control, shadow data, shadow control).
It reads each bus periodically and updates the front panel LEDs.

There is an IORQ decoder chip that fires an interrupt whenever the Z80 writes to
the front panel card's IO address.  The Z80 can transfer commands to the Pico
by using, e.g. OTIR transfers.  During an I/O instruction, the Z80 places the contents of the B register on the upper address bus (A8-A15), while the C register (the port address) goes on the lower bus (A0-A7).

Because OTIR decrements B with every loop, the Pico literally gets a real-time hardware countdown timer handed to it on A8-A15 with every single byte.  At the end of the burst,
the Pico can udpate the LCD display from its local memory.

Because the Pico has fast PIO (Programmable I/O) state machines, it does not even need to write this in C. You can write a tiny 4-line PIO assembly program that just sits there, watching the ~IORQ pin, and instantly pushes those 16 pins into a DMA FIFO buffer for your main Pico code to read at its leisure. It won't miss a single byte, even at 8MHz, 10MHz, or 20MHz.

## Shadow Bus transfers

The other option is for the Pico to work as a Shadow Bus slave or master.  The Z80 can setup a
DMA transfer from meory to the Pico, and this can then run at 40 MHz.

See [Zx50 Bus Protocol](https://github.com/mmosko/Zx50Bus/blob/main/README.md).

## Physical UI and the Zx50 CPU Card

The Front Panel card attaches via two 2x50 cables to the front panel.  One is for the
SPI control of the LCD display.  The other is for updating the LCDs and the physical
switches.  A small MCU (e.g. small 18Fxxxx) controls the LEDs based on commands from
the Pico.

This arrangement allows one to use the fancy front panel control card or bypass it
directly to the CPU card for a minimum interface.

Front Panel Connector (exact pinout TBD, 2x5 IDC)
1. +5V
2. +5V
3. TX (from Pico level shifter)
4. RX (to Pico level shifter)
5. Power switch
6. Run switch
7. Reset switch
8. Step_N switch
9. GND
10. GND

Note that the Zx50 CPU card has the exact same header on it, so one could attach

LCD Display Connector (2x5 IDC)
- 3.3V
- SCLK
- SDI (to Pico)
- SDO (from pico)
- GND
- RST (~MCLR)


Wiring
- If only the CPU card is installed, the front panel Connetor is wired directly to
the CPU card.
- If the Front Panel Card is installed, the front panel connector goes to the Front panel
card, and then a daisy chain short ribbon cables goes from the front pane card to the cpu card,
to wire the RUN and STEP switches to the clock mezzanine. The CPU card does not use the AUX pin.
- There will be some 2 position jumpers on the CPU card to connect pin 79 to RUN and pin 80
to STEP_N, in case I want to do that.  Otherwise, it will leave the 16-bit GPIO pins free.

## Interface to Zx50 Bus Probe

It is desirable for the Zx50 Bus Probe to see the Step switch.  The Reset switch is
already on the bus.  The Step switch will use Pin 80 (labelled AUX). 

It is assumed that if one is using the bus probe to control the system, there is a control
PC somewhere with the main interface and the STEP switch is just a convencience.
