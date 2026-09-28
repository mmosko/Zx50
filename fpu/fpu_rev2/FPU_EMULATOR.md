# Zx50 FPU Rev 2: Bit-Accurate Python Machine Model Specification

## 1. Executive Summary & Objectives

The purpose of the **Zx50 FPU Python Machine Model** is to provide an exact, cycle- and bit-accurate software reference of the Lattice MachXO2 FPGA hardware implementation prior to writing Verilog. It serves as:

1. **A Validation Oracle:** Generates expected bit patterns and status flag updates to verify future Verilog testbenches (`sim/`).
2. **A Microcode Prototyping Engine:** Validates that the 32-bit micro-instruction sequences specified in `SystemDesign.md` correctly execute all 60 user macro-opcodes across all four numeric formats (`i32`, `f32`, `i64`, `f64`).
3. **An Architectural Proof of Concept:** Proves that all transcendental functions (CORDIC $\sin, \cos, \tan$, Taylor $\ln, e^x$), floating-point normalizations, and multi-precision arithmetic converge accurately using only physical hardware ALU primitives.

---

## 2. Core Architectural Philosophy & Hard Emulation Constraints

To guarantee that the Python emulator faithfully reflects real digital logic and contains no "software cheat codes," the implementation strictly obeys the following rules:

### Rule 1: Byte Arrays for Registers and Memory
* **No Python `int` or `float` for register storage:** Every physical hardware register (`AL`, `AH`, `BL`, `BH`, `DL`, `DH`, `FL`, `FH`, `EA`, `EB`, `C`, `STATUS`, `SP`, `OSP`, `UPC`) is represented as a `bytearray`.
* 32-bit registers are stored as `bytearray(4)`.
* Memory (SysMEM EBR) is modeled as a flat `bytearray(2048)`.
* Byte ordering follows hardware **Little-Endian**: byte index `0` is the least significant byte (LSB), and byte index `3` is the most significant byte (MSB).

### Rule 2: Hardware-Only Arithmetic Primitives
* **No high-level mathematical libraries:** Python `math`, `numpy`, or native floating-point types (`float`) are strictly forbidden during execution.
* The emulator may only perform basic byte/bit arithmetic (`+`, `-`, `&`, `|`, `^`, `~`, `<<`, `>>`) to model individual hardware logic gates and FPGA carry chains.
* Multi-byte addition/subtraction is evaluated byte-by-byte to propagate carry bits and detect signed two's-complement overflow exactly like Lattice `CCU2C` hardware slices.

### Rule 3: Radix-4 Booth Multiplier Emulation
* Multiplication cannot use Python `*` on 32-bit or 64-bit numbers.
* Implemented as an iterative Radix-4 Booth recoder that inspects 3 bits of multiplier per cycle, performing add/subtract/shift operations on a partial product accumulator over 16 cycles (32-bit) or 32 cycles (64-bit).

### Rule 4: Table-Driven CORDIC & Transcendental Functions
* Trigonometric functions ($\sin, \cos, \tan$) must not call `math.sin` or `math.cos`.
* Evaluated exclusively through an iterative shift-and-add CORDIC rotation loop driven by an explicit ROM lookup table of fixed-point angles ($\theta_i = \text{round}(2^{31} \times \arctan(2^{-i}))$).

---

## 3. Python Package Architecture & Module Structure

The emulator will live in `fpu/fpu_rev2/model/` with a modular hierarchy that directly mirrors future Verilog hardware modules:

```text
fpu/fpu_rev2/model/
├── __init__.py
├── alu/
│   ├── __init__.py
│   ├── adder32.py         # 32-bit CCU2C carry-lookahead slice (byte-by-byte ripple carry & overflow)
│   ├── shifter32.py       # 32/64-bit logarithmic barrel shifter (LSL, LSR, ASR)
│   ├── booth_mul.py       # Radix-4 Booth multiplier step engine (16/32 cycles)
│   ├── lzc32.py           # Priority-encoder Leading Zero Count tree (returns 6-bit count in C)
│   └── exp_alu.py         # 12-bit signed exponent adder/subtractor with overflow/underflow
├── memory.py              # 2048-byte SysMEM EBR model with SP/OSP bounds and underflow trapping
├── registers.py           # RegisterFile using bytearray(4) with Little-Endian bit/byte helpers
├── cordic_lut.py          # Fixed-point atan(2^-i) angle lookup table in ROM
├── ucode_rom.py           # Microcode assembler: packs symbolic micro-ops into 32-bit binary words
├── micro_sequencer.py     # Microcode fetch/decode/execute loop (UPC increment, JNZ, JZ, DJNZ, RET)
├── dispatcher.py          # Port 0x70/0x71 host bus cycles, BSY, WAIT_N, Immediate and Batch modes
└── tests/
    ├── __init__.py
    ├── test_adder.py      # Integer addition, subtraction, carry, borrow, signed overflow
    ├── test_shifter.py    # Barrel shifter corner cases
    ├── test_booth_mul.py  # Integer multiplication (signed and unsigned)
    ├── test_stack.py      # POP/PUSH bounds, stack underflow/overflow exception trapping
    ├── test_microcode.py  # Validation of complete microcode programs from SystemDesign.md
    └── test_ieee754.py    # Validation of f32 and f64 ops against IEEE-754 test vectors
```

