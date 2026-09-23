# Zx50 CPU Rev C1 Math & Stack Coprocessor Specification

This document details the architectural hardware specification and instruction set architecture (ISA) for the ATF1508AS CPLD Coprocessor Cluster integrated on the Zx50 CPU Card (Rev C1). The software interface and opcode matrix maintain **100% binary compatibility** with the Zx50 Coprocessor Specification.

---

## 1. System Overview & Hardware Architecture

The Rev C1 CPU Card integrates a dedicated CPLD coprocessor cluster on the bottom layer of a 6-layer PCB, positioned under the Clock Mezzanine RF ground shield. It features an **ATF1508AS-7 CPLD** (`U11`) operating on an isolated **16 KB private memory bus**, decoupled from the main Z80 backplane.

```text
                  +-----------------------------------+
                  |   ATF1508AS CPLD (PLCC-84 / U11)  |
                  |   Clocks: 20/40MHz MCLK, 5/10MHz ZCLK|
                  +-----+-----------------------+-----+
                        |                       |
           CA[13:0]     |                       |  CD[7:0]
         Private Address|                       |  Private Data
                        v                       v
            +-----------+-----------------------+-----------+
            |                                               |
            |   +-------------------+   +---------------+   |
            |   | SST39SF040 Flash  |   | IS61C5128AS   |   |
            |   | 16KB Active (U13) |   | 16KB Active   |   |
            |   | LUTs / Tables     |   | SRAM (U12)    |   |
            |   +---------+---------+   +-------+-------+   |
            |             |                     |           |
            |             | ~F_CE / ~F_OE / ~F_WE| ~M_CE / ~M_OE / ~M_WE
            +-------------+---------------------+-----------+
```

### Key Hardware Specs

* **CPLD Controller (`U11`):** Microchip ATF1508AS-7JX84 (128 macrocells, 7.5 ns $t_{PD}$, 84-pin PLCC).
* **Private SRAM (`U12`):** IS61C5128AS (25 ns, SOP-32). Address lines `CA0`–`CA13` (16 KB active); `A14`–`A18` tied to `GND`. Serves as hardware stack storage, scratchpad, and microcode buffer.
* **Private Flash (`U13`):** SST39SF040 (55 ns, PLCC-32). Address lines `CA0`–`CA13` (16 KB active); `A14`–`A18` tied to `GND`. Stores Quarter-Square multiplication tables, log/antilog tables, and trigonometric seed constants.
* **Dual Clock Domains:** Ingests `MCLK` (20/40 MHz) on `GCLK1` (Pin 83) and `ZCLK` (`CLK`, 5/10 MHz) on `GCLK2` (Pin 2).
* **Backplane Protection:** Controlled by transceivers (`U2`, `U3`, `U5`, `U7`), isolating the CPU card from the backplane during autonomous operations or DMA transfers.

---

## 2. Bus Signal Mapping

### Z80 Host Interface (`U11` CPLD)

| Signal Group | Signal Names | CPLD Pin Assignments | Description |
| --- | --- | --- | --- |
| **Z80 Address** | `A0`–`A15` | Pins 21, 20, 18, 17, 16, 15, 12, 11, 10, 9, 8, 6, 5, 4, 79, 80 | Buffered Z80 host address bus |
| **Z80 Data** | `D0`–`D7` | Pins 30, 31, 28, 24, 22, 25, 27, 29 | Bidirectional Z80 host data bus |
| **Z80 Control** | `~RD`, `~WR`, `~IORQ`, `~MREQ`, `~M1` | Pins 77, 76, 74, 75, 73 | Bus cycle and transfer control inputs |
| **Handshake / Status** | `~WAIT`, `~INT`, `~RESET`, `~BUSACK` | Pins 70, 69, 1, 84 (tied to GND) | Bus hold, interrupt, reset, and isolation signals |
| **Clocks** | `MCLK`, `CLK` (`ZCLK`) | Pins 83 (`GCLK1`), 2 (`GCLK2`) | High-speed coprocessor clock and host CPU clock |

