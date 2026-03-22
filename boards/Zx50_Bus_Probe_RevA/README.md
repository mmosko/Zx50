# Zx50 Bus Probe & Injector Card (Rev A)

## 1. Overview and Purpose
The Zx50 Bus Probe is a hybrid diagnostic tool designed specifically for a Z80-based Zx50 backplane architecture. It serves as an active oscilloscope probe, an arbitrary signal injector, and a digital logic analyzer tap. 

Instead of manually moving oscilloscope probes across an active backplane, the Zx50 Probe allows a user to digitally route any of the 72 backplane signals to a central BNC output, inject external signals via a BNC input, and monitor system health via an onboard UI.

There is a Receiver card that attaches to the Zx50 bus. It has a Pi PICO as the interface to a host computer. The Pico orchestrates the backplane signal multiplexing. It is attached via SPI to an 18F4620 PIC that has two GPIO expanders. The PIC is the Zx50 bus debugger. It can read or write to the bus and it can control the clocks. The 18F4620 uses its onboard SPI to talk to the GPIO expanders and the UART to talk to the Pico. A to-be-determined serial protocol allows the Pico to send commands or read data from the 4620. The intent is the 4620 has a simple command monitor and rarely needs flash updates. The Pico has complex software in Python that is easier to program and update.

There is a Sender card that attaches to the Receiver via 2x5 ribbon cable. The Sender card attaches to an AFG to put signals on backplane traces. These can be monitored by the Receiver. Both sender and receiver have high-speed op amps and BNC connectors to attach to lab equipment.

## 2. The Universal Board Architecture
To minimize fabrication costs and guarantee matched signal paths, the system is designed as a **Universal PCB**. A single board design can be populated differently to serve as either the "Receiver" (The Brain) or the "Sender" (The Drone).

* **The Receiver (Master):** Populated with a Raspberry Pi Pico (RP2040) and a PIC18F4620. It orchestrates the signal routing, generates hardware-level system clocks, handles high-speed Z80 interrupts (`~WAIT~`, `~INT~`), and hosts the physical User Interface.
* **The Sender (Slave):** The Pi Pico and PIC are left unpopulated. It relies on the Receiver to command its local analog matrix via a 10-pin right-angle IDC ribbon cable.
* **The Jumper Matrix (3x7 Block):** A physical 21-pin routing block determines the board's role by directing the 5V control signals:
  * **Position 1-2 (Receiver Mode):** The onboard Pico drives both the local analog matrix and the remote Sender board via the ribbon cable.
  * **Position 2-3 (Sender Mode / Mirror Mode):** The local analog matrix is driven by external signals arriving from the ribbon cable.

## 3. Core Subsystems

### A. The "Voltage Firewall" (Level Shifting)
The Pi Pico operates strictly at 3.3V, while the Zx50 backplane and logic operate at 5.0V. 
* A **`74AHCT541`** buffer acts as a unidirectional level shifter and line driver.
* The "T" (TTL-compatible) inputs interpret the Pico's 3.3V signals as a valid logic HIGH, stepping them up to a robust 5.0V to drive the local multiplexers and safely push signals down the ribbon cable to the Sender board.

### B. The Analog Matrix
The core of the probing capability is a massive 72-channel crosspoint matrix.
* **Multiplexers:** Nine `CD74HC4051E` 8-channel analog multiplexers (High-Speed CMOS variant chosen over legacy `CD4051BE` to ensure <70Ω $R_{ON}$ and >100MHz bandwidth for sharp Z80 square waves).
* **Decoding:** A 4-to-16 line decoder (`74HC154` or cascaded `74HC138`s) manages the Chip Select lines for the multiplexers. Sending address `1111` (15) targets a "Phantom Mux," safely disabling the entire matrix to isolate the test equipment from the bus.
* **Op-Amps:** High-speed `OPA356xxD` CMOS operational amplifiers buffer the analog signals immediately before the `IN` and `OUT` BNC jacks to prevent the oscilloscope or function generator from loading the backplane.

