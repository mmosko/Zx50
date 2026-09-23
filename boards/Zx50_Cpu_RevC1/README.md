# Zx50 CPU Card (Rev C1)

## 1. Overview

This is the primary CPU board for the Zx50 8-slot passive backplane system. It hosts the Z80 microprocessor (running at 5 MHz to 10 MHz) and acts as the master controller for the primary bus.

Revision C1 updates the design to a **6-layer stackup**, integrating a high-performance **Math and Stack Coprocessor Cluster** mounted on the bottom side beneath the clock mezzanine shield, along with a dedicated hardware **Wait-State Generator (`wait_gen`)**.

Crucially, this board coexists with the **Zx50 Shadow Bus** architecture. It features a hardware-level "firewall" that allows a secondary master (like a Pi Pico on the Bus Probe or Front Panel card) to request the bus via `~BUSRQ`. When the Z80 yields (`~BUSAK`), the CPU card instantly severs itself from the backplane, allowing the secondary master to perform high-speed 40 MHz DMA transfers without electrical contention.

---

## 2. Core Architecture & Logic Families

### The CPU
* **Z80 Microprocessor (`U4`):** Zilog `Z84C00xxP` CMOS variant in a 40-pin DIP package (socketed).

### The Transceiver Firewall (`SN74ABT245BN`)
To drive the heavy capacitance of the 8-slot backplane, this board uses four **`SN74ABT245BN`** octal bus transceivers (`U2`, `U3`, `U5`, `U7`) with high-drive capability. A unified BOM of four '245s optimizes PCB trace routing across all 32 backplane lines.
* **Convention:** "A-Ports" face the Z80; "B-Ports" face the Backplane.
* **Address Bus (`U2`, `U3`):** Direction (`DIR`) is hardwired to `+5V` (A $\rightarrow$ B only).
* **Control Bus (`U7`):** Direction (`DIR`) is hardwired to `+5V` (A $\rightarrow$ B only). *(Unused input `A8` is tied to GND via a 10k$\Omega$ resistor `R2` to prevent CMOS floating-gate oscillation)*.
* **Data Bus (`U5`):** Direction (`DIR`) is dynamically controlled by read/acknowledge steering logic (`D_DIR` driven by `U8` / `R8`). This switches the transceiver to an input state (B $\rightarrow$ A) during standard memory/IO reads or Interrupt Acknowledge (`INTA`) cycles.
* **Isolation (`~OE`):** The `~OE` pins of all four transceivers are driven by inverted `~BUSAK` (`/BUSAK` from `U1` pin 4).

### Glue Logic & Bus Coordination
Discrete "Little Logic" and micro-logic ICs handle high-speed signal translation:
* **`74AHC1G14` (`U1` - Schmitt Inverter):** Inverts the Z80's active-low `~BUSAK` signal to drive the active-low `~OE` pins of the transceiver wall.
* **`74AHCT74` (`U9` - Dual D Flip-Flop):** Latches timing states for wait-state generation.
* **`74AHCT132` (`U10` - Quad Schmitt NAND):** Handles pulse shaping and step-logic gating for debugging.
* **`74LVC1G3208` (`U8` - 3-Input OR-AND Combo):** Manages direction and enable logic for auxiliary bus controls.

---

## 3. Hardware Wait-State Generator (`wait_gen`) Subsystem

The board incorporates a dedicated hardware wait-state generator to support single-step debugging and cycle stretching during fast coprocessor or backplane operations:
* **Dual D Flip-Flop (`SN74AHCT74DRG4` / `U9`):** Latches bus cycle transitions relative to `ZCLK` and `~M1`/`~IORQ`/`~MREQ` edges.
* **Quad Schmitt-Trigger NAND (`74AHCT132` / `U10`):** Provides noise-tolerant pulse shaping and single-step gate logic.
* **Open-Drain Output (`2N7002-7-F` N-Channel MOSFET / `Q2`):** Drives the active-low `~WAIT` line without contention, allowing other cards or the CPLD to safely assert `~WAIT`.
* **Modes Supported:**
  1. **Single-Step Execution:** Holds `~WAIT` low at $T_2$/$T_3$ until a manual step pulse is received from the Clock Mezzanine (`J3`) or Front Panel (`J4`).
  2. **Programmable Cycle Stretching:** Generates accurate 1-cycle hold states for memory or I/O windows.

---

## 4. Integrated Math & Stack Coprocessor Cluster (Bottom Layer)

Mounted entirely on the back side of the board beneath the Clock Mezzanine copper shield, a high-performance CPLD cluster operates on a dedicated private memory bus.