### Private Memory Bus Interface & Config Pins

| Signal Group | Signal Names | CPLD Pin Assignments | Destination / Description |
| --- | --- | --- | --- |
| **Private Address** | `CA0`–`CA13` | Pins 56, 54, 55, 52, 51, 50, 49, 48, 61, 63, 65, 64, 58, 60 | `U12` SRAM & `U13` Flash (`A0`–`A13`) |
| **Private Data** | `CD0`–`CD7` | Pins 33, 34, 35, 36, 37, 39, 40, 41 | Bidirectional private memory data bus |
| **SRAM Control** | `~M_CE`, `~M_OE`, `~M_WE` | Pins 46, 45, 44 | Controls private SRAM (`U12`) |
| **Flash Control** | `~F_CE`, `~F_OE`, `~F_WE` | Pins 68, 67, 57 | Controls private Flash (`U13`) |
| **Speed Select** | `MEM_SPD` | Pin 81 | Hardware Memory Pipeline Speed Selector (Jumper `J8`) |

---

## 3. Register & I/O Interface Protocol

The CPLD decodes host I/O port base address `0x70` (or `0x71` depending on system configuration).

| Port Address | Operation | Register Name | Description |
| --- | --- | --- | --- |
| **`0x70`** | Write | `DATA_PUSH` | Pushes 1 byte to Top of Stack ($TOS$) in private SRAM, auto-incrementing byte pointer. |
| **`0x70`** | Read | `DATA_POP` | Reads 1 byte from Top of Stack ($TOS$) in private SRAM, auto-decrementing byte pointer. |
| **`0x71`** | Write | `CMD_EXEC` | Writes opcode to execution FSM, pulls `~WAIT` low, and executes computation. |
| **`0x71`** | Read | `STATUS` | Returns status flags: `[BUSY, ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW, ERR, 0]`. |

### Status Register Bit Flags (`0x71` Read)

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BUSY` | `ZERO` | `SIGN` | `CARRY` | `OVERFLOW` | `UNDERFLOW` | `ERR` | Reserved (0) |

* **`BUSY` (Bit 7):** High during math execution or table lookups.
* **`ERR` (Bit 1):** Set high if an illegal opcode, divide-by-zero, or unsupported format is requested.

---

## 4. Stack Memory Architecture

The math stack is hosted in the **first 256 bytes of Private SRAM (`U12`)** at addresses `0x0000`–`0x00FF`. The 8-bit Stack Pointer counter ($SP$) resides inside the CPLD.

```text
       32-Bit / 16.16 Fixed-Point Stack                64-Bit Double Precision Stack
    +------------------------------------+       +------------------------------------+
0x00| TOS  (Top of Stack) - Byte 0 (LSB) |   0x00| TOS  (Top of Stack) - Byte 0 (LSB) |
0x01| TOS                 - Byte 1       |   0x01| TOS                 - Byte 1       |
0x02| TOS                 - Byte 2       |   0x02| TOS                 - Byte 2       |
0x03| TOS                 - Byte 3 (MSB) |   ... | ...                                |
    +------------------------------------+   0x07| TOS                 - Byte 7 (MSB) |
0x04| NOS  (Next on Stack)- Byte 0       |       +------------------------------------+
... | ...                                |   0x08| NOS  (Next on Stack)- Byte 0       |
0x07| NOS                 - Byte 3       |   ... | ...                                |
    +------------------------------------+   0x0F| NOS                 - Byte 7       |
0x08| Stack Level 2                      |       +------------------------------------+
... | ...                                |   0x10| Stack Level 2                      |
0x1F| Stack Level 7 (8 Levels Max)       |   0x1F| Stack Level 3 (4 Levels Max)       |
    +------------------------------------+       +------------------------------------+
