# Zx50 CPU Rev C2 Math & Stack Coprocessor Specification

This document details the architectural hardware specification, instruction set architecture (ISA), and microcoded execution engine for the ATF1508AS CPLD Coprocessor Cluster integrated on the Zx50 CPU Card (Rev C2). The Verilog codebase is written in standard Verilog for direct synthesis compatibility with legacy toolchains (Microchip/Atmel ProChip Designer, WinCUPL, Quartus II 13.0sp1) without SystemVerilog dependencies.

---

## 1. System Overview & Hardware Architecture

The Rev C2 CPU Card integrates a dedicated CPLD coprocessor cluster on the bottom layer of a 6-layer PCB, positioned under the Clock Mezzanine RF ground shield. It features an **ATF1508AS-7 CPLD** (`U11`) operating on an isolated **32 KB private memory bus**, decoupled from the main Z80 backplane.

```text
                  +-----------------------------------+
                  |   ATF1508AS CPLD (PLCC-84 / U11)  |
                  |   Clocks: 20/40MHz MCLK, 5/10MHz ZCLK|
                  +-----+-----------------------+-----+
                        |                       |
           CA[14:0]     |                       |  CD[7:0]
         Private Address|                       |  Private Data
                        v                       v
            +-----------+-----------------------+-----------+
            |                                               |
            |   +-------------------+   +---------------+   |
            |   | SST39SF040 Flash  |   | IS61C256AL    |   |
            |   | 32KB Active (U13) |   | 32KB Active   |   |
            |   | LUTs / Tables     |   | SRAM (U12)    |   |
            |   +---------+---------+   +-------+-------+   |
            |             |                     |           |
            |             |     ~C_OE / ~C_WE   |           |
            |             +----------+----------+           |
            |                        |                      |
            |               ~F_CE <--+--> ~M_CE             |
            +-----------------------------------------------+

```

### Key Hardware Specs

* **CPLD Controller (`U11`):** Microchip ATF1508AS-7JX84 (128 macrocells, 7.5 ns $t_{\text{PD}}$, 84-pin PLCC).


* **Private SRAM (`U12`):** ISSI `IS61C256AL-12TLI` (12 ns access time, 28-pin TSOP-I). Address lines `CA0`–`CA14` provide a full **32 KB active private memory space**. Serves as hardware stack storage, scratchpad, and microcode execution frame.


* **Private Flash (`U13`):** SST39SF040 (55 ns, PLCC-32). Address lines `CA0`–`CA14` (32 KB active); `A15`–`A18` tied to `GND`. Stores Quarter-Square multiplication tables, log/antilog tables, and trigonometric seed constants.


* **Consolidated Control Lines:** Memory read enable (`~C_OE`, Pin 45) and write enable (`~C_WE`, Pin 46) are consolidated into a shared pair of control strobes across both private memory ICs. Device targeting is gated by dedicated Chip Enable lines (`~M_CE` on Pin 44 for SRAM; `~F_CE` on Pin 68 for Flash), saving 2 macrocells and 2 package I/O pins on the CPLD.


* **High-Speed Single-Cycle Memory Access Timing:**
* At 40 MHz ($T_{\text{clk}} = 25\text{ ns}$), the **12 ns SRAM access time** ($t_{\text{AA}}$) provides **13 ns of timing margin** per clock cycle.


* Eliminates multi-cycle wait states and complex hold pipelines. Reads and writes execute as clean single-cycle transfers synchronized to `posedge mclk`.




* **Dual Clock Architecture & Asynchronous CDC Handshaking:**
* **`ZCLK` Domain (5/10 MHz):** Synchronously decodes Z80 I/O read/write cycles, updates the 8-bit Stack Pointer ($SP$), and drives host handshake lines (`wait_n`, `int_n`).


* **`MCLK` Domain (20/40 MHz):** Drives high-speed command execution, private SRAM/Flash pipeline timing, and microcoded math calculations.


* **4-Phase Level CDC Handshake:** Inter-domain requests (`exec_req` from `ZCLK` $\rightarrow$ `MCLK`) and acknowledgments (`done_ack` from `MCLK` $\rightarrow$ `ZCLK`) use level-driven handshaking with 2-stage synchronizers (`req_sync`, `ack_sync`). This guarantees zero pulse-dropping when crossing between asynchronous clock domains.





---

## 2. Bus Signal Mapping

### Z80 Host Interface (`U11` CPLD)