### C. The Dedicated Logic Analyzer Field
To support professional diagnostic equipment (e.g., Tektronix logic analyzers), the rear of the card features a raw, unbuffered test point field.
* Arranged in standard 2xN 2.54mm pitch groupings spaced out by function: `ADDR [0:15]`, `DATA [0:7]`, `CTRL [0:7]`, `SHADOW_DATA [0:7]`, `SHADOW_CTRL [0:7]`, and `CLOCK [0:1]`.
* **Dedicated Ground Row:** Every signal pin is paired directly with an adjacent `GND` pin (Row 2), ensuring short return paths and pristine signal integrity for flying-lead probes.
* The headers are intentionally unbuffered, relying on the <2pF capacitance of professional logic analyzer pods to spy on the true analog state of the bus.

## 4. Mechanical & Physical Design

* **Asymmetric "Tower" Form Factor:** The PCB utilizes an inverted-T (or L-shaped) `Edge.Cuts` profile. The base fits the standard 5-inch Zx50 card dimensions, while the front UI section extends upward to 7 inches. This ensures the display and status LEDs clear the adjacent memory/CPU cards in the chassis.
* **User Interface:**
  * **Primary Display:** An `EA DIP205-4` 20x4 Character LCD, mounted flush to the PCB. It runs natively on the Pico's 3.3V SPI bus, with a dedicated 33Ω resistor dropping the 5V rail for the yellow/green backlight.
  * **Status LEDs:** Three right-angle horizontal LEDs (`CLK`, `MCLK`, `PWR`) mounted on the top edge of the board to provide immediate, bench-visible heartbeat and clock status.
* **Horizontal Interconnects:** The PIC ICSP programming header (`J4`) and the Sender/Receiver ribbon cable header (`J8`) use right-angle footprints to prevent cable collisions with adjacent Zx50 cards.

## 5. Firmware Architecture (PIC18F4620 Z80 BIU)

The PIC18F4620 operates as a 5V-native Z80 Bus Interface Unit (BIU). Running at 32MHz (via an 8MHz internal oscillator and 4x PLL), it provides strictly timed, cycle-accurate control over the Zx50 bus. 

### The RPC Serial Protocol
The PIC acts as a slave to the Pi Pico via a 1 Mbps UART link. It continuously listens for a magic Sync Byte (`0x5A`) followed by a 4-byte payload: `[OPCODE] [ADDR_H] [ADDR_L] [PARAM]`. Supported operations include:
* `CMD_LD` (0x01) / `CMD_STORE` (0x02): Read/Write a single byte to memory.
* `CMD_IN` (0x03) / `CMD_OUT` (0x04): Read/Write to I/O ports.
* `CMD_LDIR` (0x05): High-speed block memory writes up to 255 bytes.
* `CMD_SNAPSHOT` (0x07): Passively captures the current state of the Address, Data, and Control buses.
* `CMD_GHOST` (0x08): Hardware isolation toggle.
* `CMD_STEP` (0x11): Issues a single manual clock pulse.

### Hardware Ghost Mode
To prevent bus contention when the PIC is not actively driving the bus, the system defaults to "Ghost Mode". In this state, the `74ABT245` bidirectional transceivers (`U6` and `U7`) are driven into a High-Z state by pulling their Output Enable (`~OE`) pins HIGH, safely isolating the PIC's local pins from the active Zx50 backplane.

### Exact Cycle Emulation
Unlike standard microcontrollers that just toggle pins arbitrarily, the PIC firmware meticulously emulates Z80 machine cycles. * **Address Setup:** Uses the 8MHz hardware SPI bus to pre-load the 16-bit address into dual `MCP23S17` expanders.
* **T-State Sequencing:** The clock generation transitions from continuous PWM to manual bit-banging (`Z80_Clock_High()`, `Z80_Clock_Low()`), allowing the PIC to precisely orchestrate T1, T2, and T3 states.
* **Hardware WAIT:** During T2 and TW (Wait States), the PIC actively samples the external `Z80_WAIT` line, stalling its internal sequence just like real silicon until the external hardware is ready.

### Bus Snapshot
To analyze the state of the backplane at any given microsecond, the `CMD_SNAPSHOT` function temporarily opens the `74ABT245` transceivers in a "Listen Only" (A->B) direction. It pulls the 16-bit address from the SPI expanders, reads the Data and Control lines from its local PORT registers, immediately re-isolates the bus, and dispatches a 6-byte confirmation packet back to the Pico.

## 6. Automated Backplane Characterization Protocol