```

---

## 5. Instruction Set Architecture & Opcode Matrix

Opcodes written to port `0x71` are split into two 4-bit fields:

$$\text{Format Field} = \text{Opcode}[7:4] \quad \text{and} \quad \text{Operation Field} = \text{Opcode}[3:0] \quad \text{}$$

### Format Field (`opcode[7:4]`)

| Value | Identifier | Data Type            | Size / Operand | Hardware Acceleration Level |
| ----- | --------- | --------------------- | -------------- | --------------------------- |
| `0x0` | `i16`     | 16-Bit Signed Integer | 2 Bytes        | Native CPLD Hardware (1 Tick Add/Sub) |
| `0x1` | `i32`     | 32-Bit Signed Integer | 4 Bytes        | Native CPLD Hardware (1 Tick Add/Sub, 34 Tick Mult/Div) |
| `0x2` | `i64`     | 64-Bit Signed Integer | 8 Bytes        | Microcoded / Software Pass-through |
| `0x3` | `float` / `fx1616` | 32-Bit IEEE-754 / 16.16 Fixed | 4 Bytes | Native CPLD Hardware (16.16 Fixed) / Fast LUT |
| `0x4` | `dfloat`  | 64-Bit IEEE-754 Float | 8 Bytes        | Microcoded (Private SRAM) |
| `0x5` | `cfloat`  | 32-Bit Complex Float ($a + bi$) | 8 Bytes | Dual-Pass Native 32-bit Core |
| `0xE` | `special` | Custom Extensions     | Custom          | CPLD Table Acceleration |
| `0xF` | `mgmt`    | Hardware / Stack Management | 0 Bytes   | Native CPLD Control Logic |

### Operation Field (`opcode[3:0]`) Matrix

| Op Value | Mnemonic | Supported Formats | Description | Execution Time (40 MHz MCLK) |
| ----- | ----- | --- | --- | --- |
| `0x0` | `ADD` | `0x0`–`0x5` | Addition ($TOS = NOS + TOS$) | $25\text{ ns}$ ($i16/i32/fx1616$) |
| `0x1` | `SUB` | `0x0`–`0x5` | Subtraction ($TOS = NOS - TOS$) | $25\text{ ns}$ ($i16/i32/fx1616$) |
| `0x2` | `MUL` | `0x0`–`0x5` | Multiplication ($TOS = NOS \times TOS$) | $0.85\ \mu\text{s}$ (Shift-and-Add) |
| `0x3` | `DIV` | `0x0`–`0x5` | Division ($TOS = NOS / TOS$) | $0.85\ \mu\text{s}$ (Restoring Shift) |
| `0x4` | `SQRT` | `0x0`–`0x4` | Square Root ($\sqrt{TOS}$) | $1.10\ \mu\text{s}$ (LUT + Iterative) |
| `0x5` | `CHS` | `0x0`–`0x5` | Change Sign ($TOS = -TOS$) | $25\text{ ns}$ |
| `0x6` | `SIN` | `0x3` | Sine ($\sin(TOS)$ via Flash LUT) | $0.15\ \mu\text{s}$ (3-Read LUT) |
| `0x7` | `COS` | `0x3` | Cosine ($\cos(TOS)$ via Flash LUT) | $0.15\ \mu\text{s}$ (3-Read LUT) |
| `0x8` | `EXP` | `0x3` | Exponential ($e^{TOS}$ via Flash LUT) | $0.20\ \mu\text{s}$ |
| `0x9` | `LN` | `0x3` | Natural Log ($\ln(TOS)$ via Flash LUT) | $0.20\ \mu\text{s}$ |
| `0xA` | `LOG10` | `0x3` | Base-10 Log ($\log_{10}(TOS)$ via Flash LUT) | $0.20\ \mu\text{s}$ |
| `0xB` | `LOG_MUL` | `0x1`, `0x3` | Fast Log-Table Multiply | $0.10\ \mu\text{s}$ (3-Read LUT) |
| `0xC` | `LOG_DIV` | `0x1`, `0x3` | Fast Log-Table Divide | $0.10\ \mu\text{s}$ (3-Read LUT) |

### Management Opcodes (`Format = 0xF`)

| Full Opcode | Mnemonic | Description | Latency |
| --- | --- | --- | --- |
| **`0xF0`** | `CLR_STK` | Resets Stack Pointer to `0x0000` | $25\text{ ns}$ |
| **`0xF1`** | `POP_TOS` | Drops $TOS$ (decrements $SP$ by active stride) | $25\text{ ns}$ |
| **`0xF2`** | `DUP_TOS` | Duplicates $TOS$ entry on stack in SRAM | $100\text{ ns}$ |
| **`0xFF`** | `RESET` | Soft resets execution state machine & flags | $25\text{ ns}$ |

---

## 6. Execution FSM Logic & Timing

```text
                    +--------------------+
                    |     ST_IDLE        |  Listen on I/O Ports
                    +--------------------+
                              |
                     Opcode Write (0x71)
                              |
                              v
                    +--------------------+
                    |     ST_ISOLATE     |  Assert ~WAIT (Pin 70)
                    +--------------------+
                              |
                              v
                    +--------------------+
                    |     ST_FETCH_MEM   |  1 or 2-Tick SRAM/Flash Access
                    +--------------------+  Fetch Operands from U12/U13
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
   +--------------------+            +--------------------+
   |   ST_BIT_SERIAL    |            |   ST_TABLE_LOOKUP  |
   | (ADD/SUB/MUL/DIV)  |            |  (LOG/SIN/COS/EXP) |
   +--------------------+            +--------------------+
   | 1/34 MCLK Ticks    |            | 3-4 Private Memory |
   | Shift/Add Engine   |            | Read Cycles        |
   +--------------------+            +--------------------+
             |                                 |
             +----------------+----------------+
                              |
                              v
                    +--------------------+
                    |    ST_WRITEBACK    |  Store Result in U12 SRAM
                    +--------------------+  Update SP Counter
                              |
                              v
                    +--------------------+
                    |     ST_RELEASE     |  Deassert ~WAIT
                    +--------------------+  Return Status