| Signal Group | Signal Names | CPLD Pin Assignments | Description |
| --- | --- | --- | --- |
| **Z80 Address** | `A0`–`A15` | Pins 21, 20, 18, 17, 16, 15, 12, 11, 10, 9, 8, 6, 5, 4, 79, 80 | Buffered Z80 host address bus|
| **Z80 Data** | `D0`–`D7` | Pins 30, 31, 28, 24, 22, 25, 27, 29 | Bidirectional Z80 host data bus|
| **Z80 Control** | `~RD`, `~WR`, `~IORQ`, `~MREQ`, `~M1` | Pins 77, 76, 74, 75, 73 | Bus cycle and transfer control inputs|
| **Handshake / Status** | `~WAIT`, `~INT`, `~RESET`, `~BUSACK` | Pins 70, 69, 1, 84 (tied to GND) | Open-drain `~WAIT`/`~INT` lines, reset, and isolation signals|
| **Clocks** | `MCLK`, `CLK` (`ZCLK`) | Pins 83 (`GCLK1`), 2 (`GCLK2`) | High-speed coprocessor clock and host CPU clock|

### Private Memory Bus Interface & Config Pins (Rev C2 Netlist)

| Signal Group | Signal Names | CPLD Pin Assignments | Destination / Description |
| --- | --- | --- | --- |
| **Private Address** | `CA0`–`CA14` | Pins 56, 54, 55, 52, 51, 50, 49, 48, 61, 63, 65, 64, 57, 58, 60 | `U12` SRAM & `U13` Flash (`A0`–`A14`)|
| **Private Data** | `CD0`–`CD7` | Pins 37, 36, 35, 34, 33, 41, 40, 39 | Bidirectional private memory data bus|
| **Shared Control** | `~C_OE`, `~C_WE` | Pins 45, 46 | Consolidated Output Enable and Write Enable strobes|
| **Chip Enables** | `~M_CE`, `~F_CE` | Pins 44, 68 | Dedicated Chip Enable for SRAM (`U12`) & Flash (`U13`)|
| **Speed Select** | `CLK_SPD` | Pin 81 | Hardware Memory Pipeline Speed Selector (Jumper `J8`)|

---

## 3. Register & I/O Interface Protocol

The CPLD decodes host I/O port base address `0x70` and `0x71`.

| Port Address | Operation | Register Name | Description |
| --- | --- | --- | --- |
| **`0x70`** | Write | `DATA_PUSH` | Pushes 1 byte to Top of Stack ($TOS$) in private SRAM, auto-incrementing byte pointer ($SP$).|
| **`0x70`** | Read | `DATA_POP` | Reads 1 byte from Top of Stack ($TOS$) in private SRAM, auto-decrementing byte pointer ($SP$).|
| **`0x71`** | Write | `CMD_EXEC` | Latches opcode to execution dispatcher (`zx50_fpu_dispatch`), pulls `~WAIT` low, and executes computation.|
| **`0x71`** | Read | `STATUS` | Returns status flags: `[BUSY, ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW, ERR, 0]`.|

### Status Register Bit Flags (`0x71` Read)

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BUSY` | `ZERO` | `SIGN` | `CARRY` | `OVERFLOW` | `UNDERFLOW` | `ERR` | Reserved (0)|

* **`BUSY` (Bit 7):** Set high during command execution; cleared automatically when the execution engine completes execution.


* **`ERR` (Bit 1):** Set high if an illegal opcode, divide-by-zero, or execution fault is encountered.



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

## 5. Microcoded Execution Datapath Architecture

To eliminate product-term explosion on the ATF1508AS CPLD (128 macrocells max), execution logic uses a **Microcoded Datapath Architecture** rather than separate state machines per opcode. All arithmetic operations, lookup queries, and memory moves route through a **single shared 16-bit ALU core** (`zx50_fpu_alu_core`) and a unified register file.

```text
               +-------------------------------------------------------+
               |                MICRO-SEQUENCER DISPATCHER             |
               | (Reads Microcode Steps from Internal Sequence Table)   |
               +---------------------------+---------------------------+
                                           |
                                           | Micro-Instruction Control Bus
                                           v