```text
                  +-----------------------------------+
                  |   ATF1508AS CPLD (PLCC-84 / U11)  |
                  |   Dual Clocks: 20MHz MCLK / 5MHz ZCLK|
                  +-----+-----------------------+-----+
                        |                       |
           CA0-CA13     |                       |  CD0-CD7
         Private Address|                       |  Private Data
                        v                       v
            +-----------+-----------------------+-----------+
            |                                               |
            |   +-------------------+   +---------------+   |
            |   | SST39SF040 Flash  |   | IS61C5128AS   |   |
            |   | 16KB Active (55ns)|   | 16KB Active   |   |
            |   | PLCC-32 (U13)     |   | SRAM 32-SOP   |   |
            |   +---------+---------+   +-------+-------+   |
            |             |                     |           |
            |             | ~F_CE / ~F_OE / ~F_WE| ~M_CE / ~M_OE / ~M_WE
            +-------------+---------------------+-----------+
```

### 1. Central Controller (`ATF1508ASx-xxJx84` / `U11`)
* **Package:** 128-macrocell CPLD in an 84-pin PLCC surface-mount socket.
* **Dual Clock Architecture:** Driven by both **20/40 MHz `MCLK`** (`GCLK1`, Pin 83) and **5/10 MHz `ZCLK`** (`CLK`, Pin 2) from the clock mezzanine (`J3`). The internal state machine executes at `MCLK` speed, enabling sub-cycle arithmetic and table lookups before the Z80 samples data.
* **Features:** Hardware multiplication (Quarter-Square algorithm), fast division seed generation, 16.16 fixed-point ALU, trigonometric LUT queries, and custom DMA/stack frame acceleration.

### 2. Private Memory Architecture (Zero `~BUSREQ` Contention)
The CPLD manages its own dedicated private address (`CA0`–`CA13`) and data (`CD0`–`CD7`) buses, isolating coprocessor memory operations from the primary Z80 system bus:
* **Private Address Space (16 KB):** A 14-bit address bus (`CA0`–`CA13`) provides 16 KB of addressable private memory space. Upper address lines (`A14`–`A18`) on both memory ICs are tied directly to **`GND`** to guarantee static CMOS levels and prevent floating pin oscillations.
* **Private Flash/EEPROM (`SST39SF040` / `U13`):** 16 KB active window (55 ns NOR Flash) in a 32-pin PLCC socket. Stores non-volatile lookup tables (Quarter-Square $f(n)=\lfloor n^2/4 \rfloor$, sine/cosine maps, logarithmic tables, reciprocal seeds).
* **Private SRAM (`IS61C5128AS-25QLI` / `U12`):** 16 KB active window (25 ns High-Speed Static RAM) in a 32-pin SOP footprint. Serves as private scratchpad, hardware stack frame storage, or modifiable shadow RAM.
* **Pull-up Protection:** `~M_CE` and `~F_CE` lines are fitted with $10\text{ k}\Omega$ pull-up resistors (`R7`, `R10`) to $+5\text{V}$ to keep both memory chips deselected and High-Z during power-up or CPLD JTAG re-programming.

### 3. Private Memory Access Speed Selector (`J8` - `MEM SPD`)
To support both 20 MHz and 40 MHz `MCLK` speeds without requiring CPLD bitstream re-flashing:
* **Header (`J8`):** 2-pin (1x2) 2.54mm pin header connected to CPLD Pin 81 (`I/O/GCLK3`) with a $10\text{ k}\Omega$ pull-up resistor (`R5`) to $+5\text{V}$.
* **Jumper Open (High / Default):** Selects **2-cycle private access pipeline** (safe access window for 40 MHz `MCLK` with 25 ns SRAM).
* **Jumper Shorted to GND (Low):** Selects **1-cycle private access pipeline** (fast mode for 20 MHz `MCLK`).

### 4. JTAG In-System Programming
* **Header (`J7`):** 6-pin (1x6) 2.54mm male header.
* **Pinout:** $+5\text{V}$ (Pin 1), `GND` (Pin 2), `TMS` (Pin 3), `TDO` (Pin 4), `TDI` (Pin 5), `TCLK` (Pin 6). Compatible with Waveshare USB-JTAG converters and OpenOCD.
* **Offline Option:** The PLCC-32 Flash chip can be extracted and programmed offline using a T48 / TL866-3G universal programmer.

---

## 5. Power-On Reset (POR) Subsystem

Handled by a **Microchip `MCP1316MT-46LE/OT`** Supervisor IC (SOT-23-5, `U6`).
* **Boot Delay:** Imposes a ~200 ms delay on power-up to allow bulk capacitors ($100\,\mu\text{F}$ `C9`) to charge and peripheral clock sources/Picos to initialize before releasing `~RESET`.
* **Threshold:** 4.6V trip point for brown-out protection.
* **Open-Drain Output:** Safely drives the shared `~RESET` rail (`Pin 1`).
* **Manual Reset (`SW1`):** Tactile button connected to `~MR` (`Pin 3`) for debounced hardware reset during bench testing.

---

## 6. 6-Layer Stackup & PCB Routing Strategy

Revision C1 uses a **6-layer stackup** to accommodate the high-density coprocessor cluster beneath the top-side clock shield without interfering with front-side copper:

