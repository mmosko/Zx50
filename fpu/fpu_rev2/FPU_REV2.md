# Zx50 CPU Rev C4 Math & Stack Coprocessor Specification

This document details the architectural hardware specification, instruction set architecture (ISA), and microcoded
execution engine for the Latice MachXO2 Coprocessor FPGA integrated on the Zx50 CPU Card (Rev C4).

See the ProgrammersGuide.md for details of using the FPU form Z80 assembly code.

---

## 1. System Overview & Hardware Architecture

This section gives a brief overview of the system without delving into the minute details.

- CPU: Zilog Z80C 10 MHz
- Bus: Backplane with AC termination
- Coprocessor:
    - Lattice MachXO2-2000 (speed grade 4) direclty on the Z80 CPU bus via level shifters.
    - Private SRAM
    - Private FLASH (IS25LP080D, Serial NOR Flash (Quad SPI) 3.3V 8M-bit 1M x 8 8ns)
- Stack:
    - Organized in 4-byte words, but may hold 8-byte data (e.g. i64, F64).

### Notation

- SP: Stack pointer (the memory address of the next write)
- TOS: Top of Statck (the top word on the stack)
- NOS: Next on Stack (the word just under the TOS)

### Flash organization

The FPGA program is stored on internal flash. The external flash is used for lookup tables, FPU microcode, and
optional Z80 firmware.

As we have a 1MB flash, we can organize each section in, say, 64KB blocks, for 12 blocks. The specific code used is
determined by the DBG_N line and the DBG[0:2] values on boot.

If DBG3 is LOW on boot (using internal pull up),
the FPGA will enable Z80 memory, otherwise, it only exposes the FPU operation. DBG3 only needs to be low during
power on (or reset), not all the time.

- Normal FPU microcode
- Debug FPU Microcode
- Normal Z80 firmware
- Debug Z80 firmware

### General operation

- The flash contains the FPU programming in one section and the Z80 firmware in another section.
- There is a jumper for `DBG_EN`. If this is sat, the FPGA copies one set of firmware and program to the SRAM,
  otherwise, it uses the production version.
- If DBG3 is low on boot, the FPGA will copy a 64KB block of flash to the SRAM.
- The FPGA will copy all FPU microcode and lookup tables to the internal FPGA RAM.

### Operating principle

The FPU works on a stack. Unary operations read and write back the TOS. Binary operations consume the TOS and
NOS, and write back the result to the new TOS.

The stack may hold 4-byte or 8-byte numbers. The stack itself does not know what it holds, it is implied by
the command given to operate on the stack (e.g. 8-byte add or 4-byte multiplication, etc.). It is up to
the user to correctly track the format of numbers on the stack and use the correct command.

- Port 0x70 is the stack register. A write is a push and a read is a pop.
- Port 0x71 is the command register.
    - A write executes a management command or a stack operation.
    - A read pulls in the status register.
- The FPU can operate in blocking or non-blocking mode (set by mgmt command)
    - Blocking mode (the default): Raises the ~WAIT signal to block the Z80 until done. The user reads the status
      register to get the operation status, then reads the stack register as needed. On the FPGA, some operations
      will complete in one or two MCLK cycles, so do not assert ~WAIT.
    - Non-blocking: The user reads the status register until it is not BUSY.

While the FPGA has dual ported memory, that does not mean that the Z80 should read/write the stack at any time.
Initially, stack operations are only allowed when the status register BUSY is false.

### Overview of FPU services

Data Types:

- i32 (signed 32-bit)
- i64 (signed 64-bit)
- F32 (IEEE 32-bit float)
- F64 (IEEE 64-bit float)

Management commands:

- Reset FPU.
- Set BLOCKING mode or NONBLOCKING mode.

Arithmetic Opcodes:

- binary: add, subract, multiply, divide, sqrt, pow, exp, ln,
- unary: change sign, absolute value, floor, ceil
- unary (trig): sin, cos, tan

Stack Opcodes:

- Duplicate TOS (4 or 8 bytes)
- Format conversions
- Store and Load TOS (uses internal memory for user storage, separte from ALU scratch memory)
- Clear stack.

The Store and Load commands move data between the stack and a small internal memory. It allows moving 4-byte and 8-byte
words on and off the stack in a single Z80 IO operation (TODO: work out full set of COMMAND values to make sure
this is a true statement).

## Hardware Specifcations

- FPGA
- SRAM
- Flash
- Internal RAM and flash
- level shifters and signal delays
- Z80 Clock (5 MHz or 10 MHz)
- Shadow bus MCLK (20 MHz or 40 MHz): leads the Z80 clock by half a MCLK cycle

### Clocking Overview

There are two external clocks: ZCLK is a 5 or 10 MHz Z80 clock and MCLK is a 20 or 40 MHz shadow bus clock. ZCLK
is synchronous with MCLK and always a half MCLK cycle behind it.