+-----------------------------------------------------------------------------------------+
|                                    UNIFIED DATAPATH BUS                                 |
|                                                                                         |
|  +--------------------+   +---------------------+   +--------------------------------+  |
|  |   MEM_BUS_ENGINE   |   |   16-BIT CORE ALU   |   |   REGISTER FILE / SCRATCHPAD   |  |
|  | - Read SRAM (TOS/NOS)| | - Add / Sub / Abs   |   | - ACC  (TOS Byte / Accumulator)|  |
|  | - Write SRAM (NOS) |   | - Shift Right / Left|   | - OPB  (NOS Byte / Sec Operand)|  |
|  | - Read Flash LUT   |   | - Pass-through      |   | - TMP0 (16-bit Scratch Pad 0)  |  |
|  +---------+----------+   +----------+----------+   | - TMP1 (16-bit Scratch Pad 1)  |  |
|            |                         |              +---------------+----------------+  |
|            +-------------------------+------------------------------+                   |
+-----------------------------------------------------------------------------------------+

```

### 5.1 Shared Datapath Registers & Scratchpad

| Register Name | Width | Functional Role |
| --- | --- | --- |
| **`ACC`** | 8 bits | Primary accumulator byte (latches TOS bytes during serial passes). |
| **`OPB`** | 8 bits | Secondary operand byte (latches NOS bytes during serial passes). |
| **`TMP0`** | 16 bits | Primary 16-bit scratchpad register (stores sum $a+b$, Flash lookup keys, or partial products). |
| **`TMP1`** | 16 bits | Secondary 16-bit scratchpad register (stores difference $\vert{}a-b\vert{}$, Flash lookup results, or divisors). |
| **`BYTE_CNT`** | 3 bits | Multi-byte iteration counter for 16-bit, 32-bit, and 64-bit frame traversal. |
| **`U_PC`** | 5 bits | Microcode Program Counter (pointers to active step in the sequence table). |

### 5.2 Micro-Instruction Control Word Definition

Every step in a calculation is defined by a standardized micro-instruction control vector:

| Field Name | Bit Width | Encoding / Function |
| --- | --- | --- |
| **`ALU_OP`** | 3 bits | `000`: Pass X, `001`: Add ($X+Y$), `010`: Sub ($X-Y$), `011`: Abs Diff ($\vert{}X-Y\vert{}$), `100`: Shift Right, `101`: Shift Left |
| **`SRC_X_SEL`** | 2 bits | Operand X Selector: `00` = `ACC`, `01` = `OPB`, `10` = `TMP0`, `11` = `TMP1` |
| **`SRC_Y_SEL`** | 2 bits | Operand Y Selector: `00` = `ACC`, `01` = `OPB`, `10` = `TMP0`, `11` = `TMP1` |
| **`MEM_CMD`** | 3 bits | `000`: NOP, `001`: Read SRAM TOS, `010`: Read SRAM NOS, `011`: Read Flash LUT (`ADDR` = `TMP`), `100`: Write SRAM NOS |
| **`REG_LD`** | 3 bits | Target Register Latch Strobe: `001`: `ACC`, `010`: `OPB`, `011`: `TMP0_LO`, `100`: `TMP0_HI`, `101`: `TMP1_LO`, `110`: `TMP1_HI` |
| **`STEP_CTRL`** | 2 bits | `00`: Advance `U_PC` + 1, `01`: Loop on `BYTE_CNT`, `10`: Assert `DONE_P` & Reset `U_PC` to 0 |

### 5.3 Microcode Sequence Example: Quarter-Square Multiplication (`OP_MUL`)

Quarter-Square multiplication computes $a \times b = f(a+b) - f(\vert{}a-b\vert{})$ where $f(n) = \lfloor n^2 / 4 \rfloor$. The operation is executed by the microcode sequencer in 10 deterministic steps:

1. **`STEP 10`**: `MEM_CMD = RD_SRAM_TOS` $\rightarrow$ Latch `ACC` ($a$).
2. **`STEP 11`**: `MEM_CMD = RD_SRAM_NOS` $\rightarrow$ Latch `OPB` ($b$).
3. **`STEP 12`**: `ALU_OP = ADD(ACC, OPB)` $\rightarrow$ Latch `TMP0` ($a+b$). `ALU_OP = ABS_DIFF(ACC, OPB)` $\rightarrow$ Latch `TMP1` ($\vert{}a-b\vert{}$).
4. **`STEP 13`**: `MEM_CMD = RD_FLASH_LUT(TMP0_LO)` $\rightarrow$ Latch `TMP0[7:0]` ($f(a+b)_{\text{lo}}$).
5. **`STEP 14`**: `MEM_CMD = RD_FLASH_LUT(TMP0_HI)` $\rightarrow$ Latch `TMP0[15:8]` ($f(a+b)_{\text{hi}}$).
6. **`STEP 15`**: `MEM_CMD = RD_FLASH_LUT(TMP1_LO)` $\rightarrow$ Latch `TMP1[7:0]` ($f(\vert{}a-b\vert{})_{\text{lo}}$).
7. **`STEP 16`**: `MEM_CMD = RD_FLASH_LUT(TMP1_HI)` $\rightarrow$ Latch `TMP1[15:8]` ($f(\vert{}a-b\vert{})_{\text{hi}}$).
8. **`STEP 17`**: `ALU_OP = SUB(TMP0, TMP1)` $\rightarrow$ Latch `TMP0` (Product $a \times b$).
9. **`STEP 18`**: `MEM_CMD = WR_SRAM_NOS(TMP0[7:0])` (Store LSB of result into SRAM).
10. **`STEP 19`**: `MEM_CMD = WR_SRAM_NOS(TMP0[15:8])` (Store MSB of result into SRAM) $\rightarrow$ `STEP_CTRL = DONE`.

---

## 6. Instruction Set Architecture & Opcode Matrix

Opcodes written to port `0x71` are split into two 4-bit fields:

```text
Format Field    = Opcode[7:4]
Operation Field = Opcode[3:0]