| Layer | Type | Dedicated Function |
| :--- | :--- | :--- |
| **Layer 1 (Top)** | Signal / Plane | Primary Z80 component traces, Clock Mezzanine RF shield copper ground pour |
| **Layer 2 (GND)** | Power Plane | Continuous $GND$ reference plane |
| **Layer 3 (Inner 1)** | Signal | **Private Coprocessor Bus:** `CA0`–`CA13`, `CD0`–`CD7`, and private control lines (`~M_CE`, `~M_OE`, `~M_WE`, `~F_CE`, `~F_OE`, `~F_WE`) |
| **Layer 4 (Inner 2)** | Signal | **Z80 Bus Ingest:** Taps `A0`–`A15`, `D0`–`D7`, and control lines from `U4` to the CPLD |
| **Layer 5 (VCC)** | Power Plane | Continuous $+5\text{V}$ power distribution plane |
| **Layer 6 (Bottom)** | Signal / SMT | Bottom-mounted SMT footprints: ATF1508AS PLCC-84 (`U11`), SST39SF040 PLCC-32 (`U13`), IS61C5128AS SOP-32 (`U12`) |

---

## 7. Interfaces & Connectors

| Connector | Type | Description |
| :--- | :--- | :--- |
| **`J1` - Backplane** | 80-Pin Edge Connector | Standard Zx50 2.54mm bus interface. |
| **`J2` - Bus Connect / Step Tap** | 2x2 Pin Socket | Tap for `AUX` (Pin 80), `GPIO15`, `~STEP`, and `~RUN` signals. |
| **`J3` - Clock Mezzanine** | 2x5 Socket (2.54mm) | Ingests `MCLK` (20/40 MHz), `CLK` (5/10 MHz ZCLK), and `~STEP` signals. |
| **`J4` - Front Panel** | 2x5 Right-Angle IDC | Interfaces status LEDs (`RUN`, `HALT`), `~RESET`, `~STEP`, and power lines. |
| **`J5` - TP_D_DIR Debug** | 1x2 Header (2.54mm) | Hardware tap for Data Bus Direction monitoring and GND test point. |
| **`J6` - TP_BUSAK Debug** | 1x2 Header (2.54mm) | Hardware tap for `~BUSAK` signal observation. |
| **`J7` - Coprocessor JTAG** | 1x6 Header (2.54mm) | In-System Programming header for the ATF1508AS CPLD (`+5V`, `GND`, `TMS`, `TDO`, `TDI`, `TCLK`). |
| **`J8` - MEM SPD Jumper** | 1x2 Header (2.54mm) | Hardware jumper for 1-cycle vs 2-cycle private memory access speed selection (`Pin 81` / `R5`). |

---

## 8. Estimated Power Consumption Analysis

Operating at $5\text{V}$, the Rev C1 CPU card draws a typical active current of **~170 mA (~0.85 W)** and a worst-case peak switching current of **~280 mA (~1.40 W)**. The power load is split between the primary Z80 CPU subsystem and the high-speed coprocessor cluster.

### A. Primary CPU & Bus Interface Subsystem

| Component | Part Number | Qty | Typ. Current | Max Current | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Z80 CPU (10 MHz)** | `Z84C00xxP` | 1 | 10 mA | 20 mA | CMOS low-power core |
| **Bus Transceivers** | `SN74ABT245BN` | 4 | 15 mA | 40 mA | Drives 8-slot backplane capacitance |
| **Wait-State Logic** | `74AHCT74` / `132` | 2 | 8 mA | 15 mA | Dual D-FF & Schmitt NAND gates |
| **Glue Logic & Supervisor** | `74AHC1Gxx` / `MCP1316` | 5 | 3 mA | 5 mA | SOT-23 micro-logic & reset controller |
| **Status LEDs & Pull-ups** | `PWR`, `HALT` LEDs | 2 | 8 mA | 10 mA | ~$470\Omega$ current limiting |
| **Subtotal (CPU Side)** | | | **~44 mA** | **~90 mA** | **~0.22 W Typ / 0.45 W Max** |

### B. Coprocessor Cluster Subsystem (Bottom Layer)

| Component | Part Number | Qty | Typ. Current | Max Current | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **CPLD (20/40 MHz MCLK)** | `ATF1508ASx-xxJx84` | 1 | 65 mA | 100 mA | Dynamic $I_{CC}$ scales with MCLK frequency |
| **Private SRAM (25 ns)** | `IS61C5128AS-25QLI` | 1 | 15 mA | 30 mA | Active read/write state |
| **Private Flash (55 ns)** | `SST39SF040` | 1 | 15 mA | 30 mA | Active table read state |
| **Subtotal (Coprocessor)** | | | **~95 mA** | **~160 mA** | **~0.48 W Typ / 0.80 W Max** |

### C. Total Card Power Summary
* **Typical Active Load:** **139 mA – 170 mA** (~0.70 W – 0.85 W @ 5V)
* **Maximum Peak Load:** **250 mA – 280 mA** (~1.25 W – 1.40 W @ 5V)