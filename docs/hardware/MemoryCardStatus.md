# Project Checkpoint: Z80 Universal Shadow Bus CPLD

## 1. The Hardware Status: VERIFIED
* **The Problem:** The CPLD was pulling 0.5A, getting dangerously hot, and causing bus contention.
* **The Fix:** The 0805 LEDs on the `~CE` lines were preventing the 10k pull-ups from pulling the bus to a solid 5V. We bodged 10k resistors directly across the outermost pads of the LED/Resistor pairs, bypassing the diode drop.
* **The Litmus Test:** Flashing a "blank slate" (all pins input/tri-stated) dropped the board's current draw to a cool, healthy **114mA**. The physical hardware, memory chips, and CPLD silicon are 100% healthy.

## 2. The Logic Pivot: Centralized Master State Machine
* **The Old Architecture:** Decentralized logic. The DMA, MMU, and Bus Arbiter were independent modules using combinatorial flags (`dma_is_active`, `sh_busy_n`) to negotiate control.
* **The Bug:** This caused nanosecond race conditions (e.g., the "Elevator Deadlock," where yielding the local bus accidentally cancelled the backplane request), leading to the transceivers staying closed and yielding `0xFF` data corruption during card-to-card DMA transfers.
* **The New Architecture:** We are abandoning whack-a-mole patching. We are building a strict, top-down **Master State Machine (Moore Machine)**. The sub-modules (DMA, MMU) will be stripped of their internal state machines and reduced to "dumb" datapaths. A single top-level controller will dictate exactly what every transceiver and memory pin is doing at any given time.

## 3. The State Table Rules
We are defining a CSV matrix of pin invariants *before* writing any Verilog.
* **No Blanks:** Every cell must be explicitly defined to prevent the synthesizer from inferring latches.
* **`OUT (value)` vs. `OUT`:** * `OUT (1b0)` means the pin is hardcoded to `0` for that entire state.
    * `OUT` means the Master State Machine claims ownership of the pin, but delegates the exact value (0, 1, or Z) to the underlying datapath logic.
* **Break-Before-Make:** Transitions between bus owners must pass through `MUTE` states to prevent physical transceiver shoot-through.

## 4. Current Matrix Progress: Group 1 (Locked)
We have successfully defined the **Open-Drain / Backplane Control Group** (`INT_N`, `WAIT_N`, `SH_BUSY_N`):
* **`MUTE_PASSIVE`:** All open-drain lines yield to `Z`. The card drops off the bus silently and instantly.
* **`MUTE_ACTIVE`:** The card asserts `WAIT_N = 0` and `SH_BUSY_N = 0` (the "brick wall") to freeze the Z80 and the Shadow Bus while its transceivers spin up.
* **Master vs. Slave Handoff:** During a DMA transfer, the Master listens (`IN`) to `SH_BUSY_N`, while the Slave drives (`OUT`) `SH_BUSY_N` to stall the Master if it needs to refresh or wait.
* **Interrupts:** `INT_N` is asserted via `OUT (1b0)` and cleanly released via `Z`.

## 5. Next Steps (Upon Resume)
When we return to the CSV, we need to fill in the invariant states for the remaining pin groups:
1.  **Group 2 (Address & LUT Routing):** `L_A`, `ATL_A`, `ATL_D`, `ATL_OE_N`. Define when the Z80 drives the addresses versus when the internal DMA counter drives them.
2.  **Group 3 (Local Memory Controls):** `CE_N`, `OE_N`, `WE_N`. Define exact chip-select logic to ensure internal SRAMs don't fight the backplane transceivers.