```

### Format Field (`opcode[7:4]`)

| Value | Identifier | Data Type | Size / Operand | Hardware Acceleration Level |
| --- | --- | --- | --- | --- |
| `0x0` | `i16` | 16-Bit Signed Integer | 2 Bytes | Native Microcode Datapath|
| `0x1` | `i32` | 32-Bit Signed Integer | 4 Bytes | Native Microcode Datapath (Byte-Serial Iteration)|
| `0x2` | `i64` | 64-Bit Signed Integer | 8 Bytes | Microcoded Loop Pass-through|
| `0x3` | `float` / `fx1616` | 32-Bit IEEE-754 / 16.16 Fixed | 4 Bytes | Native Microcode Datapath / Flash LUT Acceleration|
| `0x4` | `dfloat` | 64-Bit IEEE-754 Float | 8 Bytes | Microcoded (Private SRAM)|
| `0x5` | `cfloat` | 32-Bit Complex Float ($a + bi$) | 8 Bytes | Dual-Pass Native Microcode Core|
| `0xE` | `special` | Custom Extensions | Custom | Flash Table Acceleration|
| `0xF` | `mgmt` | Hardware / Stack Management | 0 Bytes | Native CPLD Control Logic|

### Management Opcodes (`Format = 0xF`)

| Full Opcode | Mnemonic | Description | Latency |
| --- | --- | --- | --- |
| **`0xF0`** | `CLR_STK` | Resets Stack Pointer to `0x0000` | $25\text{ ns}$<br> |
| **`0xF1`** | `POP_TOS` | Drops $TOS$ (decrements $SP$ by active stride) | $25\text{ ns}$<br> |
| **`0xF2`** | `DUP_TOS` | Duplicates $TOS$ entry on stack in SRAM | $100\text{ ns}$<br> |
| **`0xFF`** | `RESET` | Soft resets execution state machine & flags | $25\text{ ns}$<br> |

---

## 7. Simulation & Verilog Architecture Setup

### 7.1 Environment Overview & Module Hierarchy

The simulation environment uses a modular architecture where the CPLD core (`zx50_fpu.v`) delegates execution logic to the microcode engine while handling top-level bus interfacing.

```text
tb_zx50 (Testbench Top)
 ├── zx50_clock             (Clock Mezzanine BFM: Glitch-free MCLK / ZCLK generation)[cite: 11]
 ├── zx50_backplane         (Passive Backplane: Weak pull-ups for Z80 & Shadow Bus)[cite: 11]
 └── zx50_fpu_block         (FPU Subsystem Cluster Wrapper)[cite: 11]
      ├── zx50_fpu          (U11 - ATF1508AS CPLD Top Level Logic)[cite: 11]
      │    ├── zx50_fpu_dispatch    (Command Execution Dispatcher)[cite: 11]
      │    └── zx50_fpu_microengine (Unified Microcoded Execution Engine)
      │         └── zx50_fpu_alu_core (Single Shared 16-Bit Core ALU Primitive)
      ├── is61c256al_12     (U12 - 32KB Active Private SRAM Model)[cite: 11]
      └── sst39sf040        (U13 - 32KB Active Private Flash ROM Model)[cite: 11]

