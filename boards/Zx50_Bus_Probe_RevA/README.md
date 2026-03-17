# Zx50 Bus Probe & Injector Card (Rev A)

## 1. Overview and Purpose
The Zx50 Bus Probe is a hybrid diagnostic tool designed specifically for a Z80-based Zx50 backplane architecture. It serves as an active oscilloscope probe, an arbitrary signal injector, and a digital logic analyzer tap. 

Instead of manually moving oscilloscope probes across an active backplane, the Zx50 Probe allows a user to digitally route any of the 72 backplane signals to a central BNC output, inject external signals via a BNC input, and monitor system health via an onboard UI.

There is a Receiver card that attaches to the Zx50 bus.  It has a Pi PICO as the interface to a host computer.  The Pico orchestrates the backplane signal multiplexing.  It is attached via SPI to an 18F4620 PIC that has two GPIO expanders.  The PIC is the Zx50 bus debugger.  It can read or write to the bus and it can control the clocks.  The 18F4620 uses its onboard SPI to talk to the GPIO expanders and the UART to talk to the Pico.  A to-be-determined serial protocol allows the Pico to send commands or read data from the 4620.  The intent is the 4620 has a simple command monitor and rarely needs flash updates.  The Pico has complex software in Python that is easier to program and update.

There is a Sender card that attaches to the Receiver via 2x5 ribbon cable.  The Sender card attaches to an AFG to put signals on backplane traces.  These can be monitored by the Receiver.  Both sender and receiver have high-speed op amps and BNC connectors to attach to lab equipment.

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
