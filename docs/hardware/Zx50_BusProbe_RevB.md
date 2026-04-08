# Zx50 Bus Probe Rev B: Hardware Evolution & Optimization

This document outlines the transition from the Rev A "Breadboard-style" prototype to a high-performance Rev B production card. The primary goals are to resolve the **10 MHz signal collapse** caused by high-resistance multiplexers and to optimize the board footprint using Surface Mount Technology (SMT).

---

## 1. The Core Performance Fix: 5 $\Omega$ Switching
The Rev A prototype used **74HC4051** multiplexers, which exhibit an internal "On-Resistance" ($R_{on}$) of approximately **80–100 $\Omega$**. When combined with bus and cable capacitance, this created an $RC$ low-pass filter that "rounded" 10 MHz square waves into unusable "shark fins".

**Rev B Solution:**
* **Component:** **SN74CBT3251** (Digital Bus Switch).
* **Impact:** Reduces $R_{on}$ to **5 $\Omega$**, effectively eliminating the bottleneck and restoring sharp signal edges at 10 MHz.



---

## 2. Option A: The "Hand-Solder" Rev B
Designed for manual assembly using a standard soldering iron. This option uses **SOIC** packages with a **1.27mm pin pitch**, which are significantly easier to handle than the high-density TQFP or QFN alternatives.

### Chip Selection (Hand-Solder)
| Function | Component | Package | Note |
| :--- | :--- | :--- | :--- |
| **Main MCU** | **PIC18F27Q43-I/SO** | 28-SOIC | 64MHz, Master Clock Generator, DMA. |
| **I/O Expander** | **MCP23S17-E/SO** | 28-SOIC | [cite_start]Uses 3 units to offload Z80 Address and Data buses [cite: 240-243]. |
| **Bus MUX** | **SN74CBT3251DR** | 16-SOIC | Provides 5 $\Omega$ high-speed signal path. |
| **Transceiver** | **74ABT245DW** | 20-SOIC | [cite_start]SOIC version of the ABT logic used in Rev A[cite: 77]. |

[cite_start]**Architecture Change:** Since the 28-pin SOIC PIC has fewer pins than the 40-pin DIP, the **Z80 Data Bus** is moved to a third SPI-based MCP23S17 expander [cite: 240-243].

---

## 3. Option B: The "Ultra-Compact" Rev B (JLC PCBA)
If utilizing professional PCBA services (like JLC), we can exploit high-density packaging to drastically reduce the card size and potentially eliminate the need for multiple I/O expanders.

### Chip Selection (PCBA Optimized)
| Function | Component | Package | Advantage |
| :--- | :--- | :--- | :--- |
| **Main MCU** | **PIC18F47Q43-I/PT** | **44-TQFP** | Restores full 40+ I/O pins in a 10x10mm area; eliminates 3rd expander. |
| **I/O Expander** | **MCP23S17-E/SS** | **28-SSOP** | 0.65mm pitch; roughly 50% smaller than the SOIC version. |
| **Bus MUX** | **SN74CBT3251PWR** | **16-TSSOP** | Ultra-thin package; allows MUXes to be grouped tightly near the bus. |
| **Passives** | **0603 Metric** | SMD | [cite_start]Replaces bulky axial resistors/tantalums[cite: 61, 62]. |

**Size Reduction:** This move reduces the vertical height of the card by $\sim$40% and allows for a 4-layer PCB design, providing a dedicated ground plane to further reduce the "Ghost Mode" ringing observed in Rev A.

---

## 4. Hardware Logic & Master Clock Master
In Rev B, the PIC moves from a "passive listener" to a **Clock Master**.
* **NCO/PWM:** The PIC generates `MCLK` and `CLK` natively, allowing the Python host to request "Step" or "Slo-Mo" execution.
* [cite_start]**Wait-State Insertion:** The PIC can monitor `~WAIT` and hold the clock automatically during slow SPI snapshots[cite: 216].



---

## 5. Software Compatibility
The MicroPython `Zx50Console` class remains largely the same, with minor adjustments to the `pin_map.py` to reflect the new SPI Chip Select (CS) logic for the third expander (in the SOIC version).

```python
# Revised SPI Map for Rev B (SOIC Option)
CS_PINS = {
    "ADDR_LOW":  "GPA0", # Expander 1
    "ADDR_HIGH": "GPA1", # Expander 2
    "DATA_BUS":  "GPA2", # Expander 3 (New)
    [cite_start]"DISPLAY":   "GPIO17" # Pico Native [cite: 222]
}
```