The FPU will use a x4 PLL multiplier on MCLK for the internal FPU operations, i.e. a 80 MHz or 160 Mhz internal
clock.

---

## 2. Bus Signal Mapping

---

## 3. Register & I/O Interface Protocol

The CPLD decodes host I/O port base address `0x70` and `0x71`.

| Port Address | Operation | Register Name | Description                                                                                                |
|--------------|-----------|---------------|------------------------------------------------------------------------------------------------------------|
| **`0x70`**   | Write     | `DATA_PUSH`   | Pushes 1 byte to Top of Stack ($TOS$) in private SRAM, auto-incrementing byte pointer ($SP$).              |
| **`0x70`**   | Read      | `DATA_POP`    | Reads 1 byte from Top of Stack ($TOS$) in private SRAM, auto-decrementing byte pointer ($SP$).             |
| **`0x71`**   | Write     | `CMD_EXEC`    | Latches opcode to execution dispatcher (`zx50_fpu_dispatch`), pulls `~WAIT` low, and executes computation. |
| **`0x71`**   | Read      | `STATUS`      | Returns status flags: `[BUSY, ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW, ERR, 0]`.                            |

### Status Register Bit Flags (`0x71` Read)

| Bit 7  | Bit 6  | Bit 5  | Bit 4   | Bit 3      | Bit 2       | Bit 1 | Bit 0        |
|--------|--------|--------|---------|------------|-------------|-------|--------------|
| `BUSY` | `ZERO` | `SIGN` | `CARRY` | `OVERFLOW` | `UNDERFLOW` | `ERR` | Reserved (0) |

* **`BUSY` (Bit 7):** Set high during command execution; cleared automatically when the execution engine completes
  execution.


* **`ERR` (Bit 1):** Set high if an illegal opcode, divide-by-zero, or execution fault is encountered.

---

## 4. Stack Memory Architecture

## OpCodes (port 0x71)

There are ALU, Stack, and Management opcode spaces. These are the commands sent to the command port (0x71).
We structured the commands to use only 1 byte, so all operations are a single Z80 OUT.

### ALU Opcodes

ALU opcodes have a prefix (operation) and suffix (data format)

TODO: is 0b101 needed? One could simply do a format conversion on the f32 to an f64 then, e.g., multiply.

| Bits  | Format     | Notes                      |
|-------|------------|----------------------------|
| 0b000 | i32        | i32 operands to i32 result |
| 0b001 | f32        | f32 operands to f32 result |
| 0b010 | i64        | i64 operands to i64 result |
| 0b011 | f64        | f64 operands to f64 result |
| 0b100 | f32 to f64 | f32 operands to f64 result |
| 0b101 | reserved   |                            |
| 0b110 | reserved   |                            |
| 0b111 | reserved   |                            |

`fff` is the data format bits

| Bits        | Operation       |
|-------------|-----------------|
| 0b0000_0fff | ADD             |
| 0b0000_1fff | SUB             |
| 0b0001_0fff | MUL             |
| 0b0001_1fff | DIV             |
| 0b0010_0fff | SQRT            |
| 0b0010_1fff | POW             |
| 0b0011_0fff | LN              |
| 0b0011_1fff | EXP             |
| 0b0100_0fff | reserved binary |
| 0b0100_1fff | reserved binary |
| 0b0101_0fff | CHS             |
| 0b0101_1fff | ABS             |
| 0b0110_0fff | FLOOR           |
| 0b0110_1fff | CEIL            |
| 0b0111_0fff | SIN             |
| 0b0111_1fff | COS             |
| 0b1000_0fff | TAN             |
| 0b10xx_xfff | RESERVED        |

So there are 15 x 4 (format) = 60 ALU opcodes (or 15 x 8 = 120 at most)

### Stack Opcodes

There are 16 words (64 bytes) of user memory set aside in the FPGA internal ram for storage. If the user
is operating on 8-byte words, they must perform two copy (CP) commands.

| Bits        | nmonic         | Operation                          |
|-------------|----------------|------------------------------------|
| 0b1100_0000 | DUP4           | Duplicate top 4 bytes of stack     |
| 0b1100_0001 | DUP8           | Duplicate top 8 bytes of stack     |
| 0b1100_0110 | Clear stack    | sets SP to empty location          |
| 0b1100_0111 | reserved       |                                    |
|             |                |                                    |
| 0b1100_1000 | i32 to i64     | Pad and sign-extend TOS to 8 bytes |
| 0b1100_1001 | f32 to f64     | Pad and sign-extend TOS to 8 bytes |
| 0b1100_1010 | i64 to i32     | Sign-preserving truncation         |
| 0b1100_1011 | f64 to f32     | Closest approximation              |
| 0b1100_11xx | Reserved       |                                    |
|             |                |                                    |
| 0b1101_xxxx | CP [xxxx], TOS | Copy TOS to user word `xxxx`       |
| 0b1110_xxxx | CP TOS, [xxxx] | Copy user word `xxxx` to TOS       |
| 0b1111_0000 | Zero memory    | Zero all user memory               |
| 0b1111_0xxx | reserved       |                                    |