---

## 4. Hardware Building Block Specifications

### 4.1 Register File (`registers.py`)

All registers are encapsulated in a `RegisterFile` class:

| Register Name | Byte Representation | Description |
|---|---|---|
| `AL` | `bytearray(4)` | Accumulator Low (32-bit) / TOS |
| `AH` | `bytearray(4)` | Accumulator High (32-bit) |
| `BL` | `bytearray(4)` | Operand B Low (32-bit) / NOS |
| `BH` | `bytearray(4)` | Operand B High (32-bit) |
| `DL` | `bytearray(4)` | Dedicated Math Low (32-bit, preserved) |
| `DH` | `bytearray(4)` | Dedicated Math High (32-bit, preserved) |
| `FL` | `bytearray(4)` | Pure Volatile Scratchpad Low (32-bit) |
| `FH` | `bytearray(4)` | Pure Volatile Scratchpad High (32-bit) |
| `EA` | `bytearray(2)` | Working Exponent A (12-bit signed) |
| `EB` | `bytearray(2)` | Working Exponent B (12-bit signed) |
| `C`  | `bytearray(1)` | Loop / Shift Counter (6-bit, 0..63) |
| `STATUS` | `bytearray(1)` | Status Register (`[BSY, Z, S, C, V, U, ERR, Res]`) |
| `SP` | `bytearray(1)` | Operand Stack Pointer (6-bit word address, 0..255 bytes) |
| `OSP`| `bytearray(1)` | Operation Stack Pointer (5-bit command queue, 0..31 bytes) |
| `UPC`| `bytearray(2)` | Microcode Program Counter (10-bit address, 0..1023) |

#### Helper API:
* `get_reg(name: str) -> bytearray`: Returns 4-byte or 8-byte slice (e.g. `AX` returns `AH + AL`).
* `set_reg(name: str, val: bytearray)`: Writes bytes with strict length validation.
* `get_bit(reg: bytearray, bit_idx: int) -> int` / `set_bit(reg: bytearray, bit_idx: int, val: int)`.

---

### 4.2 SysMEM EBR Memory Model (`memory.py`)

* A single continuous `bytearray(2048)` representing SysMEM EBR:
  * `0x0000`–`0x00FF` (256 bytes): Operand Stack.
  * `0x0200`–`0x02FF` (256 bytes): Internal Scratchpad RAM (64 $\times$ 32-bit words).
  * `0x0300`–`0x033F` (64 bytes): User Storage Slots (16 $\times$ 32-bit words).
  * `0x0340`–`0x035F` (32 bytes): Command Stack / Queue.
  * `0x0400`–`0x07FF` (1024 bytes): Microcode ROM & High-Precision Constant Tables.

#### Stack Bounds Enforcement:
* **`pop(width: int) -> bytearray`:**
  * Checks if `SP < width`. If so, aborts, sets `STATUS[2]` (`UNDERFLOW = 1`) and `STATUS[1]` (`ERR = 1`), and leaves `SP` untouched.
  * Otherwise, reads `memory[SP - width : SP]`, updates `SP -= width`, and returns the bytes.
* **`push(data: bytearray)`:**
  * Checks if `SP + len(data) > 256`. If so, aborts, sets `STATUS[3]` (`OVERFLOW = 1`) and `STATUS[1]` (`ERR = 1`).
  * Otherwise, writes to `memory[SP : SP + len(data)]` and updates `SP += len(data)`.

---

### 4.3 Hardware ALU Slices (`alu/`)

#### 1. 32-Bit Carry-Lookahead Adder (`alu/adder32.py`)
* Evaluates addition or subtraction ($A \pm B \pm C_{\text{in}}$) by processing four 8-bit bytes sequentially:
  ```python
  carry = cin
  for i in range(4):
      temp = a[i] + (b[i] ^ sub_mask) + carry
      result[i] = temp & 0xFF
      carry = (temp >> 8) & 1
  ```
* **Flag Computation:**
  * `ZERO`: Set if `result == bytearray(4)`.
  * `SIGN`: Set if bit 7 of `result[3]` is 1.
  * `CARRY`: Equals final `carry` out of MSB.
  * `OVERFLOW`: Set if signs of operands match and differ from sign of result:
    $V = (A_{31} \oplus \text{Result}_{31}) \ \& \ (\overline{A_{31} \oplus B_{31}})$.

#### 2. Logarithmic Barrel Shifter (`alu/shifter32.py`)
* Implements `LSL`, `LSR`, and `ASR` across 32-bit and 64-bit byte arrays.
* Shift magnitude taken directly from counter `C[5:0]`.
* Shifts are performed using 5 cascaded 2-to-1 multiplexer stages (shifts of 16, 8, 4, 2, 1 bits).

