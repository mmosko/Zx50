# Zx50 CPU Rev C2 Math & Stack Coprocessor Specification



This document details the architectural hardware specification and instruction set architecture (ISA) for the ATF1508AS CPLD Coprocessor Cluster integrated on the Zx50 CPU Card (Rev C2). The Verilog codebase is written in standard Verilog for direct synthesis compatibility with old toolchains (Microchip/Atmel ProChip Designer, WinCUPL, Quartus II 13.0sp1) without SystemVerilog dependencies.

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


* **Private SRAM (`U12`):** ISSI `IS61C256AL-12TLI` (12 ns access time, 28-pin TSOP-I). Address lines `CA0`–`CA14` provide a full **32 KB active private memory space**. Serves as hardware stack storage, scratchpad, and microcode buffer.


* **Private Flash (`U13`):** SST39SF040 (55 ns, PLCC-32). Address lines `CA0`–`CA14` (32 KB active); `A15`–`A18` tied to `GND`. Stores Quarter-Square multiplication tables, log/antilog tables, and trigonometric seed constants.


* **Consolidated Control Lines:** Memory read enable (`~C_OE`, Pin 45) and write enable (`~C_WE`, Pin 46) are consolidated into a shared pair of control strobes across both private memory ICs. Device targeting is gated by dedicated Chip Enable lines (`~M_CE` on Pin 44 for SRAM; `~F_CE` on Pin 68 for Flash), saving 2 macrocells and 2 package I/O pins on the CPLD.


* **High-Speed Single-Cycle Memory Access Timing:**
* At 40 MHz ($T_{\text{clk}} = 25\text{ ns}$), the **12 ns SRAM access time** ($t_{\text{AA}}$) provides **13 ns of timing margin** per clock cycle.


* Eliminates multi-cycle wait states and complex hold pipelines. Reads and writes execute as clean single-cycle transfers synchronized to `posedge mclk`.




* **Dual Clock Architecture & Asynchronous CDC Handshaking:**
* **`ZCLK` Domain (5/10 MHz):** Synchronously decodes Z80 I/O read/write cycles, updates the 8-bit Stack Pointer ($SP$), and drives host handshake lines (`wait_n`, `int_n`).


* **`MCLK` Domain (20/40 MHz):** Drives high-speed command execution, private SRAM/Flash pipeline timing, and math calculations.


* **4-Phase Level CDC Handshake:** Inter-domain requests (`exec_req` from `ZCLK` $\rightarrow$ `MCLK`) and acknowledgments (`done_ack` from `MCLK` $\rightarrow$ `ZCLK`) use level-driven handshaking with 2-stage synchronizers (`req_sync`, `ack_sync`). This guarantees zero pulse-dropping when crossing between asynchronous 5–10 MHz and 20–40 MHz clock domains.





---

## 2. Bus Signal Mapping

### Z80 Host Interface (`U11` CPLD)

| Signal Group | Signal Names | CPLD Pin Assignments | Description |
| --- | --- | --- | --- |
| **Z80 Address** | `A0`–`A15` | Pins 21, 20, 18, 17, 16, 15, 12, 11, 10, 9, 8, 6, 5, 4, 79, 80 | Buffered Z80 host address bus |
| **Z80 Data** | `D0`–`D7` | Pins 30, 31, 28, 24, 22, 25, 27, 29 | Bidirectional Z80 host data bus |
| **Z80 Control** | `~RD`, `~WR`, `~IORQ`, `~MREQ`, `~M1` | Pins 77, 76, 74, 75, 73 | Bus cycle and transfer control inputs |
| **Handshake / Status** | `~WAIT`, `~INT`, `~RESET`, `~BUSACK` | Pins 70, 69, 1, 84 (tied to GND) | Open-drain `~WAIT`/`~INT` lines, reset, and isolation signals |
| **Clocks** | `MCLK`, `CLK` (`ZCLK`) | Pins 83 (`GCLK1`), 2 (`GCLK2`) | High-speed coprocessor clock and host CPU clock |

### Private Memory Bus Interface & Config Pins (Rev C2 Netlist)

| Signal Group | Signal Names | CPLD Pin Assignments | Destination / Description |
| --- | --- | --- | --- |
| **Private Address** | `CA0`–`CA14` | Pins 56, 54, 55, 52, 51, 50, 49, 48, 61, 63, 65, 64, 57, 58, 60 | `U12` SRAM & `U13` Flash (`A0`–`A14`) |
| **Private Data** | `CD0`–`CD7` | Pins 37, 36, 35, 34, 33, 41, 40, 39 | Bidirectional private memory data bus |
| **Shared Control** | `~C_OE`, `~C_WE` | Pins 45, 46 | Consolidated Output Enable and Write Enable strobes |
| **Chip Enables** | `~M_CE`, `~F_CE` | Pins 44, 68 | Dedicated Chip Enable for SRAM (`U12`) & Flash (`U13`) |
| **Speed Select** | `CLK_SPD` | Pin 81 | Hardware Memory Pipeline Speed Selector (Jumper `J8`) |

