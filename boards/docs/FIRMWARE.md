# Zx50 Bus Probe: Firmware Development Plan

## Phase 1: PIC18F4620 "Ghost Mode"
**Goal:** Guarantee the PIC processor boots up completely transparent to the Zx50 backplane to prevent electrical contention.
* **Toolchain:** Microchip MPLAB X & XC8 Compiler.
* **Process:** 1. Write a minimal `main.c` that initializes the system clock.
  2. Write `0xFF` to `TRISA`, `TRISB`, `TRISC`, `TRISD`, and `TRISE`. This explicitly sets every single GPIO pin to a High-Impedance (Input) state.
  3. Disable analog multiplexing on digital pins (`ADCON1 = 0x0F` or equivalent for the 4620).
  4. Enter a `while(1) { Sleep(); }` loop. 
* **Outcome:** The PIC is effectively removed from the circuit, safely clearing the runway for the Pi Pico.

## Phase 2: Automated Backplane Characterization
**Goal:** Use the Pi Pico to inject high-speed signals into the naked backplane while a PC orchestrates measurements via the Tektronix MDO3034.
* **Toolchain:** C/C++ SDK (Pico), Python + `pyvisa` (PC).
* **Process:**
  1. **Pico Firmware:** Write a simple USB-Serial command parser that listens for commands like `FREQ 10000000`. Use the Pico's PIO (Programmable I/O) to generate a mathematically perfect square wave on a designated Shadow Bus pin at the requested frequency.
  2. **Python Orchestrator:** Write a script on the PC that:
     * Connects to the Pico (COM port) and the Tektronix (Ethernet/IP).
     * Commands the Pico to start generating a 1MHz clock.
     * Commands the Tektronix to Auto-Scale, measure Peak-to-Peak voltage on the active line, and measure crosstalk (Vpp) on an adjacent quiet line.
     * Steps the frequency up to 40MHz in 1MHz increments, logging the data to a CSV.
* **Outcome:** A comprehensive bandwidth and crosstalk profile of the physical OSH Park backplane.

## Phase 3: Inter-Processor Communication (IPC)
**Goal:** Establish a reliable command-and-control protocol between the PIC and the Pico.
* **Architecture:** The Pico acts as the "High-Speed Brawn" (DMA, 40MHz signaling), while the PIC acts as the "Supervisor Brain" (handling the analog muxes `U2`-`U12` and steady-state Z80 monitoring).
* **Physical Layer:** Utilize the dedicated UART (`TX`/`RX`) or SPI pins running between the two chips on the Bus Probe board. 
* **Protocol:** Implement a simple packetized serial protocol (e.g., `[SYNC] [LENGTH] [COMMAND] [PAYLOAD] [CHECKSUM]`). 
  * Example Command: Pico tells PIC, *"Set Mux Array to route Z80 Address Line A15 to Analog Channel 1."*

## Phase 4: Full Bus Master & Monitor
**Goal:** Develop the software to freeze the Z80, take over the bus, and inject/read data.
* **Process:** 1. Pico asserts `~BUSRQ` and waits for `~BUSAK` from the Z80.
  2. Pico asserts `~OE` on the Bus Probe's transceiver firewall to physically connect itself to the backplane.
  3. Pico executes DMA transfers to memory or I/O, utilizing the PIC to monitor analog signal integrity during the transfer.