#### 3. Radix-4 Booth Multiplier (`alu/booth_mul.py`)
* Evaluates $AX \leftarrow AL \times BL$ (32-bit) in 16 cycles or $\{DX, AX\} \leftarrow AX \times BX$ (64-bit) in 32 cycles.
* Inspects triplets of multiplier bits $\{y_{2i+1}, y_{2i}, y_{2i-1}\}$:
  * `000` or `111`: $+0$
  * `001` or `010`: $+1 \times \text{Multiplicand}$
  * `011`: $+2 \times \text{Multiplicand}$ (shifted left 1)
  * `100`: $-2 \times \text{Multiplicand}$
  * `101` or `110`: $-1 \times \text{Multiplicand}$
* Updates a partial product accumulator using only `adder32` and arithmetic shifts.

#### 4. Priority Encoder Leading Zero Count (`alu/lzc32.py`)
* Counts leading zeros in a 32-bit or 64-bit byte array using a 4-level binary tree of 4-bit priority encoders.
* Returns a 6-bit integer loaded directly into `C[5:0]`.

#### 5. Exponent Arithmetic Slice (`alu/exp_alu.py`)
* Performs 12-bit signed addition/subtraction on exponent registers `EA` and `EB`.
* Directly flags IEEE exponent overflow ($E > +1023$) and underflow ($E < -1022$).

---

### 4.4 Microcode ROM Assembler & Sequencer (`ucode_rom.py`, `micro_sequencer.py`)

1. **Micro-Instruction Packing:**
   * An assembler parses symbolic microcode lines (e.g. `ADD AL, BL`, `POP AX`, `DJNZ loop`) and encodes them into 32-bit binary words according to Section 4.1 of `SystemDesign.md`:
     `[31:26] OPCODE`, `[25] W`, `[24:22] DST`, `[21:19] SRC`, `[18:16] FLAG_COND`, `[15:0] OFFSET/IMM`.
2. **Micro-Sequencer Execution Cycle:**
   * Fetches 4-byte microcode word from `ROM[UPC]`.
   * Decodes fields and dispatches operands to the target ALU slice or memory function.
   * Updates `UPC`:
     * Normal: $UPC \leftarrow UPC + 1$.
     * `JNZ` / `JZ`: $UPC \leftarrow UPC + \text{offset}$ if condition met.
     * `DJNZ`: Decrements $C \leftarrow C - 1$; branches if $C \neq 0$.
     * `RET`: Signals Dispatcher that the subroutine has concluded.

---

### 4.5 Dispatcher & Host Bus Interface (`dispatcher.py`)

Models the Z80 Port `0x70` and Port `0x71` interface:
* **Port `0x70` Read:** Returns `STATUS[7:0]`.
* **Port `0x70` Write:** Pushes/pops 32-bit or 64-bit operands to/from TOS (Little-Endian byte stream).
* **Port `0x71` Write:**
  * Checks mode (`IMMEDIATE` vs `BATCH`).
  * If `SET_IMMEDIATE` (`0xFC`): Sets `IMMEDIATE = 1`.
  * If `SET_BATCH` (`0xFB`): Sets `IMMEDIATE = 0`.
  * If in Batch Mode: Queues opcode into Command Stack `0x0340` (`OSP += 1`).
  * If in Immediate Mode (or on `EXEC_BATCH` `0xFA`): Asserts `BUSY <= 1`, looks up microcode entry address from jump table, sets `UPC`, and executes until `RET`.
  * Holds `BUSY <= 1` continuously across the entire batch sequence.
  * Releases `BUSY <= 0` upon subroutine completion.

---

## 5. Verification & Test Plan

1. **Unit Testing ALU Primitives:**
   * Run exhaustive 16-bit tests and targeted 32-bit edge cases on `adder32` (detect carry, borrow, overflow).
   * Verify Radix-4 Booth multiplier against signed integer multiplication vectors.
2. **Stack Underflow / Overflow Trapping:**
   * Attempt popping from empty stack $\to$ verify `UNDERFLOW = 1`, `ERR = 1`, $SP$ unmodified.
   * Attempt pushing 65th word $\to$ verify `OVERFLOW = 1`, `ERR = 1`, memory write blocked.
3. **Macro-Opcode Validation:**
   * Verify all 60 user macro-opcodes using known test vectors:
     * Arithmetic: `ADD`, `SUB`, `MUL`, `DIV` for integer and float.
     * CORDIC: Compare $\sin(\theta), \cos(\theta), \tan(\theta)$ against fixed-point tolerances.
     * Transcendental: `LN`, `EXP`, `POW`.
4. **Z80 Benchmark Validation:**
   * Run the four canonical programs from `ProgrammersGuide.md` (Manhattan Distance, 3D Vector Norm, Sphere Volume, Quadratic Formula) in Immediate, Non-blocking, and Batch modes to verify bit-exact outputs.

---

## 6. Implementation Readiness Checklist

- [x] All physical registers and bitwidths defined in `SystemDesign.md`.
- [x] SysMEM EBR memory map and byte allocations defined.
- [x] 32-bit micro-instruction word bitfields defined.
- [x] All 22 micro-operations specified in Leventhal format.
- [x] All 60 user macro-opcodes and stack side effects documented in `ProgrammersGuide.md`.
- [x] Emulation constraints (byte arrays, hardware ALU emulation, no Python native floats) formalized in this document.