```

### Memory Pipeline Rules & Speed Selection (`MEM_SPD`)

Private memory access pipeline timing is hardware-configurable via **Pin 81 (`MEM_SPD` / Jumper `J8`)**:

> **Memory Speed Mode (`MEM_SPD` / Pin 81):**
> * **`HI` (Logic 1 / Pull-up):** **1-Cycle Access** (Single `MCLK` tick per access; ideal for lower clock speeds or ultratight execution windows).
> * **`LOW` (Logic 0 / Shorted to GND):** **2-Cycle Access** (Two `MCLK` ticks per access; $2 \times 25\text{ ns} = 50\text{ ns}$ access window, safe default for $40\text{ MHz}$ `MCLK` with $25\text{ ns}$ SRAM).

---

# Simulation & Verilog Architecture Setup

## 1. Environment Overview & Module Hierarchy

The simulation model is structured in hierarchical layers to validate timing, bus isolation, and instruction execution—ranging from individual memory chips up to the backplane and clock generators.

```text
tb_zx50 (Testbench Top)
 ├── zx50_clock           (Clock Mezzanine BFM: Glitch-free MCLK / ZCLK generation)
 ├── zx50_backplane       (Passive Backplane: Weak pull-ups for Z80 & Shadow Bus)
 └── zx50_cpu_card        (Full CPU Rev C1 Board Level Model)
      ├── z80_cpu_util    (Z80 Bus Functional Model: T-State accurate driver)
      ├── Bus Drivers     (74ABT245 transceivers, d_dir, wait_gen, firewall logic)
      └── zx50_fpu_block  (FPU Subsystem Block)
           ├── zx50_fpu   (U11 - ATF1508AS CPLD Core Engine)
           ├── is61c5128as(U12 - 16KB Active Private SRAM Model)
           └── sst39sf040 (U13 - 16KB Active Private Flash ROM Model)
