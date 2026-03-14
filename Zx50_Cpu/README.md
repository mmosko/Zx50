# Zx50 CPU Card

## 1. Overview
This is the primary CPU board for the Zx50 8-slot passive backplane system. It hosts the Z80 microprocessor (running at 8 to 10 MHz) and acts as the master controller for the primary bus. 

Crucially, this board is designed to coexist with the **Zx50 Shadow Bus** architecture. It features a hardware-level "firewall" that allows a coprocessor (like a Pi Pico on the Bus Probe or Front Panel card) to request the bus via `~BUSRQ`. When the Z80 yields (`~BUSAK`), the CPU card instantly severs itself from the backplane, allowing the Pico to perform high-speed 40MHz DMA transfers without electrical contention.

## 2. Core Architecture & Logic Families

### The CPU
* **Z80 Microprocessor:** Zilog `Z84C00xxP` CMOS variant in a 40-pin DIP package. 

### The Transceiver Firewall (`74AHCT245`)
To drive the heavy capacitance of the 8-slot backplane, standard `74HC` logic is insufficient. This board uses **`74AHCT245`** octal bus transceivers (±8mA drive current) for all bus interfacing. 
To optimize PCB trace routing, a unified BOM of four '245s is used (rather than mixing in '244s). 
* **Convention:** "A-Ports" face the Z80; "B-Ports" face the Backplane.
* **Address Bus (x2):** `DIR` is hardwired to `+5V` (A -> B only).
* **Control Bus (x1):** `DIR` is hardwired to `+5V` (A -> B only). *(Note: The unused `A8` input on this buffer is tied to GND via a 10kΩ pull-up to prevent CMOS floating-gate oscillation).*
* **Data Bus (x1):** `DIR` is dynamically driven directly by the Z80's `~RD` pin. 
* **Isolation (`~OE`):** The `~OE` pins of all four transceivers are driven by an inverted `~BUSAK` signal. 

### Glue Logic (`74AHC1G14`)
A single "Little Logic" SOT-23-5 Schmitt-Trigger Inverter (`SN74AHC1G14DBVR` / Digi-Key: `296-1088-1-ND`) is used to invert the Z80's `~BUSAK` signal to correctly drive the active-low `~OE` pins of the transceiver wall.

## 3. Power-On Reset (POR) Subsystem
The Master Reset logic is completely handled by a **Microchip `MCP1318MT-46LE/OT`** Supervisor IC (SOT-23-5, Digi-Key: `MCP1318MT-46LE/OTCT-ND`). 

* **The Boot Delay:** It imposes a strict ~200ms delay on power-up. This guarantees the 1000µF backplane bulk capacitance is fully charged, the clock oscillators are stable, and the Pi Pico bootloaders on the peripheral cards have fully initialized before the Z80 takes its first step.
* **Voltage Threshold:** Trips at 4.6V to prevent brown-out corruption.
* **Open-Drain Output:** Safely shares the backplane's `~RESET` line with other cards that may pull the line low.
* **No Watchdog:** The `1318M` specifically omits the hardware watchdog timer (unlike the 1316M), preventing accidental Z80 reboots during extended Pi Pico DMA operations.
* **Local Button:** A right-angle tactile switch (`Omron B3F` / Digi-Key: `SW402-ND`) is wired to the `~MR` (Manual Reset) pin, providing perfect, capacitor-free hardware debouncing for bench testing.

## 4. Interfaces

* **J1 - Backplane:** Standard Zx50 80-pin Edge Connector.
* **J3 - Clock Mezzanine (2x5 Socket):** Receives `MCLK` (40MHz), `CLK` (10MHz ZCLK), and manages the async-latched `~STEP` signals from the Zx50 Clock Mezzanine module.
* **J4 - Front Panel (2x5 Header):** Mirrors the signals sent to the system Front Panel. Includes `RUN`, `~STEP`, `~RESET`, and `TX`/`RX` paths. The `~STEP` signal is routed down to the backplane's `AUX` pin (Pin 80) to coordinate with the Clock Mezzanine and Bus Probe.