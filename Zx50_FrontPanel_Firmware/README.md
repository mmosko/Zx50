# Zx50 Front Panel Firmware

## 1. Overview

This directory contains the MicroPython firmware for the Raspberry Pi Pico on the Zx50 Front Panel Controller card.

The firmware's primary responsibilities are:

- **Passive Bus Monitoring:** Reading the Z80's address, data, and status buses without halting the CPU and displaying
  this information in real-time on the front panel's dot-matrix displays.
- **Active I/O Device:** Acting as a target for Z80 `OUT` instructions, specifically capturing high-speed `OTIR` block
  transfers to a FIFO buffer for display on the character LCD.
- **Hardware Control:** Managing the front panel switches (`RUN`, `STEP`, `DISP_EN`) to control the display's behavior
  and, in the future, to control the Z80's `~WAIT` and `~RESET` lines.

## 2. Code Structure

The firmware is organized into several modules:

- `main.py`: The main application entry point. It contains the primary control loop, state management for the front
  panel switches, and orchestrates calls to the other modules.
- `pins.py`: Centralized definitions for all GPIO pin assignments and SPI bus configurations. This is the canonical
  source for hardware connections.
- `lcd.py`: Driver for the 4x20 character LCD. It handles the unique, bit-reversed, LSB-first SPI protocol required by
  the EA DIP205G-4NLED display.
- `leds.py`: Driver for the HCMS dot-matrix displays and the discrete status LEDs (driven by a 74HC595 shift register).
- `font.py`: Contains the 5x7 font data for rendering both standard ASCII characters and custom status glyphs on the
  HCMS displays.
- `z80_io.py`: Manages the high-speed interaction with the Z80 bus. It contains the interrupt service routine (`IRQ`)
  that captures data from `OTIR` instructions and places it into a shared FIFO.

## 3. Key Implementation Details & Maintenance Notes

This firmware has several particularities that are critical for maintenance and future development:

### Dynamic SPI Bus Configuration

The SPI bus (`SPI(0)`) is shared by two devices with incompatible SPI modes:

1. **LCD Display:** Requires `baudrate=500,000`, `polarity=1`, `phase=1`.
2. **HCMS Displays & LED Driver:** Require `baudrate=5,000,000`, `polarity=0`, `phase=0`.

To solve this, the `pins.py` module contains two functions, `setup_spi_for_lcd()` and `setup_spi_for_hcms_and_leds()`.
The respective driver modules (`lcd.py`, `leds.py`) are responsible for calling the appropriate setup function **before
** every SPI transaction to ensure the bus is in the correct mode.

### LCD Bit-Reversal Logic

The EA DIP205G-4NLED character display uses a non-standard, LSB-first serial protocol. The `lcd.py` driver emulates this
in software by using a pre-computed lookup table (`BIT_REVERSE_TABLE`) to reverse the bits of every byte before sending
it to the Pico's standard MSB-first SPI hardware. This is a critical piece of "twisted logic" that must be preserved for
the LCD to function.

### Switch-Based Display Logic

The main loop in `main.py` implements specific rules for updating the passive bus monitor displays:

- The `~DISP_EN` switch acts as a master enable. If high, no updates occur.
- When the `~RUN` switch is active (low), the display updates at a regular interval (`passive_update_interval`).
- When the `~RUN` switch is inactive (high), the system is in "Step Mode". The display updates only once when the mode
  is first entered, and thereafter only when the momentary `~STEP` switch is pressed.

## 4. Current Status

**Firmware Version:** 0.7

The firmware is considered feature-complete for its initial goals and is ready for hardware testing.

- **Immediate Next Step:** Board assembly needs to be completed to load and test the firmware on the physical hardware.

## 5. Future Work & Ideas

- **Remote Bus Monitoring via Wi-Fi:**
    - Enable the Pico's Wi-Fi module to connect to the local network.
    - Stream the bus status over a simple TCP socket (e.g., for `nc` or a custom client) or create a small embedded web page that mirrors the physical LCD and LEDs. This would allow for remote, headless monitoring of the Z80 system.
- **Z80 Control Implementation:**
    - Implement the logic to drive the Z80's `~WAIT` line based on the `RUN`/`STEP` switches to allow for true single-stepping and pausing of the CPU.
- **Full HCMS Display Implementation:**
    - Expand the `leds.py` and `font.py` modules to render the full Z80 address and data bus values on the dot-matrix displays, not just the status codes.