---

## 3. Register & I/O Interface Protocol

The CPLD decodes host I/O port base address `0x70` and `0x71`.

| Port Address | Operation | Register Name | Description |
| --- | --- | --- | --- |
| **`0x70`** | Write | `DATA_PUSH` | Pushes 1 byte to Top of Stack ($TOS$) in private SRAM, auto-incrementing byte pointer ($SP$). |
| **`0x70`** | Read | `DATA_POP` | Reads 1 byte from Top of Stack ($TOS$) in private SRAM, auto-decrementing byte pointer ($SP$). |
| **`0x71`** | Write | `CMD_EXEC` | Latches opcode to execution dispatcher (`zx50_fpu_dispatch`), pulls `~WAIT` low, and executes computation. |
| **`0x71`** | Read | `STATUS` | Returns status flags: `[BUSY, ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW, ERR, 0]`. |

### Status Register Bit Flags (`0x71` Read)

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BUSY` | `ZERO` | `SIGN` | `CARRY` | `OVERFLOW` | `UNDERFLOW` | `ERR` | Reserved (0) |

* **`BUSY` (Bit 7):** Set high during command execution; cleared automatically when `zx50_fpu_dispatch` completes execution.


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

## 5. Instruction Set Architecture & Opcode Matrix

Opcodes written to port `0x71` are split into two 4-bit fields:

	Format Field = Opcode[7:4]
	Operation Field = Opcode[3:0]

### Format Field (`opcode[7:4]`)

| Value | Identifier | Data Type | Size / Operand | Hardware Acceleration Level |
| --- | --- | --- | --- | --- |
| `0x0` | `i16` | 16-Bit Signed Integer | 2 Bytes | Native CPLD Hardware (1 Tick Add/Sub) |
| `0x1` | `i32` | 32-Bit Signed Integer | 4 Bytes | Native CPLD Hardware (Byte-Serial 12ns SRAM) |
| `0x2` | `i64` | 64-Bit Signed Integer | 8 Bytes | Microcoded / Software Pass-through |
| `0x3` | `float` / `fx1616` | 32-Bit IEEE-754 / 16.16 Fixed | 4 Bytes | Native CPLD Hardware (16.16 Fixed) / Fast LUT |
| `0x4` | `dfloat` | 64-Bit IEEE-754 Float | 8 Bytes | Microcoded (Private SRAM) |
| `0x5` | `cfloat` | 32-Bit Complex Float ($a + bi$) | 8 Bytes | Dual-Pass Native 32-bit Core |
| `0xE` | `special` | Custom Extensions | Custom | CPLD Table Acceleration |
| `0xF` | `mgmt` | Hardware / Stack Management | 0 Bytes | Native CPLD Control Logic |

### Management Opcodes (`Format = 0xF`)

| Full Opcode | Mnemonic | Description | Latency |
| --- | --- | --- | --- |
| **`0xF0`** | `CLR_STK` | Resets Stack Pointer to `0x0000` | $25\text{ ns}$<br> |
| **`0xF1`** | `POP_TOS` | Drops $TOS$ (decrements $SP$ by active stride) | $25\text{ ns}$<br> |
| **`0xF2`** | `DUP_TOS` | Duplicates $TOS$ entry on stack in SRAM | $100\text{ ns}$<br> |
| **`0xFF`** | `RESET` | Soft resets execution state machine & flags | $25\text{ ns}$<br> |

---

## 6. Execution & CDC Handshake FSM

```text
       ZCLK Domain (Z80 Host Interface)                 MCLK Domain (Command Dispatcher)
  +---------------------------------------+        +---------------------------------------+
  |               ST_IDLE                 |        |               ST_IDLE                 |
  |  Host writes Opcode to Port 0x71      |        |  Waiting for exec_req_mclk == 1       |
  +-------------------+-------------------+        +-------------------+-------------------+
                      |                                                |
            Latch Opcode, Set BUSY=1                                   |
            Assert wait_n=0, Raise exec_req=1                          |
                      |                                                |
                      +=================== Level CDC ==================>
                      |                                                v
                      |                            +---------------------------------------+
                      |                            |              ST_DECODE                |
                      |                            |  Decode opcode, check validity        |
                      |                            +-------------------+-------------------+
                      |                                                |
                      |                                    Valid Opcode| Invalid Opcode
                      |                                                v                |
                      |                            +-------------------+----+           |
                      |                            |              ST_EXEC   |           |
                      |                            |  Execute Math / LUT    |           |
                      |                            +-------------------+----+           |
                      |                                                |                |
                      |                                                +<---------------+
                      |                                                v
                      |                            +---------------------------------------+
                      |                            |              ST_FINISH                |
                      |                            |  Set err_flag, Raise done_ack=1       |
                      |                            +-------------------+-------------------+
                      |                                                |
                      <=================== Level CDC ==================+
                      v
  +---------------------------------------+
  |         ST_HANDSHAKE_COMPLETE         |
  |  Clear BUSY=0, Set ERR, Release wait_n|
  |  Deassert exec_req=0                  |
  +-------------------+-------------------+
                      |
                      +=================== Level CDC ==================>
                                                                       v
                                                   +---------------------------------------+
                                                   |            ST_RELEASE_ACK             |
                                                   |  Deassert done_ack=0, Return IDLE     |
                                                   +---------------------------------------+