```

---

## 2. Component Organization & Responsibilities

### System & Testbench Layer

* **`zx50_clock.v` (Clock Mezzanine Model):** Digital twin of the hardware clock generator. Uses a dual flip-flop architecture to produce phase-locked `MCLK` (20/40 MHz) and `ZCLK` (5/10 MHz) with synchronous clock-gating to prevent runt clock pulses.
* **`zx50_backplane.v` (Passive Backplane):** Implements pull-up primitives on all backplane control, address, and data lines. Prevents floating `Z` states from turning into `X` states during bus handoffs while modeling real bus termination.
* **`z80_cpu_util.v` (Z80 Bus Functional Model):** Emulates Z80 processor bus cycles. Generates accurate $T$-state timing for memory/IO operations and samples `wait_n` on falling clock edges to stall execution identically to Z80 silicon.

---

### FPU Subsystem Cluster (`zx50_fpu_block.v`)

`zx50_fpu_block.v` acts as the structural wrapper for the isolated math coprocessor cluster. It encapsulates:

* **`zx50_fpu.v` (CPLD Core):** Top-level Verilog for the ATF1508AS CPLD (`U11`). Contains the host register decoder, execution FSM, stack pointer counter, and private memory controller.
* **`is61c5128as.v` (Private SRAM `U12`):** Verilog model for the 25 ns `IS61C5128AS` SRAM. Features $25\text{ ns}$ read access timing, $8\text{ ns}$ high-Z output disable, and trailing-edge write sampling (`posedge we_n`).
* **`sst39sf040.v` (Private Flash `U13`):** Verilog model for the 55 ns `SST39SF040` Flash ROM. Supports `$readmemh` initialization for math LUTs (logarithms, trigonometric tables) and models both JEDEC write command sequences and direct testbench writes.
* **Private Bus Isolation (`CA[13:0]`, `CD[7:0]`):** The wrapper maintains private 14-bit address (`CA[13:0]`) and 8-bit data (`CD[7:0]`) traces between the CPLD, SRAM, and Flash, preventing local math memory traffic from spilling onto the host CPU card bus.

---

## 3. Planned Top-Level Integration (`zx50_cpu_card.v`)

To simulate the complete Zx50 CPU Card (Rev C1 schematic `zx50_cpu_revc1.net`), a top-level board module (`zx50_cpu_card.v`) will be integrated.

### Integrated Submodules & Logic

1. **`zx50_fpu_block` Instance:** Houses the coprocessor cluster described above.
2. **`z80_cpu_util` Instance:** Drives the internal card bus as the primary CPU core.
3. **Bus Transceivers & Firewalls:** Behavioral models of the `74ABT245` bidirectional transceivers (`U2`, `U3`, `U5`, `U7`) that isolate the card from the backplane.
4. **Control Logic (`d_dir`, `wait_gen`):**
   * **`d_dir` Logic:** Decodes data direction for internal vs. external backplane transfers.
   * **`wait_gen` Logic:** Combines wait requests from the onboard MMU, main memory, and CPLD `wait_n` line to stall the Z80 BFM during math calculations or slow I/O cycles.

---

# Appendix: Advanced Bus-Snooping Architecture (Future Extension)

## 1. Overview & Concept

While the Rev B1 CPLD primary interface uses conventional I/O port transfers (`0x70` / `0x71`), the CPLD hardware architecture (`U11`) continuously monitors the Z80 control lines (`~M1`, `~MREQ`, `~RD`) and full address/data buses.

Under **Bus-Snooping**, the CPLD passive-observes standard Z80 memory read cycles (`~M1` = 1, `~MREQ` = 0, `~RD` = 0) and shadow-copies data bytes directly off the backplane into private SRAM (`U12`). This transfers math operands into the coprocessor stack simultaneously as the Z80 executes its normal instruction flow, eliminating explicit `OTIR` I/O write loops.

---

## 2. Snooper Arming Mechanisms

To prevent the CPLD from capturing arbitrary memory reads during normal application code, the CPLD snoop engine must be **armed** before capturing bytes.

```text
                  +-----------------------------------+
                  |          CPLD IDLE STATE          |
                  +-----------------+-----------------+
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
    Option A: Port Write    Option B: 0xED Prefix   Option C: RST $28
    OUT (0x71), ARM_CMD     Fetch ED xx Opcode      Fetch 0xEF Instruction
            |                       |                       |
            +-----------------------+-----------------------+
                                    |
                                    v
                  +-----------------------------------+
                  |      ARMED / SNOOPING STATE       |
                  |  Capture N Data Reads (~M1 = 1)   |
                  +-----------------+-----------------+
                                    |
                        Snoop Counter Decrements to 0
                                    |
                                    v
                  +-----------------------------------+
                  |   EXECUTE MATH / DISARM ENGINE    |
                  +-----------------------------------+
