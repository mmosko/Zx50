# Zx50 Serial I/O & Timer Card (CTC + DART)

**Current Status:** Schematic and netlist verified. PCB trace routing in progress.

## 1. Overview
This card provides the Zx50 system with its primary human-machine interface (via two serial ports) and precision hardware timing. It combines a **Z80 DART** (Dual Asynchronous Receiver/Transmitter) for serial communications and a **Z80 CTC** (Counter/Timer Circuit) for programmable baud rate generation and system tick interrupts.

## 2. Core Chip Manifest
1. **Z80 DART (Z84C4010PEC):** 10MHz CMOS dual serial controller.
2. **Z80 CTC (Z84C30):** The 4-channel timer (provides baud rate clocks to the DART and system ticks).
3. **74AHCT138:** 3-to-8 line decoder (Address slicing for the Z80 I/O space).
4. **MAX232ACPE+:** High-speed RS-232 level shifter charge-pump (Requires only 0.1 µF caps; dedicated to Serial Port 1).
5. **7.3728 MHz Oscillator:** A standard 4-pin active crystal oscillator can (feeds the CTC's clock inputs for baud rate division).
6. **FTDI DB9-USB-D5:** Standalone USB-to-TTL module (Physical connector and level translator for Serial Port 0).

## 3. The Output Stages (The Split Design)
* **Serial 0 (USB via FTDI):**
  * **Source:** Z80 DART Channel A.
  * **Connector:** FTDI DB9-USB-D5 module (`J3`).
  * **Voltages:** 5V TTL logic. The DART's logic lines are crossed over to interface correctly with the module: `TXDA` connects to `RXD`, `RXDA` connects to `TXD`, `RTSA` connects to `CTS`, and `CTSA` connects to `RTS`.
* **Serial 1 (Classic RS-232):**
  * **Source:** Z80 DART Channel B.
  * **Connector:** Standard Right-Angle DB9 Female (PCB Mount, wired as DCE).
  * **Voltages:** True RS-232 (±10V). The DART's `TxDB`, `RxDB`, `~RTSB~`, and `~CTSB~` pins route through the `MAX232ACPE+` level-shifting IC before hitting the DB9.
  * **Charge Pump:** Uses standard charge-pump topology with unpolarized 0.1 µF ceramic capacitors (DigiKey BC1101CT-ND).

## 4. Hardware Activity LEDs
To provide immediate visual feedback during data transmission, the board features hardware-driven activity LEDs:
* **Implementation:** High-efficiency LEDs (`D1`, `D2`) are connected to the `TxDA` and `TxDB` output pins of the DART, pulled to ground through 1KΩ current-limiting resistors (`R1`, `R2`).
* **Result:** The LEDs will naturally flicker exactly when bytes are being shifted out of the UART, requiring zero software overhead.

## 5. The Direct-Drive Baud Rate Engine
Because the system backplane runs at 8-10 MHz, the 7.3728 MHz oscillator connects directly to the CTC without violating Zilog timing limits.
* **The Clock:** The 7.3728 MHz oscillator feeds the CTC's clock inputs (`CLK/TRG0` and `CLK/TRG1`). 
* **The Routing:** * CTC Channel 0 Output (`ZC/TO0`) -> DART Channel A `RxCA` and `TxCA` pins.
  * CTC Channel 1 Output (`ZC/TO1`) -> DART Channel B `RxTxCB` pin.
* **Software Math:** By placing the CTC in "Counter Mode" and the DART in x16 multiplier mode, a CTC divisor of 4 yields 115,200 baud, and a divisor of 48 yields 9,600 baud.

## 6. Interrupt Priority & The Daisy Chain
Both the CTC and the DART utilize Z80 Mode 2 Vectored Interrupts. Because they sit on the same physical card, their interrupt priority is hardwired using the Zx50 Backplane's `IEI` and `IEO` lines.
* **Routing Path:** Backplane `IEI` -> CTC `IEI` | CTC `IEO` -> DART `IEI` | DART `IEO` -> Backplane `IEO`.
* **Priority:** The CTC has a higher interrupt priority than the DART. 

## 7. Addressing Configuration
Both chips connect directly to the unbuffered `D0-D7` backplane data bus, tri-stating themselves automatically.
* **Decoder (74AHCT138):** Slices the lower 8 bits of the address bus using `A2`, `A3`, and `A4`. Assuming a base address of `0x80`:
  * `0x80 - 0x83`: Mapped to the CTC `~CE`.
  * `0x84 - 0x87`: Mapped to the DART `~CE`.
* **Sub-Addressing:** `A0` and `A1` connect directly to the CTC (`CS0`, `CS1`) and DART (`B/~A`, `C/~D`) to select internal registers.
* **Address Mirroring Note:** Because address line `A5` is not connected to the decoder, it acts as a "don't care" bit. As a result, the CTC and DART will also mirror their addresses at `0xA0 - 0xA7`.