### Management Opcodes

| Bits        | nmonic      | Operation                 |
|-------------|-------------|---------------------------|
| 0b1111_1111 | RESET       | Resets the FPU            |
| 0b1111_1110 | BLOCKING    | Sets to blocking mode     |
| 0b1111_1101 | NONBLOCKING | Sets to non-blocking mode |
| 0b1111_1100 | reserved    |                           |
| 0b1111_10xx | reserved    |                           |

---

## 5. Microcoded Execution

Internally, the FPU uses microcode to process some operations, rather than have fully implements logic for
every operation.  There are a set of internal registers used by the microcode processor (upc).


### Hardware ALU blocks

- 32-bit adder
- 32-bit multiplier
- shifter
- 

### Microcode Machine Model

### Microcode Instruction Set Architecture


## 7. Simulation & Verilog Architecture Setup

### 7.1 Environment Overview & Module Hierarchy

The simulation environment uses a modular architecture where the CPLD core (`zx50_fpu.v`) delegates execution logic to
the microcode engine while handling top-level bus interfacing.

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

* **`src/zx50_fpu.v`:** Top-level CPLD logic. Manages Z80 I/O port decoding (`0x70`/`0x71`), stack pointer counter
  ($SP$), consolidated memory strobes (`c_oe_n`, `c_we_n`), chip enables (`m_ce_n`, `f_ce_n`), open-drain `wait_n`/
  `int_n` drivers, and CDC request synchronizers.


* **`src/zx50_fpu_mem.v`:** Private memory bus arbiter & strobe generator. Maps 15-bit private addresses (`CA0`–`CA14`),
  manages `clk_spd` wait states, and generates 1-cycle `mem_ready` completion pulses.


* **`src/zx50_fpu_dispatch.v`:** Command dispatcher submodule running on `MCLK`. Decodes opcodes, controls execution
  state timing, manages level CDC acknowledgment, and outputs arithmetic status flags.


* **`src/zx50_fpu_microengine.v`:** Unified Microcoded Execution Engine. Manages the shared scratchpad register file,
  drives the microcode step pointer (`U_PC`), and sequences data transfers between memory and the ALU core.
* **`src/zx50_fpu_alu_core.v`:** Single Shared 16-Bit Arithmetic Primitive. Performs addition, subtraction, absolute
  difference, and bit shifts for all microcode routines.
* **`src/zx50_fpu_block.v`:** Subsystem cluster wrapper. Integrates CPLD (`U11`), SRAM (`U12`), and Flash (`U13`) on
  private `CA[14:0]` and `CD[7:0]` buses.


* **`src/is61c256al_12.v`:** ISSI `IS61C256AL-12TLI` 12 ns SRAM simulation model.


* **`src/sst39sf040.v`:** SST39SF040 55 ns Flash ROM simulation model. Features explicit sensitivity lists and
  `$readmemh` pre-loading for math LUTs.


* **`src/fpu_rom_map.vh`:** Auto-generated Verilog header file containing Flash ROM base addresses and lookup table
  defines.
* **`src/fpu_microcode.vh`:** Micro-instruction word encodings, control bit masks, and `U_PC` entry point defines.

#### Testbench Suite (`./sim/`)

All testbenches follow pattern-based execution via `make run-<test>` (e.g., `make run-init`):

* **`sim/init_tb.v` (`make run-init`):** Verifies boot reset state, register defaults, private memory chip select
  isolation (`m_ce_n`, `f_ce_n`), and open-drain High-Z line releases.


* **`sim/fpu_stack_tb.v` (`make run-fpu_stack`):** Verifies Port `0x70` single-byte, multi-byte 32-bit frame, and
  interleaved PUSH/POP stack operations, $SP$ tracking, and single-cycle 12ns SRAM write timing.


* **`sim/fpu_cmd_tb.v` (`make run-fpu_cmd`):** Verifies Port `0x71` command execution, `ZCLK`/`MCLK` 4-phase CDC
  handshaking, automatic Z80 `wait_n` stall and release, and valid/invalid opcode status reporting (`BUSY`, `ERR`).


* **`sim/fpu_mem_tb.v` (`make run-fpu_mem`):** Verifies 20 MHz vs 40 MHz Flash ROM timing, SRAM single-cycle reads,
  2-phase SRAM write hold timing, and dual-client arbitration.


* **`sim/fpu_microengine_tb.v` (`make run-fpu_microengine`):** Verifies microcode execution routines for addition
  (`OP_ADD`), subtraction (`OP_SUB`), negation (`OP_CHS`), and Quarter-Square multiplication (`OP_MUL`).

~~~
~~~

# Master Opcode & Flash LUT Inventory