```

### 7.2 Source & Testbench File Index

#### Synthesis Source Files (`./src/`)

* **`src/zx50_fpu.v`:** Top-level CPLD logic. Manages Z80 I/O port decoding (`0x70`/`0x71`), stack pointer counter ($SP$), consolidated memory strobes (`c_oe_n`, `c_we_n`), chip enables (`m_ce_n`, `f_ce_n`), open-drain `wait_n`/`int_n` drivers, and CDC request synchronizers.


* **`src/zx50_fpu_mem.v`:** Private memory bus arbiter & strobe generator. Maps 15-bit private addresses (`CA0`–`CA14`), manages `clk_spd` wait states, and generates 1-cycle `mem_ready` completion pulses.


* **`src/zx50_fpu_dispatch.v`:** Command dispatcher submodule running on `MCLK`. Decodes opcodes, controls execution state timing, manages level CDC acknowledgment, and outputs arithmetic status flags.


* **`src/zx50_fpu_microengine.v`:** Unified Microcoded Execution Engine. Manages the shared scratchpad register file, drives the microcode step pointer (`U_PC`), and sequences data transfers between memory and the ALU core.
* **`src/zx50_fpu_alu_core.v`:** Single Shared 16-Bit Arithmetic Primitive. Performs addition, subtraction, absolute difference, and bit shifts for all microcode routines.
* **`src/zx50_fpu_block.v`:** Subsystem cluster wrapper. Integrates CPLD (`U11`), SRAM (`U12`), and Flash (`U13`) on private `CA[14:0]` and `CD[7:0]` buses.


* **`src/is61c256al_12.v`:** ISSI `IS61C256AL-12TLI` 12 ns SRAM simulation model.


* **`src/sst39sf040.v`:** SST39SF040 55 ns Flash ROM simulation model. Features explicit sensitivity lists and `$readmemh` pre-loading for math LUTs.


* **`src/fpu_rom_map.vh`:** Auto-generated Verilog header file containing Flash ROM base addresses and lookup table defines.
* **`src/fpu_microcode.vh`:** Micro-instruction word encodings, control bit masks, and `U_PC` entry point defines.

#### Testbench Suite (`./sim/`)

All testbenches follow pattern-based execution via `make run-<test>` (e.g., `make run-init`):

* **`sim/init_tb.v` (`make run-init`):** Verifies boot reset state, register defaults, private memory chip select isolation (`m_ce_n`, `f_ce_n`), and open-drain High-Z line releases.


* **`sim/fpu_stack_tb.v` (`make run-fpu_stack`):** Verifies Port `0x70` single-byte, multi-byte 32-bit frame, and interleaved PUSH/POP stack operations, $SP$ tracking, and single-cycle 12ns SRAM write timing.


* **`sim/fpu_cmd_tb.v` (`make run-fpu_cmd`):** Verifies Port `0x71` command execution, `ZCLK`/`MCLK` 4-phase CDC handshaking, automatic Z80 `wait_n` stall and release, and valid/invalid opcode status reporting (`BUSY`, `ERR`).


* **`sim/fpu_mem_tb.v` (`make run-fpu_mem`):** Verifies 20 MHz vs 40 MHz Flash ROM timing, SRAM single-cycle reads, 2-phase SRAM write hold timing, and dual-client arbitration.


* **`sim/fpu_microengine_tb.v` (`make run-fpu_microengine`):** Verifies microcode execution routines for addition (`OP_ADD`), subtraction (`OP_SUB`), negation (`OP_CHS`), and Quarter-Square multiplication (`OP_MUL`).

~~~
~~~


# Master Opcode & Flash LUT Inventory

By grounding higher-level math functions in logarithmic and exponential identities, we can support the complete opcode suite using four small Flash ROM lookup tables ($1\text{ KB}$ total):

| Opcode | Math Expression | Execution Strategy | Flash LUTs Used |
| --- | --- | --- | --- |
| **`ADD`** | $a + b$ | Multi-byte serial pass with carry | None |
| **`SUB`** | $a - b$ | Multi-byte serial pass with borrow | None |
| **`CHS`** | $-a$ | Two's complement negation ($0 - a$) | None |
| **`ABS`** | $\Vert{}a\Vert{}$ | Clear sign bit (byte 3) | None |
| **`MUL`** | $a \times b$ | Quarter-Square identity: $f(a+b) - f(\Vert{}a-b\Vert{})$ | `FLASH_QS_TABLE` |
| **`DIV`** | $a / b$ | Reciprocal multiply: $a \times \frac{1}{b}$ | `FLASH_RECIP_TABLE`, `FLASH_QS_TABLE` |
| **`SQRT`** | $\sqrt{x}$ | Seed lookup + 1 Newton-Raphson pass | `FLASH_SQRT_TABLE`, `FLASH_QS_TABLE` |
| **`EXP`** | $e^x$ | Range reduction: $2^{x \cdot \log_2(e)} = 2^I \times 2^F$ | `FLASH_EXP2_TABLE`, `FLASH_QS_TABLE` |
| **`LN`** | $\ln(x)$ | Log identity: $\log_2(x) \times \ln(2)$ | `FLASH_LOG2_TABLE`, `FLASH_QS_TABLE` |
| **`POW`** | $x^y$ | Log-Exponent chain: $2^{y \cdot \log_2(x)}$ | `FLASH_LOG2_TABLE`, `FLASH_EXP2_TABLE`, `FLASH_QS_TABLE` |

*Note on $\text{LN}(x)$:* Natural log requires zero new hardware logic or tables. It runs `LOG2(x)` and multiplies the result by the 16.16 constant $\ln(2) \approx 0.693147$ (`16'h00B1` in fixed-point).

