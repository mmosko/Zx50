# Zx50 Front Panel Architecture

The Zx50 Front Panel provides a comprehensive, diagnostic-level physical user interface. To minimize PCB routing complexity and eliminate the need for secondary microcontrollers, the design is split into two halves:
1. **The Brain (Front Panel Bus Card):** Plugs into the Zx50 backplane. It contains the Pi Pico, seven 8-bit bus latches, and the high-speed PIO trigger logic.
2. **The Faceplate (Dumb Terminal):** A physical panel containing only SPI displays, a single shift register, LEDs, and mechanical switches. It contains no firmware and is driven entirely by the Pico over two 2x5 ribbon cables.

---

## 1. Physical User Interface (The Faceplate)

The faceplate utilizes an aerospace-grade UI, relying on alphanumeric dot-matrix displays and custom pixel glyphs to reduce discrete LED clutter.

### Displays (SPI Bus)
* **Z80 Bus Readout:** 1x **HCMS-3973** (8-Character, 3.3V, Green).
  * Displays: Address (4 Hex), Data (2 Hex), Read/Write flag (1 Char), Mem/IO flag (1 Char).
* **Shadow Bus Readout:** 1x **HCMS-3962** (4-Character, 3.3V, Red).
  * Displays: Shadow Data (2 Hex), Shadow Control Signals (2 Chars).
  * *Glyph Logic:* Because HCMS displays allow direct 5x7 pixel RAM access, the 6 shadow control lines (`~SSTB~`, `~SINC~`, `~S_EN~`, `~S_DONE~`, `SRW`, `~S_BUSY~`) are mapped into two characters using custom bitmap glyphs (e.g., illuminating the top 3 rows for one signal, and the bottom 3 rows for another).
* **System Display:** 1x **EA DIP205G-4NLED** (LCD, SPI Mode). Displays high-level system text, Pico diagnostics, and DMA strings.

### Status LEDs
* **Real-Time Indicators (Yellow):** * 1x `POWER` (Hardwired to power rails).
  * 1x `RUN` (Hardwired to the Run/Stop switch).
* **Latched Z80 Status (Green):**
  * 8x discrete LEDs displaying `~M1~`, `~HALT~`, `~WAIT~`, `~BUSRQ~`, `~BUSAK~`, `~INT~`, `~NMI~`, `~RESET~`. 
  * Driven locally on the faceplate by a single **74HC595** 8-bit shift register sharing the SPI bus.

### Switches
* **POWER:** Heavy-duty SPST toggle (Wired directly to the ATX supply or power relay).
* **RUN / STOP:** SPST Toggle. Grounds the `/RUN` line, illuminates the Yellow RUN LED, and signals the Pico to either sleep the displays (RUN) or sample the bus (STOP).
* **STEP:** Momentary pushbutton. Manually clocks the Z80 when in STOP mode.
* **RESET:** Momentary pushbutton. Hardwired directly to the CPU card's reset circuit.
* **DISPLAY ON / OFF:** SPST Toggle. Allows the user to manually blank the SPI displays and shift registers to eliminate visual noise during full-speed runs.

---

## 2. Ribbon Cable Pinouts

The faceplate connects to the Front Panel Card via two 10-pin (2x5) IDC ribbon cables. 

### Cable 1: CPU Control & Switches
This cable mirrors the front panel header on the Zx50 CPU card, allowing the faceplate to plug directly into the CPU card for a minimal setup (bypassing the Pico UI entirely).
* **Pin 1:** `+5V`
* **Pin 2:** `+5V`
* **Pin 3:** `NC`
* **Pin 4:** `DISP_EN` (From Display On/Off Switch -> To Pico GPIO)
* **Pin 5:** `NC`
* **Pin 6:** `/RUN` (From Run/Stop Switch)
* **Pin 7:** `~RESET_SW` (From Reset Switch)
* **Pin 8:** `~STEP` (From Step Switch)
* **Pin 9:** `GND`
* **Pin 10:** `GND`

### Cable 2: SPI Display Bus
This cable is driven exclusively by the Pico's SPI peripheral to update the UI hardware. Because the HCMS-39xx series is natively 3.3V, no level-shifting is required on the data lines.
* **Pin 1:** `+3.3V` (Logic power for LCD, HCMS displays, and 74HC595)
* **Pin 2:** `+5V` (Required for EA DIP205 LCD LED Backlight)
* **Pin 3:** `SCLK` (Shared SPI Clock)
* **Pin 4:** `MOSI` (Shared SPI Data Out)
* **Pin 5:** `LCD_CS` (Chip Select for EA DIP205)
* **Pin 6:** `SHARED_RS` (Register Select, shared by EA DIP205 and HCMS displays)
* **Pin 7:** `HCMS_CE` (Chip Enable for the two HCMS dot-matrix displays)
* **Pin 8:** `595_LATCH` (Latch clock for the 74HC595 Green LED driver)
* **Pin 9:** `GND`
* **Pin 10:** `GND`

---

## 3. The Brain: Front Panel Bus Card Architecture

To safely read the 5V Zx50 backplane without damaging the 3.3V Pi Pico, the Front Panel Card relies on a multiplexed, native 3.3V local bus driven by 5V-tolerant latches.