```

### Option A: Explicit Port Write Arming

* **Mechanism:** The Z80 writes an arming command byte to port `0x71` (e.g., opcode `0xF4` = *Arm Snoop 4 Bytes*, `0xF8` = *Arm Snoop 8 Bytes*).
* **Execution:** The CPLD sets an internal counter and arms its snoop register. The next $N$ non-`~M1` memory reads on the bus are copied into $TOS$ in private SRAM.
* **Pros/Cons:** Zero risk of false triggers; trivial CPLD decoding logic.

### Option B: Undocumented `0xED` Opcode Prefix Capture

* **Mechanism:** The CPLD decodes `~M1` opcode fetches looking for an unmapped `0xED` prefix sequence (e.g., `0xED 0x38`).
* **Execution:** On CMOS Z80 CPUs (`Z84C00`), unused `0xED` prefix pairs execute as 2-byte, 8-$T$-state `NOP` instructions. The Z80 advances `PC` safely while the CPLD arms its snoop state machine.
* **Pros/Cons:** Eliminates I/O port decoding cycles; requires 2-byte instruction decoding logic in CPLD.

### Option C: `RST $28` (`0xEF`) Inline Parameter Block

* **Mechanism:** The Z80 executes `RST 28h` (`0xEF`, 1 byte, 11 $T$-states). The math parameters are placed inline in memory immediately following the `RST` instruction byte.
* **Execution:** As the `RST` handler (or CPLD) increments the return address on the stack, the CPLD snoops the data bytes directly following `0xEF` as they are read from ROM/RAM.
* **Pros/Cons:** Extremely compact software call footprint; requires stack-frame return address adjustment.

---

## 3. Interrupt Guarding Requirement (`DI` / `EI`)

If an Interrupt Service Routine (ISR) fires during an active snoop window, the Z80 pauses the main program, pushes registers to the stack (memory writes), and fetches ISR instructions (memory reads).

Without protection, the CPLD would mistake the ISR's memory reads for math operands, corrupting the coprocessor stack.

### Required Software Pattern

Any snooped sequence must be wrapped in `DI` (Disable Interrupts) and `EI` (Enable Interrupts) to guarantee atomicity:

```assembly
    DI                  ; Disable interrupts (4 T-states)
    OUT (0x71), A       ; Arm CPLD for 4-byte snoop (11 T-states)
    LD  HL, (OPERAND_A) ; CPLD snoops bytes 0 & 1 (16 T-states)
    LD  DE, (OPERAND_B) ; CPLD snoops bytes 2 & 3 (16 T-states)
    OUT (0x71), C       ; Trigger Math Opcode & Disarm (11 T-states)
    EI                  ; Re-enable interrupts (4 T-states)
```

---

## 4. Z80 Cycle Performance Comparison

Below are timing calculations comparing standard **Port-Based Block I/O (`OTIR` / `INIR`)** versus **Port-Armed Bus Snooping** for 4-byte (32-bit) and 8-byte (64-bit / dual 32-bit) math operations.

### Assumptions

* **Z80 Instruction Timings:** `DI` / `EI` = $4\ T$, `OUT (n), A` = $11\ T$, `LD BC, (nn)` = $16\ T$, `OTIR` = $(N-1) \times 21 + 16\ T$, `INIR` = $(N-1) \times 21 + 16\ T$.
* **CPLD Hardware Hold (`~WAIT`):** $8.5\ T$-states ($34\text{ MCLK ticks}$ at 4:1 clock ratio).
* **Result Readback:** Results are returned via standard `INIR` block read.

---

### Case 1: 4-Byte Payload (Single 32-Bit Operand Input + 32-Bit Result)

#### Conventional Port-Based Method (`OTIR` + `INIR`)

```assembly
    LD   C, 0x70        ; Setup port (7 T)
    OTIR                ; Send 4 bytes operand (79 T)
    LD   A, CMD_ADD32   ; Load command (7 T)
    OUT  (0x71), A      ; Trigger math (11 T)
    ; --- CPLD WAIT Hold: 8.5 T ---
    INIR                ; Read 4 bytes result (79 T)