---

### Micro-Operation (uOp) Bus Control Word

Every micro-step executed by `zx50_fpu_microengine` is encoded as a 15-bit micro-instruction word:

$$\text{uOp Word} = [\text{ALU\_OP}(3) \mid \text{SRC\_X}(2) \mid \text{SRC\_Y}(2) \mid \text{MEM\_CMD}(3) \mid \text{REG\_LD}(3) \mid \text{SEQ\_CTRL}(2)]$$

#### Field Definitions

1. **`ALU_OP[2:0]` (3 bits) — 16-Bit Shared ALU Command**
* `3'b000` (`ALU_PASS_X`) : Output = $X$
* `3'b001` (`ALU_ADD`)    : Output = $X + Y + \text{cin}$
* `3'b010` (`ALU_SUB`)    : Output = $X - Y - \text{cin}$
* `3'b011` (`ALU_ABS_D`)  : Output = $\Vert{}X - Y\Vert{}$
* `3'b100` (`ALU_SHL`)    : Output = $X \ll 1$
* `3'b101` (`ALU_SHR`)    : Output = $X \gg 1$


2. **`SRC_X[1:0]` & `SRC_Y[1:0]` (2 bits each) — Datapath Muxes**
* `2'b00` (`MUX_ACC`)  : Zero-extended 8-bit `ACC`
* `2'b01` (`MUX_OPB`)  : Zero-extended 8-bit `OPB`
* `2'b10` (`MUX_TMP0`) : 16-bit Scratch Register `TMP0`
* `2'b11` (`MUX_TMP1`) : 16-bit Scratch Register `TMP1`


3. **`MEM_CMD[2:0]` (3 bits) — Memory Access Pipeline**
* `3'b000` (`MEM_NOP`)      : Bus Idle
* `3'b001` (`MEM_RD_TOS`)   : Read SRAM at address `SP - 4 + BYTE_CNT`
* `3'b010` (`MEM_RD_NOS`)   : Read SRAM at address `SP - 8 + BYTE_CNT`
* `3'b011` (`MEM_RD_FLASH`) : Read Flash ROM at address in `TMP0` / `TMP1`
* `3'b100` (`MEM_WR_NOS`)   : Write `ALU_OUT[7:0]` to SRAM at address `SP - 8 + BYTE_CNT`


4. **`REG_LD[2:0]` (3 bits) — Register Latch Enable**
* `3'b000` (`LD_NONE`)    : No register update
* `3'b001` (`LD_ACC`)     : Latch `mem_rdata` into `ACC`
* `3'b010` (`LD_OPB`)     : Latch `mem_rdata` into `OPB`
* `3'b011` (`LD_TMP0_LO`) : Latch `ALU_OUT[7:0]` or `mem_rdata` into `TMP0[7:0]`
* `3'b100` (`LD_TMP0_HI`) : Latch `ALU_OUT[15:8]` or `mem_rdata` into `TMP0[15:8]`
* `3'b101` (`LD_TMP1_LO`) : Latch `ALU_OUT[7:0]` or `mem_rdata` into `TMP1[7:0]`
* `3'b110` (`LD_TMP1_HI`) : Latch `ALU_OUT[15:8]` or `mem_rdata` into `TMP1[15:8]`