### The 74LVC573A Latches
The card utilizes seven **74LVC573A** (Octal Transparent D-Type Latches with 3-State Outputs). Powered at 3.3V, these chips possess fully 5V-tolerant inputs, acting as perfect one-way voltage step-downs from the Z80 to the Pico.

The Latch Enable (`LE`) pins of all 7 chips are tied together. The Pico pulses this single line to instantly "freeze" a coherent, microsecond-accurate snapshot of the entire 56-pin bus state before reading the data.

* **Latch 1:** Z80 Address Low (`A0` - `A7`)
* **Latch 2:** Z80 Address High (`A8` - `A15`)
* **Latch 3:** Z80 Data (`D0` - `D7`)
* **Latch 4:** Shadow Data (`SD0` - `SD7`)
* **Latch 5:** Shadow Control (`~SSTB~`, `~SINC~`, `~S_EN~`, `~S_DONE~`, `SRW`, `~S_BUSY~`)
* **Latch 6:** Z80 Control 1 (`~M1~`, `~MREQ~`, `~IORQ~`, `~RD~`, `~WR~`, `~RFSH~`, `~HALT~`, `~WAIT~`)
* **Latch 7:** Z80 Control 2 (`~INT~`, `~NMI~`, `~RESET~`, `~BUSRQ~`, `~BUSAK~`)

### The Pi Pico GPIO Map (26/26 Pins Used)
The outputs of all seven latches are tied to a shared 8-bit local bus. The Pico multiplexes this bus by asserting the specific Output Enable (`~OE`) of the latch it wishes to read.

* **Shared 8-Bit Read Bus (8 Pins):** * `GP0` - `GP7` (Reads `Q0-Q7` from the active latch)
* **Hardware Latch Control (8 Pins):**
  * `GP8` - `GP14`: Selects `~OE` for Latches 1 through 7.
  * `GP15`: Global Latch Enable (`LE`) to freeze the snapshot.
* **Faceplate SPI Bus (5 Pins):** * `GP16` - `GP20`: `SCLK`, `MOSI`, `LCD_CS`, `HCMS_CE`, `595_LATCH`.
* **Faceplate Switches (3 Pins):** * `GP21`: `RUN_SW`
  * `GP22`: `STEP_SW`
  * `GP26`: `DISP_EN_SW`
* **Fast PIO Triggers (2 Pins):** * `GP27`: `~IORQ` (Hardware trigger for OTIR capture).
  * `GP28`: `~WR` (Hardware trigger modifier).

---

## 4. High-Speed Pico Integration

### OTIR High-Speed Capture
The Pico is capable of intercepting LCD strings directly from the Z80 utilizing block I/O instructions (`OTIR`).

During an `OTIR` instruction, the Z80 places the `B` register on the upper address bus (`A8-A15`). Because `OTIR` decrements `B` with every loop, the Pico receives a real-time hardware countdown timer handed to it on `A8-A15` with every single byte. 

The Pico uses a fast PIO (Programmable I/O) state machine hardwired to `GP27` (`~IORQ`) and `GP28` (`~WR`) to instantly assert the `~OE` pins for the Data and Address High latches, pushing the results directly into a DMA FIFO buffer. This ensures zero dropped bytes even at maximum backplane speeds.

### Shadow Bus Transfers
Alternatively, the Pico can act as a Shadow Bus slave or master. The Z80 can set up a DMA transfer from memory directly to the Pico, transferring display buffers out-of-band at up to 40 MHz.

### 5. Bill of Materials (Front Panel Bus Card)

To safely interface the 3.3V Pi Pico with the 5V Zx50 backplane and supply enough current for the faceplate displays, the card requires the following core components:

**Logic & Control:**
1. **1x Raspberry Pi Pico** (The core state machine and SPI master).
2. **7x 74LVC573A** (Octal Transparent D-Type Latches). *Must be LVC family for 5V input tolerance while powered at 3.3V.*
3. **1x 74AHCT1G04** (Optional single inverter for hardware interrupt conditioning, if needed).

**Power Supply:**
Because the HCMS-39xx dot-matrix displays on the faceplate can draw upwards of 150mA at full brightness, the system bypasses the Pico's internal 300mA regulator in favor of a dedicated high-current LDO.
4. **1x AMS1117-3.3** (or equivalent 3.3V, 1A LDO Linear Regulator in SOT-223).
   * **Input:** Powered directly from the Zx50 5V rail.
   * **Output:** Supplies the 3.3V rail for the Pi Pico (`VSYS`), the seven `74LVC573A` latches, and Pin 1 of the SPI Ribbon Cable.
5. **Capacitors:**
   * 1x `100µF` to `220µF` Electrolytic (Bulk input decoupling on the 5V rail).
   * 1x `10µF` Ceramic (LDO Input stability).
   * 1x `22µF` Ceramic (LDO Output stability).
   * 8x `0.1µF` Ceramic (Bypass capacitors for the Pico and the 7 latches).

**Connectors:**
6. **1x Zx50 Edge Connector** (Backplane interface).
7. **2x 2x5 IDC Headers** (Ribbon cable interfaces to the Faceplate).