```

* **Total Conventional Clock Time:** $7 + 79 + 7 + 11 + 8.5 + 79 = \mathbf{191.5\ T\text{-states}}$

#### Port-Armed Snooping Method

```assembly
    DI                  ; Guard snoop window (4 T)
    OUT  (0x71), ARM_4  ; Arm 4-byte snoop (11 T)
    LD   HL, (OP_32)    ; Read bytes 0 & 1 -> Snooped! (16 T)
    LD   DE, (OP_32+2)  ; Read bytes 2 & 3 -> Snooped! (16 T)
    OUT  (0x71), ADD32  ; Trigger math (11 T)
    EI                  ; Re-enable interrupts (4 T)
    ; --- CPLD WAIT Hold: 8.5 T ---
    INIR                ; Read 4 bytes result (79 T)
```

* **Total Snooped Clock Time:** $4 + 11 + 16 + 16 + 11 + 4 + 8.5 + 79 = \mathbf{149.5\ T\text{-states}}$
* **Net Performance Gain:** **$42\ T\text{-states}$ saved ($\mathbf{1.28\times}$ Speedup / 22% Reduction)**

---

### Case 2: 8-Byte Payload (Two 32-Bit Operands Input + 32-Bit Result)

#### Conventional Port-Based Method (`OTIR` + `INIR`)

```assembly
    LD   C, 0x70        ; Setup port (7 T)
    OTIR                ; Send 8 bytes operands (163 T)
    LD   A, CMD_ADD32   ; Load command (7 T)
    OUT  (0x71), A      ; Trigger math (11 T)
    ; --- CPLD WAIT Hold: 8.5 T ---
    INIR                ; Read 4 bytes result (79 T)
```

* **Total Conventional Clock Time:** $7 + 163 + 7 + 11 + 8.5 + 79 = \mathbf{275.5\ T\text{-states}}$

#### Port-Armed Snooping Method

```assembly
    DI                  ; Guard snoop window (4 T)
    OUT  (0x71), ARM_8  ; Arm 8-byte snoop (11 T)
    LD   HL, (OP_A)     ; Op A Bytes 0 & 1 -> Snooped! (16 T)
    LD   DE, (OP_A+2)   ; Op A Bytes 2 & 3 -> Snooped! (16 T)
    LD   BC, (OP_B)     ; Op B Bytes 0 & 1 -> Snooped! (16 T)
    LD   IX, (OP_B+2)   ; Op B Bytes 2 & 3 -> Snooped! (20 T)
    OUT  (0x71), ADD32  ; Trigger math (11 T)
    EI                  ; Re-enable interrupts (4 T)
    ; --- CPLD WAIT Hold: 8.5 T ---
    INIR                ; Read 4 bytes result (79 T)
```

* **Total Snooped Clock Time:** $4 + 11 + 16 + 16 + 16 + 20 + 11 + 4 + 8.5 + 79 = \mathbf{185.5\ T\text{-states}}$
* **Net Performance Gain:** **$90\ T\text{-states}$ saved ($\mathbf{1.49\times}$ Speedup / 33% Reduction)**

---

### Key Takeaway

Bus snooping eliminates the high per-byte iteration penalty ($21\ T$-states/byte) of Z80 block I/O loops (`OTIR`).

Furthermore, if the host application **already needed those variable values loaded into Z80 registers** for local conditional checks, the data fetch overhead ($32\text{ to }68\ T$-states) is essentially **free**, pushing the effective hardware speedup past **$\mathbf{1.8\times}$**.