5. **`SEQ_CTRL[1:0]` (2 bits) — Micro-Sequencer Control**
* `2'b00` (`NEXT`) : Advance `U_PC <= U_PC + 1`
* `2'b01` (`LOOP`) : Decrement `BYTE_CNT`; if non-zero jump back, else `U_PC <= U_PC + 1`
* `2'b10` (`DONE`) : Assert `done_p` completion pulse; reset `U_PC <= 0`



---

### CPLD Datapath & Bus Interconnect Architecture

```text
                             DATAPATH CONTROL BUS
  +-------------------------------------------------------------------------+
  |  u_alu_op  |  u_src_x  |  u_src_y  |  u_mem_cmd  |  u_reg_ld  | u_seq   |
  +-----+-----------+-----------+-----------+-------------+------------+----+
        |           |           |           |             |            |
        |           v           v           |             |            |
        |     +-----------------------+     |             |            |
        |     |   Operand Mux X / Y   |     |             |            |
        |     +-----------+-----------+     |             |            |
        |                 |                 |             |            |
        v                 v 16-bit          |             |            |
  +-----------------------------------+     |             |            |
  |     16-Bit Shared ALU Core        |     |             |            |
  |  (zx50_fpu_alu_core primitive)    |     |             |            |
  +-----------------+-----------------+     |             |            |
                    |                       |             |            |
                    v 16-bit                |             |            |
  +-----------------------------------+     |             |            |
  |       DATAPATH RESULT BUS         |     |             |            |
  +----+------------+------------+----+     |             |            |
       |            |            |          |             |            |
       v            v            v          v             v            v
  +---------+  +---------+  +---------+  +---------+  +-----------+  +-------+
  |   ACC   |  |   OPB   |  |  TMP0   |  |  TMP1   |  | MEM CTRL  |  | U_PC  |
  | (8-bit) |  | (8-bit) |  |(16-bit) |  |(16-bit) |  |(zx50_fpu  |  | (5-bit|
  | Reg File|  | Reg File|  | Scratch |  | Scratch |  |   _mem)   |  | Seq)  |
  +---------+  +---------+  +---------+  +---------+  +-----------+  +-------+

```

---

### Microcode Routine Map (`U_PC` Step Routines)

#### 1. Addition / Subtraction Loop (`OP_ADD` / `OP_SUB`) — `U_PC = 0x00`

* `0x00`: Read SRAM TOS byte `BYTE_CNT` $\rightarrow$ Latch `ACC`
* `0x01`: Read SRAM NOS byte `BYTE_CNT` $\rightarrow$ Latch `OPB`
* `0x02`: Compute `ALU_ADD` / `ALU_SUB` ($OPB \pm ACC \pm \text{carry}$) $\rightarrow$ Write Result to SRAM NOS byte `BYTE_CNT`
* `0x03`: `SEQ_CTRL = LOOP` (If `BYTE_CNT` $< 3$, branch to `0x00`, else advance to `0x04`)
* `0x04`: Lock `status_flags` $\rightarrow$ `SEQ_CTRL = DONE`

#### 2. Quarter-Square Multiplication (`OP_MUL`) — `U_PC = 0x08`

* `0x08`: Fetch TOS LSB $\rightarrow$ `ACC`; Fetch NOS LSB $\rightarrow$ `OPB`
* `0x09`: `ALU_ADD(ACC, OPB)` $\rightarrow$ `TMP0` ($a+b$); `ALU_ABS_D(ACC, OPB)` $\rightarrow$ `TMP1` ($\Vert{}a-b\Vert{}$)
* `0x0A`: Query `FLASH_QS_TABLE` LSB at `TMP0` $\rightarrow$ `TMP0_LO`
* `0x0B`: Query `FLASH_QS_TABLE` MSB at `TMP0` $\rightarrow$ `TMP0_HI` ($f(a+b)$ complete in `TMP0`)
* `0x0C`: Query `FLASH_QS_TABLE` LSB at `TMP1` $\rightarrow$ `TMP1_LO`
* `0x0D`: Query `FLASH_QS_TABLE` MSB at `TMP1` $\rightarrow$ `TMP1_HI` ($f(\Vert{}a-b\Vert{})$ complete in `TMP1`)
* `0x0E`: `ALU_SUB(TMP0, TMP1)` $\rightarrow$ Store Product in `TMP0`
* `0x0F`: Write `TMP0_LO` to SRAM NOS byte 0; Write `TMP0_HI` to SRAM NOS byte 1
* `0x10`: Zero-pad bytes 2 & 3 in SRAM NOS (for 32-bit frame) $\rightarrow$ `SEQ_CTRL = DONE`

