# Zx50 Shadow Bus Protocol Specification

The Shadow Bus is a secondary, high-speed DMA (Direct Memory Access) backplane designed to operate parallel to the primary Z80 bus. It allows coprocessors (Masters) to rapidly stream data to and from memory or peripherals (Targets) using a hardware-level cycle-stealing and burst protocol.

## 1. Signal Definitions

| Signal | Name | Direction | Active | Description |
| :--- | :--- | :--- | :--- | :--- |
| `~S_EN` | Shadow Enable | Master -> Target | LOW | Claims the bus and wakes up the Target. |
| `SRW` | Shadow Read/Write | Master -> Target | HIGH/LOW | Defines data direction (0 = Write to Target, 1 = Read from Target). |
| `~SSTB` | Shadow Strobe | Master -> Target | LOW | The primary data clock. Validates data on the bus. |
| `~SINC` | Shadow Increment | Master -> Target | LOW | Commands the Target to advance its internal address pointer. |
| `~S_BUSY` | Shadow Busy | Target -> Master | LOW | Asynchronous stall. Tells the Master to freeze its strobes. |
| `~S_DONE` | Shadow Done | Master -> Target | LOW | Terminal count flag. Indicates the current byte is the final byte. |

---

## 2. Phases of a Transfer

### Phase 1: The Setup (Master Driven)
To initiate a transfer, the Master must physically claim the bus:
1. The Master drives the initial address onto the Shadow Address bus.
2. The Master asserts `SRW` to declare the direction of the burst.
3. The Master asserts `~S_EN` LOW. It remains LOW for the entire duration of the burst block.

### Phase 2: The Data Pump (Master Driven)
Once the bus is claimed, the Master dictates the speed of the transfer using the strobe pins.
* **On a DMA Write (`SRW=0`):** The Master places data on the bus, then pulses `~SSTB` LOW to signal the Target to latch the data.
* **On a DMA Read (`SRW=1`):** The Master pulses `~SSTB` LOW to command the Target to drive data onto the bus. The Master latches the data on the rising edge of `~SSTB`.
* **Pointer Math:** The Master pulses `~SINC` LOW to tell the Target to increment its internal address tracker for the next byte. *(Note: `~SSTB` and `~SINC` can be pulsed simultaneously, but keeping them independent allows for error recovery or repeated reads).*

### Phase 3: Flow Control (Target Driven)
The Target uses `~S_BUSY` to prevent the Master from overrunning it (e.g., if the Target is a memory card currently serving a Z80 read cycle).
* **The Master's Golden Rule:** The Master MUST continuously sample `~S_BUSY`. 
* If `~S_BUSY` is pulled LOW by the Target, the Master must instantly freeze its state machine. It cannot issue any further `~SSTB` or `~SINC` pulses until the Target releases `~S_BUSY` back to HIGH.

### Phase 4: Termination (Master Driven)
When the Master reaches the end of its programmed transfer block:
1. During the `~SSTB` pulse of the **final byte**, the Master concurrently asserts `~S_DONE` LOW.
2. The Target latches the final byte, detects the `~S_DONE` flag, and triggers any necessary internal interrupts (e.g., "Buffer Full").
3. The Master releases `~S_EN` HIGH, returning the Shadow Bus to an idle (High-Z) state.

---

## 3. The Rules of Engagement (Summary)
1. **The Master dictates the pace, but the Target grants permission.** 2. A Master must never step on an active `~S_BUSY` line.
3. Transceivers on inactive cards must yield all Shadow Bus lines to `Z` (High-Impedance) to allow the backplane pull-up resistors to hold the bus in a clean, idle HIGH state.