To validate the electrical integrity, propagation delays, and crosstalk of the Zx50 backplane, the system utilizes an automated testing protocol orchestrated by a laptop. This test requires two Zx50 Bus Probe cards: one configured as the **Receiver** (Master, populated with the Pi Pico) and one as the **Sender** (Slave, analog matrix only). They are connected via the 10-pin IDC ribbon cable.

### Hardware Setup
* **Laptop:** Runs the Python master control script. Connects to the Pi Pico via USB Serial and to the oscilloscope via Ethernet/USB (PyVISA/SCPI).
* **Oscilloscope (Tektronix MDO3034):** * **AFG Output:** Connected via BNC to the Sender card's `IN` port.
  * **CH1 (Optional Reference):** Probes the Sender card to measure the injected signal at the source.
  * **CH2 (Measurement):** Connected via BNC to the Receiver card's `OUT` port to measure the signal after traversing the backplane.

### The Serial Control Protocol (USB CDC)
The laptop communicates with the Receiver's Pi Pico using a simple ASCII protocol:
* `GHOST\n` - Instantly disables the 74HC154 decoders on both cards, isolating all test equipment from the backplane. Returns `OK GHOST`.
* `SELECT TX <physical_pin>\n` - Routes the AFG signal from the Sender's BNC `IN` to the specified backplane pin. Returns `OK TX <pin> <signal>`.
* `SELECT RX <physical_pin>\n` - Routes the specified backplane pin to the Receiver's BNC `OUT`. Returns `OK RX <pin> <signal>`.
* `IDN?\n` - Identifies the firmware variant. Returns `OK Zx50_PROBE_REVA`.
* `BRIDGE <ON/OFF>\n` - Engages/disengages the PIC18F4620 Z80 Bus Interface Unit for active protocol testing. (To be implemented).

### Automated Sweep Execution Flow
1. **Initialize:** The laptop establishes connections to the Pico and the Tektronix scope, sending `GHOST` to ensure bus safety.
2. **Frequency Sweep:** The scope's AFG is configured to step through operational frequencies (e.g., 8MHz, 10MHz, 20MHz, 30MHz, 36MHz, 40MHz).
3. **Signal Measurement:** For each frequency, the script iterates through all 71 active backplane pins:
   * Commands the Pico to `SELECT TX <pin>` and `SELECT RX <pin>`.
   * Commands the scope to measure attenuation and phase shift between the AFG source and CH2.
4. **Crosstalk Measurement:** While injecting a signal into the target pin, the script iterates the Receiver card through adjacent backplane traces (e.g., Target `Pin + 1`, `Pin - 1`), using the scope to measure peak-to-peak voltage (noise coupling) on CH2.
5. **Teardown:** The AFG is disabled, the Pico is commanded to `GHOST`, and a comprehensive CSV characterization report is generated.

## 7. MicroPython Firmware Architecture (Pi Pico)

The Pi Pico orchestrates the routing of signals across both the local (Receiver) and remote (Sender) analog matrices. The firmware is written in MicroPython and is highly modular to allow for rapid updates during testing.

### Modular Codebase
* **`pin_map.py`**: A pure configuration file containing the hardware dictionaries. It maps the physical J1 Edge Connector integer pin numbers (critical for calculating physical trace adjacency) to their logical signal names, the specific `CD74HC4051E` multiplexer chip, and the channel index (0-7). It also maintains the Pico GPIO assignments for the local and remote control buses.
* **`display.py`**: A dedicated hardware driver for the `EA DIP205-4` LCD. It handles the SPI initialization, the hard-reset sequence on boot, and the specific 3-byte formatting required by the display's `RW1073` controller. It abstracts all formatting so the main loop can update the UI with a single function call.
* **`main.py`**: The execution core. It establishes a non-blocking serial loop using `select.poll()`, parsing ASCII commands from the laptop. It maintains state variables for the currently routed `TX` and `RX` signals, updating the LCD in real-time.

### Break-Before-Make Safety
To prevent catastrophic bus collisions, `main.py` enforces a strict hardware-level "break-before-make" sequence inside the `route_signal()` function:
1. **Break:** Forces the `74LS154` decoder address to `1111` (Address 15, the "Phantom Mux"), instantly dropping the Enable pins on all multiplexers to disable output.
2. **Select:** Manipulates the GPIO pins to set the S0, S1, and S2 channel selection bits while the matrix is safely dead.
3. **Make:** Writes the target 4-bit address to the decoder, enabling only the single requested multiplexer to bridge the path to the BNC connector.