```

---

# Simulation & Verilog Architecture Setup

## 1. Environment Overview & Module Hierarchy

The simulation environment uses a modular architecture where the CPLD core (`zx50_fpu.v`) delegates execution logic to submodules while handling top-level bus interfacing.

```text
tb_zx50 (Testbench Top)
 ├── zx50_clock           (Clock Mezzanine BFM: Glitch-free MCLK / ZCLK generation)
 ├── zx50_backplane       (Passive Backplane: Weak pull-ups for Z80 & Shadow Bus)
 └── zx50_fpu_block       (FPU Subsystem Cluster Wrapper)
      ├── zx50_fpu        (U11 - ATF1508AS CPLD Top Level Logic)
      │    └── zx50_fpu_dispatch (Command Execution Dispatcher Submodule)
      ├── is61c256al      (U12 - 32KB Active Private SRAM Model)
      └── sst39sf040      (U13 - 32KB Active Private Flash ROM Model)

```

---

## 2. Source & Testbench File Index

### Synthesis Source Files (`./src/`)

* **`src/zx50_fpu.v`:** Top-level CPLD logic. Manages Z80 I/O port decoding (`0x70`/`0x71`), stack pointer counter ($SP$), consolidated memory strobes (`~C_OE`, `~C_WE`), chip enables (`~M_CE`, `~F_CE`), open-drain `wait_n`/`int_n` drivers, and CDC request synchronizers.


* **`src/zx50_fpu_mem.v`:** Private memory bus arbiter & strobe generator. Maps 15-bit private addresses (`CA0`–`CA14`) and handles single-cycle read/write strobe timing.


* **`src/zx50_fpu_dispatch.v`:** Command dispatcher submodule running on `MCLK`. Decodes opcodes, controls execution state timing, manages level CDC acknowledgment, and outputs arithmetic status flags.


* **`src/zx50_fpu_block.v`:** Subsystem cluster wrapper. Integrates CPLD (`U11`), SRAM (`U12`), and Flash (`U13`) on private `CA[14:0]` and `CD[7:0]` buses.


* **`src/is61c256al.v`:** ISSI `IS61C256AL-12TLI` 12 ns SRAM simulation model.


* **`src/sst39sf040.v`:** SST39SF040 55 ns Flash ROM simulation model. Features explicit sensitivity lists and `$readmemh` pre-loading for math LUTs.


* **`src/zx50_clock.v`:** Glitch-free dual clock generator (`MCLK` / `ZCLK`).


* **`src/zx50_backplane.v`:** Backplane pull-up primitives.


* **`src/z80_cpu_util.v`:** T-State accurate Z80 Bus Functional Model.



### Testbench Suite (`./sim/`)

All testbenches follow pattern-based execution via `make run-<test>` (e.g., `make run-init`):

* **`sim/init_tb.v` (`make run-init`):** Verifies boot reset state, register defaults, private memory chip select isolation (`~M_CE`, `~F_CE`), and open-drain High-Z line releases.


* **`sim/fpu_stack_tb.v` (`make run-fpu_stack`):** Verifies Port `0x70` single-byte, multi-byte 32-bit frame, and interleaved PUSH/POP stack operations, $SP$ tracking, and single-cycle 12ns SRAM write timing.


* **`sim/fpu_cmd_tb.v` (`make run-fpu_cmd`):** Verifies Port `0x71` command execution, `ZCLK`/`MCLK` 4-phase CDC handshaking, automatic Z80 `wait_n` stall and release, and valid/invalid opcode status reporting (`BUSY`, `ERR`).