#### 3. Division (`OP_DIV`) — `U_PC = 0x12`

* `0x12`: Fetch NOS byte 3 $\rightarrow$ Query `FLASH_RECIP_TABLE` $\rightarrow$ Latch 16-bit reciprocal into `TMP1`
* `0x13`: Call `MUL` microcode pass on TOS and `TMP1`
* `0x14`: Store 32-bit quotient back to SRAM NOS frame $\rightarrow$ `SEQ_CTRL = DONE`

#### 4. Square Root (`OP_SQRT`) — `U_PC = 0x16`

* `0x16`: Fetch TOS MSB $\rightarrow$ Query `FLASH_SQRT_TABLE` $\rightarrow$ Latch initial seed $y_0$ into `TMP0`
* `0x17`: Execute Newton-Raphson micro-step: $y_1 = y_0 \cdot (3 - X \cdot y_0^2) \gg 1$
* `0x18`: Store 32-bit result to SRAM NOS frame $\rightarrow$ `SEQ_CTRL = DONE`

#### 5. Base-2 Logarithm (`OP_LOG2` / `OP_LN`) — `U_PC = 0x1A`

* `0x1A`: Fetch TOS mantissa byte $\rightarrow$ Query `FLASH_LOG2_TABLE` $\rightarrow$ Latch into `TMP0`
* `0x1B`: If `OP_LN`: Multiply `TMP0` by constant $\ln(2)$ (`16'h00B1`) via `MUL` pass
* `0x1C`: Store 32-bit log result to SRAM NOS frame $\rightarrow$ `SEQ_CTRL = DONE`

#### 6. Exponentiation (`OP_EXP`) — `U_PC = 0x1E`

* `0x1E`: Multiply input $X$ by $\log_2(e)$ constant (`16'h0171`) $\rightarrow$ Split into Integer $I$ and Fractional $F$
* `0x1F`: Query `FLASH_EXP2_TABLE` at address $F$ $\rightarrow$ Latch into `TMP0`
* `0x20`: Shift `TMP0` left by $I$ bits using `ALU_SHL` loop
* `0x21`: Store 32-bit exponent result to SRAM NOS frame $\rightarrow$ `SEQ_CTRL = DONE`

#### 7. General Power Function (`OP_POW`: $x^y$) — `U_PC = 0x22`

* `0x22`: Execute `LOG2(x)` pass $\rightarrow$ Store result in `TMP0`
* `0x23`: Execute `MUL(y, TMP0)` pass $\rightarrow$ Store product $P = y \cdot \log_2(x)$ in `TMP1`
* `0x24`: Execute `EXP2(P)` pass $\rightarrow$ Store final result $2^P$ to SRAM NOS frame $\rightarrow$ `SEQ_CTRL = DONE`

---

### Implementation File Action Plan

When we build this tomorrow:

1. **`tools/build_rom.py`**: Update to output all 4 lookup tables (`QS`, `RECIP`, `SQRT_SEED`, `EXP2`/`LOG2`) into `sim/fpu_rom.hex` and generate `src/fpu_rom_map.vh`.
2. **`src/fpu_microcode.vh`**: Define micro-instruction control bitmasks and `U_PC` entry point lookup constants.
3. **`src/zx50_fpu_microengine.v`**: Instantiate the 16-bit ALU primitive (`zx50_fpu_alu_core.v`), build the register file (`ACC`, `OPB`, `TMP0`, `TMP1`), and implement the micro-sequencer state machine.
4. **`sim/fpu_microengine_tb.v`**: Run the testbench suite verifying `ADD`, `SUB`, `MUL`, `DIV`, `SQRT`, `EXP`, and `POW` against simulated 12ns SRAM and 55ns Flash.