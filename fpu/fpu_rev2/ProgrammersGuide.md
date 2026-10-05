# Zx50 FPU Rev 2 Z80 Programmer's Guide

This document is the definitive software reference for programming the FPGA-based Floating-Point and Stack Coprocessor on the **Zx50 CPU Card (Rev C4)** from the Z80 host CPU.

- **High-Level Hardware Architecture & Interface:** [FPU_REV2.md](file:///Users/marc/Documents/z80/Zx50/fpu/fpu_rev2/FPU_REV2.md)
- **Low-Level Internal Micro-Architecture:** [SystemDesign.md](file:///Users/marc/Documents/z80/Zx50/fpu/fpu_rev2/SystemDesign.md)
- **Development Roadmap:** [TODO.md](file:///Users/marc/Documents/z80/Zx50/fpu/fpu_rev2/TODO.md)

---

## 1. Coprocessor Interface & Host Ports

The FPU coprocessor communicates with the Z80 host across standard Z80 I/O space at base addresses **`0x70`** and **`0x71`**:

```text
+-----------+-----------+---------------+---------------------------------------------------+
| Port Addr | Direction | Register Name | Software Function                                 |
+-----------+-----------+---------------+---------------------------------------------------+
| 0x70      | Write     | DATA_PUSH     | Push 1 byte to Top of Stack (TOS); auto-increments SP |
| 0x70      | Read      | DATA_POP      | Pop 1 byte from Top of Stack (TOS); auto-decrements SP|
| 0x71      | Write     | CMD_EXEC      | Write User OpCode to trigger arithmetic/management|
| 0x71      | Read      | STATUS        | Read 8-bit coprocessor status and arithmetic flags|
+-----------+-----------+---------------+---------------------------------------------------+
```

### 1.1 Data Stack Port (`0x70`)
* **Pushing Operands:** Pushing a multi-byte word (`i32`, `f32`, `i64`, `f64`) requires streaming consecutive bytes to Port `0x70`. Hardware writes each byte to `Stack[SP]` in internal SysMEM EBR and automatically increments the byte pointer $SP \leftarrow SP + 1$.
* **Popping Results:** Popping a multi-byte word from the stack requires reading consecutive bytes from Port `0x70`. Hardware retrieves `Stack[SP - 1]` and automatically decrements $SP \leftarrow SP - 1$.
* **Block I/O Acceleration:** Z80 block I/O instructions (`OTIR` for push, `INIR` for pop) can stream full operands at maximum bus speed without software loop overhead.

### 1.2 Command & Status Port (`0x71`)
* **Writing an OpCode:** Writing an 8-bit opcode to Port `0x71` triggers the coprocessor execution engine or queues the command (depending on immediate vs. batch mode).
* **Reading Status:** Reading Port `0x71` returns the runtime status register with zero wait states.

---

## 2. Status Register (`STATUS[7:0]`)

The 8-bit `STATUS` register is the primary software interface for execution monitoring, branch testing, and error handling. It is returned on any I/O read of Port `0x71`:

```text
+--------+--------+--------+--------+-----------+------------+-------+----------+
| Bit 7  | Bit 6  | Bit 5  | Bit 4  | Bit 3     | Bit 2      | Bit 1 | Bit 0    |
+--------+--------+--------+--------+-----------+------------+-------+----------+
| BUSY   | ZERO   | SIGN   | CARRY  | OVERFLOW  | UNDERFLOW  | ERR   | Reserved |
+--------+--------+--------+--------+-----------+------------+-------+----------+
```

### Bit Definitions

* **`BUSY` (Bit 7):**
  * `1`: Coprocessor is currently executing an operation (or processing a batch queue).
  * `0`: Coprocessor is idle and ready to accept new commands or data.
  * In non-blocking mode, the host polls this bit before issuing commands or reading results.
* **`ZERO` (Bit 6, `ZF`):**
  * Set to `1` if the result of the last arithmetic operation is zero ($R = 0$).
* **`SIGN` (Bit 5, `SF`):**
  * Set to `1` if the result of the last operation is negative (MSB $= 1$).
* **`CARRY` (Bit 4, `CF`):**
  * Set to `1` on integer addition carry out or subtraction borrow.
* **`OVERFLOW` (Bit 3, `VF`):**
  * Set to `1` if signed integer arithmetic overflows the representable dynamic range, floating-point math overflows to $\pm\infty$, or a `PUSH` exceeds the 256-byte stack limit.
* **`UNDERFLOW` (Bit 2, `UF`):**
  * Set to `1` if floating-point math underflows to denormalized/zero, or a `POP` is attempted on an empty stack ($SP = 0$).
* **`ERR` (Bit 1, `EF`):**
  * Master error flag. Set to `1` on illegal opcodes, division by zero, invalid floating-point domain errors (e.g. $\sqrt{-x}$ or $\ln(-x)$), or stack boundary violations.
* **`Reserved` (Bit 0):**
  * Always reads as `0`.

### Z80 Assembly Status Polling Pattern
```z80
Wait_Fpu_Ready:
    IN   A, (0x71)          ; Read STATUS register
    RLCA                    ; Rotate Bit 7 (BUSY) into Carry
    JR   C, Wait_Fpu_Ready  ; Loop while BUSY == 1
    RRA                     ; Restore status byte
    AND  0x02               ; Test Bit 1 (ERR)
    JR   NZ, Fpu_Error_Trap ; Jump if ERR == 1
    RET
```

---

## 3. Supported Data Formats & Byte Ordering

All data operands on the stack are stored in standard **Little-Endian** byte order (least significant byte pushed first and at lowest memory address, most significant byte pushed last).

```text
32-Bit Types (i32, f32):  4 Bytes -> [Byte 0 (LSB)]  [Byte 1]  [Byte 2]  [Byte 3 (MSB)]
64-Bit Types (i64, f64):  8 Bytes -> [Byte 0 (LSB)]  ...                 [Byte 7 (MSB)]
```

### 3.1 32-Bit Signed Integer (`i32`)
* Standard 2's complement 32-bit signed integer.
* Value range: $-2,147,483,648$ to $+2,147,483,647$ (`0x80000000` to `0x7FFFFFFF`).

### 3.2 32-Bit Single-Precision Float (`f32`)
* IEEE-754 Single-Precision format:
  * 1 sign bit ($S$, bit 31).
  * 8 exponent bits ($E$, bits 30:23, bias = 127).
  * 23 fraction/mantissa bits ($M$, bits 22:0, implicit leading 1).
* Dynamic range: $\approx \pm 1.18 \times 10^{-38}$ to $\pm 3.40 \times 10^{38}$.

### 3.3 64-Bit Signed Integer (`i64`)
* Standard 2's complement 64-bit signed integer.
* Value range: $-2^{63}$ to $+2^{63}-1$.

### 3.4 64-Bit Double-Precision Float (`f64`)
* IEEE-754 Double-Precision format:
  * 1 sign bit ($S$, bit 63).
  * 11 exponent bits ($E$, bits 62:52, bias = 1023).
  * 52 fraction/mantissa bits ($M$, bits 51:0, implicit leading 1).
* Dynamic range: $\approx \pm 2.23 \times 10^{-308}$ to $\pm 1.80 \times 10^{308}$.

---

## 4. User OpCode Reference (Port `0x71` Language)

Opcodes written to Port `0x71` are single-byte commands (`0x00`–`0xFF`). For arithmetic and mathematical operations, the lower 3 bits define the target numeric format (`fff`).

### 4.1 Format Encoding Field (`fff`)

| Suffix `fff` | Binary | Target Data Type | Operand Size | Result Size | Min Binary Depth | Min Unary Depth |
|:---:|:---:|---|:---:|:---:|:---:|:---:|
| `_i32` | `0b000` | 32-bit Signed Integer | 4 Bytes | 4 Bytes | 8 Bytes | 4 Bytes |
| `_f32` | `0b001` | 32-bit IEEE Single Float | 4 Bytes | 4 Bytes | 8 Bytes | 4 Bytes |
| `_i64` | `0b010` | 64-bit Signed Integer | 8 Bytes | 8 Bytes | 16 Bytes | 8 Bytes |
| `_f64` | `0b011` | 64-bit IEEE Double Float | 8 Bytes | 8 Bytes | 16 Bytes | 8 Bytes |

---

### 4.2 Comprehensive User OpCode Summary Table

The table below summarizes all user opcodes. Stack effect follows standard Forth RPN notation `( before -- after )`:
* `NOS`: Next on stack (first pushed operand).
* `TOS`: Top of stack (second pushed operand).
* **Flags:** `X` = modified by result; `0` = cleared; `1` = set; `-` = unaffected; `*` = exception/error dependent.
* **Underflow Trapping:** Any operation attempted with fewer than the required bytes on the stack triggers **Stack Underflow** (`U=1, ERR=1`), aborting execution and preserving $SP$.

| Opcode | Hex Range | Mnemonic | Forth Stack Effect | $\Delta SP$ | Required Depth | Cycles (@80MHz) | BSY | Z | S | C | V | U | ERR | Primary Error / Side Effects |
|---|:---:|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `0b0000_0fff` | `0x00`–`0x03` | `ADD_fff` | `( a b -- sum )` | $-4$ / $-8$ | 8 / 16 B | 1–2 | X | X | X | X | X | * | * | Stack Underflow ($U=1, ERR=1$), Int/Float Overflow ($V=1$) |
| `0b0000_1fff` | `0x08`–`0x0B` | `SUB_fff` | `( a b -- diff )` | $-4$ / $-8$ | 8 / 16 B | 1–2 | X | X | X | X | X | * | * | Stack Underflow ($U=1, ERR=1$), Int/Float Overflow ($V=1$), Borrow ($C=1$) |
| `0b0001_0fff` | `0x10`–`0x13` | `MUL_fff` | `( a b -- prod )` | $-4$ / $-8$ | 8 / 16 B | 16–32 | X | X | X | 0 | X | * | * | Stack Underflow ($U=1, ERR=1$), Int/Float Overflow ($V=1$), Float Underflow ($U=1$) |
| `0b0001_1fff` | `0x18`–`0x1B` | `DIV_fff` | `( a b -- quot )` | $-4$ / $-8$ | 8 / 16 B | 16–32 | X | X | X | 0 | X | * | * | Stack Underflow ($U=1, ERR=1$), Div-by-Zero ($ERR=1, V=1$), Float Underflow ($U=1$) |
| `0b0010_00x1` | `0x21`, `0x23` | `SQRT_F32/F64`| `( x -- root )` | $0$ | 4 / 8 B | 16–32 | X | X | 0 | 0 | 0 | * | * | Float-only. Stack Underflow ($U=1, ERR=1$), Negative Operand ($ERR=1$) |
| `0b0010_10x1` | `0x29`, `0x2B` | `POW_F32/F64` | `( base exp -- res )` | $-4$ / $-8$ | 8 / 16 B | ~120 | X | X | X | 0 | X | * | * | Float-only. Stack Underflow ($U=1, ERR=1$), Exponent Overflow/Underflow |
| `0b0011_00x1` | `0x31`, `0x33` | `LN_F32/F64`  | `( x -- ln_x )` | $0$ | 4 / 8 B | ~60 | X | X | X | 0 | 0 | * | * | Float-only. Stack Underflow ($U=1, ERR=1$), Non-positive Operand $x \le 0$ ($ERR=1$) |
| `0b0011_10x1` | `0x39`, `0x3B` | `EXP_F32/F64` | `( x -- e_x )` | $0$ | 4 / 8 B | ~60 | X | X | 0 | 0 | X | * | * | Float-only. Stack Underflow ($U=1, ERR=1$), Exponent Overflow ($V=1$), Underflow ($U=1$) |
| `0b0101_0fff` | `0x50`–`0x53` | `CHS_fff` | `( x -- -x )` | $0$ | 4 / 8 B | 1–2 | X | X | X | X | X | * | * | Stack Underflow ($U=1, ERR=1$), Int Negate Overflow ($V=1$) |
| `0b0101_1fff` | `0x58`–`0x5B` | `ABS_fff` | `( x -- \|x\| )` | $0$ | 4 / 8 B | 1–2 | X | X | 0 | 0 | X | * | * | Stack Underflow ($U=1, ERR=1$), Int MaxNeg Overflow ($V=1$) |
| `0b0110_00x1` | `0x61`, `0x63` | `FLOOR_F32/F64`| `( x -- floor )` | $0$ | 4 / 8 B | ~10 | X | X | X | 0 | 0 | * | * | Float-only. Stack Underflow ($U=1, ERR=1$) |
| `0b0110_10x1` | `0x69`, `0x6B` | `CEIL_F32/F64` | `( x -- ceil )` | $0$ | 4 / 8 B | ~10 | X | X | X | 0 | 0 | * | * | Float-only. Stack Underflow ($U=1, ERR=1$) |
| `0b0111_00x1` | `0x71`, `0x73` | `SIN_F32/F64` | `( theta -- sin )` | $0$ | 4 / 8 B | ~36 | X | X | X | 0 | 0 | * | * | Float-only. Stack Underflow ($U=1, ERR=1$) |
| `0b0111_10x1` | `0x79`, `0x7B` | `COS_F32/F64` | `( theta -- cos )` | $0$ | 4 / 8 B | ~36 | X | X | X | 0 | 0 | * | * | Float-only. Stack Underflow ($U=1, ERR=1$) |
| `0b1000_00x1` | `0x81`, `0x83` | `TAN_F32/F64` | `( theta -- tan )` | $0$ | 4 / 8 B | ~52 | X | X | X | 0 | X | * | * | Float-only. Stack Underflow ($U=1, ERR=1$), Asymptote Overflow ($V=1$) |
| `0b1010_xxxx` | `0xA0`–`0xAF` | `PUSH_CONST`| `( -- const )` | $+4$ / $+8$ | 0 B | 2–3 | X | 0 | 0 | 0 | * | - | * | Stack Overflow ($V=1, ERR=1$ if $SP + \text{bytes} > 256$) |
| `0b1100_0000` | `0xC0` | `DUP4` | `( a -- a a )` | $+4$ | 4 B | 2 | X | - | - | - | * | * | * | Stack Underflow ($U=1, ERR=1$), Stack Overflow ($V=1, ERR=1$) |
| `0b1100_0001` | `0xC1` | `DUP8` | `( a -- a a )` | $+8$ | 8 B | 3 | X | - | - | - | * | * | * | Stack Underflow ($U=1, ERR=1$), Stack Overflow ($V=1, ERR=1$) |
| `0b1100_0010` | `0xC2` | `CONV_U32_U64`| `( u32 -- u64 )` | $+4$ | 4 B | 2 | X | X | X | 0 | * | * | * | Zero-extends 32-bit uint to 64-bit uint |
| `0b1100_0011` | `0xC3` | `CONV_U64_U32`| `( u64 -- u32 )` | $-4$ | 8 B | 2 | X | X | X | 0 | X | * | * | Truncates 64-bit uint to 32-bit uint ($V=1$ on overflow) |
| `0b1100_0110` | `0xC6` | `CLEAR_STACK` | `( ... -- )` | $SP \leftarrow 0$ | 0 B | 1 | X | 1 | 0 | 0 | 0 | 0 | 0 | Clears $SP \leftarrow 0$, $OSP \leftarrow 0$, all error flags cleared |
| `0b1100_1000` | `0xC8` | `CONV_I32_I64`| `( i32 -- i64 )` | $+4$ | 4 B | 2 | X | X | X | 0 | * | * | * | Stack Underflow ($U=1, ERR=1$), Stack Overflow ($V=1, ERR=1$) |
| `0b1100_1001` | `0xC9` | `CONV_F32_F64`| `( f32 -- f64 )` | $+4$ | 4 B | 2 | X | X | X | 0 | * | * | * | Stack Underflow ($U=1, ERR=1$), Stack Overflow ($V=1, ERR=1$) |
| `0b1100_1010` | `0xCA` | `CONV_I64_I32`| `( i64 -- i32 )` | $-4$ | 8 B | 2 | X | X | X | 0 | X | * | * | Stack Underflow ($U=1, ERR=1$), Truncation Overflow ($V=1$) |
| `0b1100_1011` | `0xCB` | `CONV_F64_F32`| `( f64 -- f32 )` | $-4$ | 8 B | 2 | X | X | X | 0 | X | * | * | Stack Underflow ($U=1, ERR=1$), Exponent Overflow ($V=1$), Underflow ($U=1$) |
| `0b1100_1100` | `0xCC` | `CONV_I32_F32`| `( i32 -- f32 )` | $0$ | 4 B | ~5 | X | X | X | 0 | 0 | 0 | * | Signed 32-bit int to IEEE-754 single float |
| `0b1100_1101` | `0xCD` | `CONV_F32_I32`| `( f32 -- i32 )` | $0$ | 4 B | ~5 | X | X | X | 0 | X | 0 | * | IEEE-754 single float to signed 32-bit int (truncate, $V=1$ on overflow) |
| `0b1100_1110` | `0xCE` | `CONV_I64_F64`| `( i64 -- f64 )` | $0$ | 8 B | ~6 | X | X | X | 0 | 0 | 0 | * | Signed 64-bit int to IEEE-754 double float |
| `0b1100_1111` | `0xCF` | `CONV_F64_I64`| `( f64 -- i64 )` | $0$ | 8 B | ~6 | X | X | X | 0 | X | 0 | * | IEEE-754 double float to signed 64-bit int (truncate, $V=1$ on overflow) |
| `0b1101_xxxx` | `0xD0`–`0xDF` | `CP [x], TOS` | `( val -- )` | $-4$ / $-8$ | 4 / 8 B | 2 | X | - | - | - | - | * | * | Stack Underflow ($U=1, ERR=1$) |
| `0b1110_xxxx` | `0xE0`–`0xEF` | `CP TOS, [x]` | `( -- val )` | $+4$ / $+8$ | 0 B | 2 | X | - | - | - | * | - | * | Stack Overflow ($V=1, ERR=1$ if $SP + \text{bytes} > 256$) |
| `0b1111_0000` | `0xF0` | `ZERO_MEM` | `( -- )` | $0$ | 0 B | 17 | X | - | - | - | - | - | - | Clears all 16 user memory storage slots to zero |
| `0b1111_1010` | `0xFA` | `EXEC_BATCH` | `( ... -- ... )` | Varies | Varies | Burst | X | * | * | * | * | * | * | Executes queued command stack; holds `BUSY=1` throughout |
| `0b1111_1011` | `0xFB` | `SET_BATCH` | `( -- )` | $0$ | 0 B | 1 | 0 | - | - | - | - | - | - | Sets Batch Queuing Mode (`IMMEDIATE = 0`) |
| `0b1111_1100` | `0xFC` | `SET_IMMEDIATE`| `( -- )` | $0$ | 0 B | 1 | 0 | - | - | - | - | - | - | Sets Immediate Execution Mode (`IMMEDIATE = 1`) |
| `0b1111_1101` | `0xFD` | `SET_NONBLOCKING`| `( -- )` | $0$ | 0 B | 1 | 0 | - | - | - | - | - | - | Clears Blocking Mode (`BLOCKING = 0`, no `~WAIT~`) |
| `0b1111_1110` | `0xFE` | `SET_BLOCKING`| `( -- )` | $0$ | 0 B | 1 | 0 | - | - | - | - | - | - | Sets Blocking Mode (`BLOCKING = 1`, asserts `~WAIT~`) |
| `0b1111_1111` | `0xFF` | `RESET` | `( ... -- )` | $SP \leftarrow 0$ | 0 B | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | Master soft reset; clears all flags, $SP \leftarrow 0$, $OSP \leftarrow 0$ |

---

### 4.3 Standardized User Instruction Reference (Leventhal Format)

```
================================================================================
ADD_fff — ADDITION (i32, f32, i64, f64)
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Precision | Operand Size | Required Depth | Net $\Delta SP$ | Latency (@80MHz) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`ADD_I32`** | `0x00` | `0b0000_0000` | 32-bit Signed Int   | 4 Bytes | 8 Bytes  | $-4$ Bytes | 1 Cycle (12.5 ns) |
| **`ADD_F32`** | `0x01` | `0b0000_0001` | 32-bit IEEE Float   | 4 Bytes | 8 Bytes  | $-4$ Bytes | ~12 Cycles (150 ns)|
| **`ADD_I64`** | `0x02` | `0b0000_0010` | 64-bit Signed Int   | 8 Bytes | 16 Bytes | $-8$ Bytes | 2 Cycles (25 ns)  |
| **`ADD_F64`** | `0x03` | `0b0000_0011` | 64-bit IEEE Double  | 8 Bytes | 16 Bytes | $-8$ Bytes | ~20 Cycles (250 ns)|

#### Forth Stack Diagram
```text
( NOS TOS -- Sum )
Before: [ ... | a (NOS) | b (TOS) ]  <-- SP
After:  [ ... | (a + b)           ]  <-- SP (shrinks by 1 operand)
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR
+-----+-----+-----+-----+-----+-----+-----+
|  X  |  X  |  X  |  X  |  X  |  *  |  *  |
+-----+-----+-----+-----+-----+-----+-----+
```
* **`BSY`**: Asserted to 1 while computation executes; cleared to 0 when finished (or held high continuously in Batch Mode).
* **`Z`**: Set to 1 if result is zero (`0` or `+0.0` / `-0.0`); cleared to 0 otherwise.
* **`S`**: Set to 1 if result is negative (MSB = 1); cleared to 0 otherwise.
* **`C`**:
  * In `ADD_I32` / `ADD_I64`: Set to 1 if unsigned carry occurred out of MSB; cleared to 0 otherwise.
  * In `ADD_F32` / `ADD_F64`: Cleared to 0.
* **`V`**:
  * In `ADD_I32` / `ADD_I64`: Set to 1 if signed two's-complement overflow occurred (e.g. positive + positive = negative).
  * In `ADD_F32` / `ADD_F64`: Set to 1 if floating-point exponent overflow occurred ($E > +127$ or $E > +1023$), returning signed $\pm \infty$.
* **`U` (Side Effect / Exception):**
  * In `ADD_F32` / `ADD_F64`: Set to 1 if floating-point exponent underflow occurred.
  * **Stack Underflow Trapping:** If fewer than 2 operands are present on the stack ($SP < 8$ bytes for 32-bit, or $SP < 16$ bytes for 64-bit), hardware aborts execution and asserts **`U = 1`** and **`ERR = 1`**.
* **`ERR` (Side Effect / Exception):**
  * Set to 1 if Stack Underflow occurred, or if floating-point overflow produced a trap condition.

#### Stack Side Effects & Exception Triggers
* **Stack Underflow ($SP < \text{Depth}$):** If the stack does not contain at least 2 complete operands, `STATUS[2]` (`UNDERFLOW`) and `STATUS[1]` (`ERR`) are asserted immediately. $SP$ is unchanged, and no invalid memory write occurs.
* **Result Replacement:** The second operand ($TOS$) and first operand ($NOS$) are popped, and their algebraic sum replaces them at the new $TOS$.

#### Concrete Z80 Assembly & Stack Example
```z80
; Compute 0x7FFFFFFF + 0x00000001 in 32-bit Integer Mode (Signed Overflow)
; Stack before: TOS = 0x00000001, NOS = 0x7FFFFFFF (SP = 8)

    LD   A, 0x00            ; Opcode for ADD_I32
    OUT  (0x71), A          ; Execute ADD_I32 (waits if BLOCKING=1)

; Stack after:  TOS = 0x80000000 (-2147483648), SP = 4
; Status register read from Port 0x71 returns:
;   STATUS = 0b0010_1000 (0x28)
;              |||| ||||
;              |||| |||+--- Bit 0: Reserved (0)
;              |||| ||+---- Bit 1: ERR = 0 (No stack error)
;              |||| |+----- Bit 2: UNDERFLOW = 0
;              |||| +------ Bit 3: OVERFLOW = 1 (Signed int overflow)
;              |||+-------- Bit 4: CARRY = 0 (No unsigned carry out)
;              ||+--------- Bit 5: SIGN = 1 (Result bit 31 is 1)
;              |+---------- Bit 6: ZERO = 0 (Result non-zero)
;              +----------- Bit 7: BUSY = 0 (Finished)
```

---

```
================================================================================
SUB_fff — SUBTRACTION (i32, f32, i64, f64)
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Precision | Required Depth | Net $\Delta SP$ | Latency (@80MHz) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`SUB_I32`** | `0x08` | `0b0000_1000` | 32-bit Signed Int  | 8 Bytes  | $-4$ Bytes | 1 Cycle (12.5 ns) |
| **`SUB_F32`** | `0x09` | `0b0000_1001` | 32-bit IEEE Float  | 8 Bytes  | $-4$ Bytes | ~12 Cycles (150 ns)|
| **`SUB_I64`** | `0x0A` | `0b0000_1010` | 64-bit Signed Int  | 16 Bytes | $-8$ Bytes | 2 Cycles (25 ns)  |
| **`SUB_F64`** | `0x0B` | `0b0000_1011` | 64-bit IEEE Double | 16 Bytes | $-8$ Bytes | ~20 Cycles (250 ns)|

#### Forth Stack Diagram
```text
( NOS TOS -- Difference )
Evaluates: Difference = NOS - TOS  (First pushed operand minus second pushed operand)
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR
+-----+-----+-----+-----+-----+-----+-----+
|  X  |  X  |  X  |  X  |  X  |  *  |  *  |
+-----+-----+-----+-----+-----+-----+-----+
```
* **`C`**: In integer modes, set to 1 if an unsigned borrow occurred ($NOS < TOS$); cleared to 0 otherwise.
* **`V`**: Set to 1 on signed two's-complement overflow or float exponent overflow.
* **`U`, `ERR`**: Set to 1 if Stack Underflow occurred ($SP < \text{Depth}$).

---

```
================================================================================
MUL_fff — MULTIPLICATION (i32, f32, i64, f64)
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Precision | Required Depth | Net $\Delta SP$ | Latency (@80MHz) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`MUL_I32`** | `0x10` | `0b0001_0000` | 32-bit Signed Int  | 8 Bytes  | $-4$ Bytes | 16 Cycles (200 ns)|
| **`MUL_F32`** | `0x11` | `0b0001_0001` | 32-bit IEEE Float  | 8 Bytes  | $-4$ Bytes | ~18 Cycles (225 ns)|
| **`MUL_I64`** | `0x12` | `0b0001_0010` | 64-bit Signed Int  | 16 Bytes | $-8$ Bytes | 32 Cycles (400 ns)|
| **`MUL_F64`** | `0x13` | `0b0001_0011` | 64-bit IEEE Double | 16 Bytes | $-8$ Bytes | ~30 Cycles (375 ns)|

#### Forth Stack Diagram
```text
( NOS TOS -- Product )
Evaluates: Product = NOS * TOS
```

#### Status Flags & Side Effects
* **`V`**: In integer modes, set to 1 if the high word(s) of the product contain significant non-sign bits (truncated integer overflow). In float modes, set on exponent overflow.
* **`U`**: In float modes, set on exponent underflow.
* **Stack Underflow:** Asserts `U = 1` and `ERR = 1` if $SP < 8$ (32-bit) or $SP < 16$ (64-bit).

#### Result Widths & Widening Multiplication
* **Stack-Neutral Result Widths:** In keeping with Forth and RPN stack invariants, integer multiplication produces a result of the same width as its operands:
  - `MUL_I32`: $32 \times 32 \to 32\text{-bit}$ product + `VF` (overflow asserted if true product exceeds 32 bits signed).
  - `MUL_I64`: $64 \times 64 \to 64\text{-bit}$ product + `VF` (overflow asserted if true product exceeds 64 bits signed).
* **Widening Multiplication ($32 \times 32 \to 64$):** If a full 64-bit product of two 32-bit values is desired without risk of truncation, convert the operands to 64-bit prior to multiplying:
  - **Signed widening multiply:** Convert operands via `CONV_I32_I64` and execute `MUL_I64`.
  - **Unsigned widening multiply:** Convert operands via `CONV_U32_U64` and execute `MUL_I64`.

---

```
================================================================================
DIV_fff — DIVISION (i32, f32, i64, f64)
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Precision | Required Depth | Net $\Delta SP$ | Latency (@80MHz) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`DIV_I32`** | `0x18` | `0b0001_1000` | 32-bit Signed Int  | 8 Bytes  | $-4$ Bytes | 18 Cycles (225 ns)|
| **`DIV_F32`** | `0x19` | `0b0001_1001` | 32-bit IEEE Float  | 8 Bytes  | $-4$ Bytes | ~24 Cycles (300 ns)|
| **`DIV_I64`** | `0x1A` | `0b0001_1010` | 64-bit Signed Int  | 16 Bytes | $-8$ Bytes | 34 Cycles (425 ns)|
| **`DIV_F64`** | `0x1B` | `0b0001_1011` | 64-bit IEEE Double | 16 Bytes | $-8$ Bytes | ~38 Cycles (475 ns)|

#### Forth Stack Diagram
```text
( NOS TOS -- Quotient )
Evaluates: Quotient = NOS / TOS  (First pushed operand divided by second pushed operand)
```

#### Status Flags & Side Effects
```text
  BSY    Z     S     C     V     U    ERR
+-----+-----+-----+-----+-----+-----+-----+
|  X  |  X  |  X  |  0  |  X  |  *  |  *  |
+-----+-----+-----+-----+-----+-----+-----+
```
* **Division by Zero ($TOS == 0$):**
  * Hardware immediately detects divisor = 0.
  * Sets **`ERR = 1`** and **`OVERFLOW = 1`**.
  * In integer mode: pushes `0x7FFFFFFF` (or `0x80000000` based on sign).
  * In float mode: pushes signed $\pm \infty$ (`0x7F800000` / `0xFF800000`).
* **Stack Underflow:** Asserts `U = 1` and `ERR = 1` if $SP < \text{Depth}$.

---

```
================================================================================
SQRT_F32 / SQRT_F64 — FLOATING-POINT SQUARE ROOT
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Precision | Required Depth | Net $\Delta SP$ | Latency (@80MHz) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`SQRT_F32`** | `0x21` | `0b0010_0001` | 32-bit IEEE Float  | 4 Bytes  | 0 Bytes | ~20 Cycles (250 ns)|
| **`SQRT_F64`** | `0x23` | `0b0010_0011` | 64-bit IEEE Double | 8 Bytes  | 0 Bytes | ~32 Cycles (400 ns)|

> **Architectural Note:** Transcendental and root operations (`SQRT`, `POW`, `LN`, `EXP`, `SIN`, `COS`, `TAN`) operate strictly on floating-point data (`F32` and `F64`). Integer variants are not implemented (`0x20` and `0x22` are reserved). To compute the square root of an integer, the programmer must explicitly convert the integer argument via `CONV_I32_F32` (or `CONV_I64_F64`) prior to calling `SQRT_F32` (or `SQRT_F64`), and convert the result back via `CONV_F32_I32` (or `FLOOR_F32`) if an integer result is desired.

#### Forth Stack Diagram
```text
SQRT_F32: ( f32 -- sqrt_f32 )
SQRT_F64: ( f64 -- sqrt_f64 )
```

#### Status Flags & Side Effects
* **Domain Error ($TOS < 0$):** Attempting square root of a negative float (except $-0.0$, where $\sqrt{-0.0} = -0.0$) sets **`ERR = 1`**.
* **Zero Input:** $\sqrt{+0.0} = +0.0$; $\sqrt{-0.0} = -0.0$; does not set `ERR`.
* **Stack Underflow:** If $SP < 4$ (`SQRT_F32`) or $SP < 8$ (`SQRT_F64`), asserts **`U = 1`** and **`ERR = 1`**.

---

```
================================================================================
CHS_fff & ABS_fff — UNARY SIGN OPERATIONS (i32, f32, i64, f64)
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Precision | Function | Required Depth | Net $\Delta SP$ | Latency |
|---|:---:|:---:|:---:|---|:---:|:---:|:---:|
| **`CHS_I32`** | `0x50` | `0b0101_0000` | 32-bit Int   | Negate: $TOS \leftarrow -TOS$ | 4 Bytes | 0 | 1 Cycle |
| **`CHS_F32`** | `0x51` | `0b0101_0001` | 32-bit Float | Invert sign bit 31            | 4 Bytes | 0 | 1 Cycle |
| **`CHS_I64`** | `0x52` | `0b0101_0010` | 64-bit Int   | Negate: $TOS \leftarrow -TOS$ | 8 Bytes | 0 | 2 Cycles|
| **`CHS_F64`** | `0x53` | `0b0101_0011` | 64-bit Float | Invert sign bit 63            | 8 Bytes | 0 | 1 Cycle |
| **`ABS_I32`** | `0x58` | `0b0101_1000` | 32-bit Int   | Absolute value $\|TOS\|$      | 4 Bytes | 0 | 1 Cycle |
| **`ABS_F32`** | `0x59` | `0b0101_1001` | 32-bit Float | Force sign bit 31 to 0        | 4 Bytes | 0 | 1 Cycle |
| **`ABS_I64`** | `0x5A` | `0b0101_1010` | 64-bit Int   | Absolute value $\|TOS\|$      | 8 Bytes | 0 | 2 Cycles|
| **`ABS_F64`** | `0x5B` | `0b0101_1011` | 64-bit Float | Force sign bit 63 to 0        | 8 Bytes | 0 | 1 Cycle |

#### Status Flags & Side Effects
* **Maximum Negative Integer Overflow (`0x80000000`):** In 2's complement, $-(-2147483648)$ cannot be represented in 32 bits; sets **`OVERFLOW = 1`**.
* **Stack Underflow:** Asserts `U = 1` and `ERR = 1` if $SP < \text{Depth}$.

---

```
================================================================================
SIN_fff, COS_fff, TAN_fff — CORDIC TRIGONOMETRICS (f32, f64)
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Function | Required Depth | Net $\Delta SP$ | Latency (@80MHz) |
|---|:---:|:---:|---|:---:|:---:|:---:|
| **`SIN_F32`** | `0x71` | `0b0111_0001` | $\sin(\theta)$ (radians) | 4 Bytes | 0 | ~36 Cycles (450 ns) |
| **`COS_F32`** | `0x79` | `0b0111_1001` | $\cos(\theta)$ (radians) | 4 Bytes | 0 | ~36 Cycles (450 ns) |
| **`TAN_F32`** | `0x81` | `0b1000_0001` | $\tan(\theta)$ (radians) | 4 Bytes | 0 | ~52 Cycles (650 ns) |
| **`SIN_F64`** | `0x73` | `0b0111_0011` | $\sin(\theta)$ (radians) | 8 Bytes | 0 | ~64 Cycles (800 ns) |
| **`COS_F64`** | `0x7B` | `0b0111_1011` | $\cos(\theta)$ (radians) | 8 Bytes | 0 | ~64 Cycles (800 ns) |
| **`TAN_F64`** | `0x83` | `0b1000_0011` | $\tan(\theta)$ (radians) | 8 Bytes | 0 | ~90 Cycles (1.1 $\mu$s)|

#### Forth Stack Diagram
```text
( theta -- f(theta) )
```

#### Status Flags & Side Effects
* Evaluated via physical CORDIC rotation loop across `{AX, BX, DX}` at 1 cycle per bit.
* **Stack Underflow:** If $SP < 4$ (`f32`) or $SP < 8$ (`f64`), asserts **`U = 1`** and **`ERR = 1`**.
* **Tangent Asymptote Overflow:** Near $\pm \pi/2$, `TAN` sets **`OVERFLOW = 1`**.

---

```
================================================================================
DUP4 & DUP8 — DUPLICATE TOP OF STACK
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Duplicated Width | Required Depth | Net $\Delta SP$ | Latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`DUP4`** | `0xC0` | `0b1100_0000` | 4 Bytes (`i32`, `f32`) | 4 Bytes | $+4$ Bytes | 2 Cycles (25 ns) |
| **`DUP8`** | `0xC1` | `0b1100_0001` | 8 Bytes (`i64`, `f64`) | 8 Bytes | $+8$ Bytes | 3 Cycles (37.5 ns)|

#### Forth Stack Diagram
```text
DUP4: ( a -- a a )
DUP8: ( a_64 -- a_64 a_64 )
```

#### Status Flags & Side Effects
```text
  BSY    Z     S     C     V     U    ERR
+-----+-----+-----+-----+-----+-----+-----+
|  X  |  -  |  -  |  -  |  *  |  *  |  *  |
+-----+-----+-----+-----+-----+-----+-----+
```
* **Stack Underflow ($SP < \text{Width}$):** If stack is empty, asserting `DUP4` or `DUP8` sets **`UNDERFLOW = 1`** and **`ERR = 1`**. Stack pointer is unchanged.
* **Stack Overflow ($SP + \text{Width} > 256$):** If the 64-word stack is full, duplicating sets **`OVERFLOW = 1`** and **`ERR = 1`**. Memory write is aborted.

---

```
================================================================================
CONV_xxx_yyy — DATA TYPE CONVERSIONS
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex | Binary | Conversion Operation | Required Depth | Net $\Delta SP$ | Side Effects / Flags |
|---|:---:|:---:|---|:---:|:---:|---|
| **`CONV_U32_U64`** | `0xC2` | `0b1100_0010` | Zero-extends 32-bit uint to 64-bit uint | 4 Bytes | $+4$ Bytes | Checks Stack Overflow ($V=1, ERR=1$) |
| **`CONV_U64_U32`** | `0xC3` | `0b1100_0011` | Truncates 64-bit uint to 32-bit uint    | 8 Bytes | $-4$ Bytes | Sets `OVERFLOW = 1` if value $> 2^{32}-1$ |
| **`CONV_I32_I64`** | `0xC8` | `0b1100_1000` | Sign-extends 32-bit int to 64-bit int | 4 Bytes | $+4$ Bytes | Checks Stack Overflow ($V=1, ERR=1$) |
| **`CONV_F32_F64`** | `0xC9` | `0b1100_1001` | Expands IEEE single to double float   | 4 Bytes | $+4$ Bytes | Checks Stack Overflow ($V=1, ERR=1$) |
| **`CONV_I64_I32`** | `0xCA` | `0b1100_1010` | Truncates 64-bit int to 32-bit int    | 8 Bytes | $-4$ Bytes | Sets `OVERFLOW = 1` if value $> 2^{31}-1$ or $< -2^{31}$ |
| **`CONV_F64_F32`** | `0xCB` | `0b1100_1011` | Converts IEEE double to single float  | 8 Bytes | $-4$ Bytes | Sets `OVERFLOW`/`UNDERFLOW` on exp limits |
| **`CONV_I32_F32`** | `0xCC` | `0b1100_1100` | Converts signed 32-bit int to single  | 4 Bytes | $0$ Bytes  | Normalizes via LZC; no precision loss |
| **`CONV_F32_I32`** | `0xCD` | `0b1100_1101` | Truncates single to signed 32-bit int | 4 Bytes | $0$ Bytes  | Sets `OVERFLOW = 1` if $|val| \ge 2^{31}$ |
| **`CONV_I64_F64`** | `0xCE` | `0b1100_1110` | Converts signed 64-bit int to double  | 8 Bytes | $0$ Bytes  | Normalizes via LZC64; no precision loss |
| **`CONV_F64_I64`** | `0xCF` | `0b1100_1111` | Truncates double to signed 64-bit int | 8 Bytes | $0$ Bytes  | Sets `OVERFLOW = 1` if $|val| \ge 2^{63}$ |

#### Status Flags & Side Effects
* **Stack Underflow:** Asserts `U = 1` and `ERR = 1` if source operand is missing.
* **Truncation Overflow in `CONV_I64_I32`:** If upper 32 bits of 64-bit int are not a valid sign extension of lower 32 bits, sets **`OVERFLOW = 1`**.
* **Truncation Overflow in `CONV_U64_U32`:** If upper 32 bits of 64-bit uint are non-zero, sets **`OVERFLOW = 1`**.
* **Float-to-Int Range Overflow (`CONV_F32_I32`, `CONV_F64_I64`):** If the float magnitude exceeds the representable signed integer range, sets **`OVERFLOW = 1`** and clamps to maximum/minimum integer value.

---

```
================================================================================
CP [xxxx], TOS & CP TOS, [xxxx] — USER STORAGE MEMORY SLOTS
================================================================================
```

#### Opcode Encodings & Execution Timing
| Mnemonic | Hex Pattern | Binary Pattern | Function | Required Depth | Net $\Delta SP$ | Latency |
|---|:---:|:---:|---|:---:|:---:|:---:|
| **`CP [xxxx], TOS`** | `0xD0`–`0xDF` | `0b1101_xxxx` | Store TOS into user slot `xxxx` (0..15) | 4 Bytes | $-4$ Bytes | 2 Cycles |
| **`CP TOS, [xxxx]`** | `0xE0`–`0xEF` | `0b1110_xxxx` | Push user slot `xxxx` (0..15) onto TOS  | 0 Bytes | $+4$ Bytes | 2 Cycles |
| **`ZERO_MEM`**       | `0xF0`        | `0b1111_0000` | Clear all 16 user slots to 0            | 0 Bytes | 0 Bytes    | 17 Cycles|

#### Forth Stack Diagram
```text
CP [xxxx], TOS: ( val -- )       Pops TOS and writes to user slot xxxx
CP TOS, [xxxx]: ( -- val )       Reads user slot xxxx and pushes to TOS
```

#### Status Flags & Side Effects
* **`CP [xxxx], TOS` Stack Underflow:** If $SP < 4$, sets **`UNDERFLOW = 1`** and **`ERR = 1`**; memory slot is not modified.
* **`CP TOS, [xxxx]` Stack Overflow:** If stack is full ($SP \ge 256$), sets **`OVERFLOW = 1`** and **`ERR = 1`**; stack write is aborted.

---

```
================================================================================
PUSH_CONST — MATHEMATICAL CONSTANTS
================================================================================
```

#### Opcode Encodings
| Mnemonic | Hex | Precision | Constant & Approximate Value | Net $\Delta SP$ | IEEE-754 Hex Value |
|---|:---:|:---:|---|:---:|:---:|
| **`PUSH_PI_32`**      | `0xA0` | `f32` | $\pi \approx 3.14159265$ | $+4$ Bytes | `0x40490FDB` |
| **`PUSH_PI_64`**      | `0xA1` | `f64` | $\pi \approx 3.141592653589793$ | $+8$ Bytes | `0x400921FB_54442D18` |
| **`PUSH_E_32`**       | `0xA2` | `f32` | $e \approx 2.7182818$ | $+4$ Bytes | `0x402DF854` |
| **`PUSH_E_64`**       | `0xA3` | `f64` | $e \approx 2.718281828459045$ | $+8$ Bytes | `0x4005BF0A_8B145769` |
| **`PUSH_LN2_32`**     | `0xA4` | `f32` | $\ln(2) \approx 0.69314718$ | $+4$ Bytes | `0x3F317218` |
| **`PUSH_LN2_64`**     | `0xA5` | `f64` | $\ln(2) \approx 0.693147180559945$ | $+8$ Bytes | `0x3FE62E42_FEFA39EF` |
| **`PUSH_LOG2E_32`**   | `0xA6` | `f32` | $\log_2(e) \approx 1.442695$ | $+4$ Bytes | `0x3FB8AA3B` |
| **`PUSH_LOG2E_64`**   | `0xA7` | `f64` | $\log_2(e) \approx 1.442695040888963$ | $+8$ Bytes | `0x3FF71547_652B82FE` |
| **`PUSH_LOG2_10_32`** | `0xA8` | `f32` | $\log_2(10) \approx 3.321928$ | $+4$ Bytes | `0x40549A78` |
| **`PUSH_LOG2_10_64`** | `0xA9` | `f64` | $\log_2(10) \approx 3.321928094887362$ | $+8$ Bytes | `0x400A934F_0979A371` |
| **`PUSH_LOG10_2_32`** | `0xAA` | `f32` | $\log_{10}(2) \approx 0.301030$ | $+4$ Bytes | `0x3E9A209B` |
| **`PUSH_LOG10_2_64`** | `0xAB` | `f64` | $\log_{10}(2) \approx 0.301029995663981$ | $+8$ Bytes | `0x3FD34413_509F79FF` |
| **`PUSH_SQRT2_32`**   | `0xAC` | `f32` | $\sqrt{2} \approx 1.4142135$ | $+4$ Bytes | `0x3FB504F3` |
| **`PUSH_SQRT2_64`**   | `0xAD` | `f64` | $\sqrt{2} \approx 1.414213562373095$ | $+8$ Bytes | `0x3FF6A09E_667F3BCD` |
| **`PUSH_INV_SQRT2_32`**|`0xAE` | `f32` | $1/\sqrt{2} \approx 0.7071068$ | $+4$ Bytes | `0x3F3504F3` |
| **`PUSH_INV_SQRT2_64`**|`0xAF` | `f64` | $1/\sqrt{2} \approx 0.707106781186548$| $+8$ Bytes | `0x3FE6A09E_667F3BCD` |

#### Status Flags & Side Effects
* Loads constant using scratch register `FL` / `FX` and pushes onto stack. Leaves math register `DX` uncorrupted.
* **Stack Overflow:** If $SP + \text{bytes} > 256$, sets **`OVERFLOW = 1`** and **`ERR = 1`**.

---

```
================================================================================
MANAGEMENT COMMANDS (RESET, MODES, BATCH EXECUTION)
================================================================================
```

#### Opcode Encodings
| Mnemonic | Hex | Binary | Function |
|---|:---:|:---:|---|
| **`RESET`**           | `0xFF` | `0b1111_1111` | Master soft reset; clears all flags, $SP \leftarrow 0$, $OSP \leftarrow 0$ |
| **`SET_BLOCKING`**    | `0xFE` | `0b1111_1110` | Asserts host `~WAIT~` during computation (Default) |
| **`SET_NONBLOCKING`**| `0xFD` | `0b1111_1101` | Disables host `~WAIT~`; host polls `BUSY` flag |
| **`SET_IMMEDIATE`**   | `0xFC` | `0b1111_1100` | Executes each opcode upon arrival (Default) |
| **`SET_BATCH`**       | `0xFB` | `0b1111_1011` | Queues opcodes into Command Stack at `0x0340` |
| **`EXEC_BATCH`**      | `0xFA` | `0b1111_1010` | Executes queued batch back-to-back at 80 MHz; holds `BUSY=1` throughout |
| **`CLEAR_STACK`**     | `0xC6` | `0b1100_0110` | Resets $SP \leftarrow 0$ and $OSP \leftarrow 0$, clears error flags |

#### Status Flags & Side Effects
* `RESET` and `CLEAR_STACK` force `STATUS` flags to `0b0100_0000` (`ZERO = 1`, all error flags cleared).
* `EXEC_BATCH` asserts `BUSY = 1` and keeps it high continuously until the last operation in the batch executes `RET` (or until an error occurs), guaranteeing continuous wait-state generation in blocking mode.

---

## 5. Execution & Programming Models

The Zx50 FPU supports three distinct programming paradigms:

### 5.1 Immediate Blocking Mode (Default)
In this mode (`BLOCKING = 1`, `IMMEDIATE = 1`), writing any execution opcode to Port `0x71` causes the FPGA to pull the host `~WAIT~` line low on the Z80 clock edge. The Z80 is held in wait states until the computation finishes at 80 MHz, then resumes execution on the very next instruction cycle.
* **Pros:** Simplest programming model; zero status polling overhead; synchronous code execution.
* **When to Use:** Standard inline calculations and single-instruction evaluations.

### 5.2 Immediate Non-Blocking Mode
Configured by issuing `SET_NONBLOCKING` (`0xFD`). Writing an opcode to Port `0x71` does **not** assert `~WAIT~`. The Z80 can continue executing instructions (updating displays, servicing interrupts, or doing other work) while the FPU computes in parallel at 80 MHz.
* **Pros:** Complete host CPU / coprocessor concurrency.
* **When to Use:** Long transcendental calculations ($\sin, \cos, \ln, e^x$), 64-bit division, or iterative algorithms.

### 5.3 Batch Queuing Mode
Configured by issuing `SET_BATCH` (`0xFB`). Arriving opcodes written to Port `0x71` are not executed; instead, they are queued into the 32-byte Command Stack. When the formula is complete, the Z80 issues `EXEC_BATCH` (`0xFA`). The FPGA executes all queued operations in a single high-speed burst at 80 MHz.
* **Continuous Wait Generation in Blocking Mode:** When combined with Blocking Mode (`BLOCKING = 1`), issuing `EXEC_BATCH` causes the dispatcher to assert `BUSY <= 1` and keep it continuously high across the entire sequence of queued microcode operations. Because $\text{BWAIT\_N} = \text{BLOCKING} \ \& \ \text{BUSY}$, host `~WAIT~` remains cleanly held low for the entire batch execution with zero bus glitches, releasing only after the final result is resting on TOS.
* **Pros:** Eliminates the latency of repeatedly polling the status register between steps; the entire sequence of opcodes can be streamed to Port `0x71` using a single Z80 `OTIR` instruction.
* **When to Use:** Multi-step formula evaluations (e.g. vector norms, quadratic roots, coordinate rotations).

---

## 6. Canonical Example Programs

We implement **four benchmark problems** across the different execution models to illustrate practical programming techniques:
1. **Problem 1: Manhattan Distance** of two 2D integer points ($|X_1 - X_2| + |Y_1 - Y_2|$) in `i32`.
2. **Problem 2: Euclidean 3D Vector Norm** ($\sqrt{X^2 + Y^2 + Z^2}$) in `f32`.
3. **Problem 3: Volume of a Sphere** ($V = \frac{4}{3} \pi r^3$) in `f32` (using `PUSH_PI_32`).
4. **Problem 4: Polynomial Evaluation** ($y = A x^2 + B x + C$) in `f32` using User Storage Slots (`CP [xxxx], TOS`).

---

### 6.1 Problem 1: Manhattan Distance (`i32`)

$$D = |X_1 - X_2| + |Y_1 - Y_2|$$

#### Stack Flow (RPN):
1. Push $X_1$, push $X_2$
2. Execute `SUB_I32` $\rightarrow (X_1 - X_2)$
3. Execute `ABS_I32` $\rightarrow |X_1 - X_2|$
4. Push $Y_1$, push $Y_2$
5. Execute `SUB_I32` $\rightarrow (Y_1 - Y_2)$
6. Execute `ABS_I32` $\rightarrow |Y_1 - Y_2|$
7. Execute `ADD_I32` $\rightarrow |X_1 - X_2| + |Y_1 - Y_2|$
8. Pop 4-byte result

#### Implementation A: Immediate Blocking Mode
```z80
; ==============================================================================
; Manhattan_Distance_i32 (Immediate Blocking Mode)
; Inputs:  HL -> pointer to {X1, X2, Y1, Y2} (each 4 bytes, little-endian)
;          DE -> pointer to 4-byte buffer for result D
; ==============================================================================
Manhattan_Distance_i32:
    ; 1. Push X1 (4 bytes)
    LD   B, 4
    LD   C, 0x70
    OTIR                    ; Push X1

    ; 2. Push X2 (4 bytes)
    LD   B, 4
    OTIR                    ; Push X2

    ; 3. Execute SUB_I32 (0x08) then ABS_I32 (0x58)
    LD   A, 0x08            ; SUB_I32
    OUT  (0x71), A          ; Z80 waits until SUB completes
    LD   A, 0x58            ; ABS_I32
    OUT  (0x71), A          ; Z80 waits until ABS completes

    ; 4. Push Y1 (4 bytes)
    LD   B, 4
    OTIR                    ; Push Y1

    ; 5. Push Y2 (4 bytes)
    LD   B, 4
    OTIR                    ; Push Y2

    ; 6. Execute SUB_I32 (0x08) then ABS_I32 (0x58)
    LD   A, 0x08            ; SUB_I32
    OUT  (0x71), A
    LD   A, 0x58            ; ABS_I32
    OUT  (0x71), A

    ; 7. Execute ADD_I32 (0x00)
    XOR  A                  ; ADD_I32 = 0x00
    OUT  (0x71), A

    ; 8. Pop 4-byte Result into [DE]
    EX   DE, HL             ; HL -> destination
    LD   B, 4
    LD   C, 0x70
    INIR                    ; Pop result LSB to MSB
    RET
```

---

### 6.2 Problem 2: Euclidean 3D Vector Norm (`f32`)

$$D = \sqrt{X^2 + Y^2 + Z^2}$$

#### Stack Flow (RPN):
1. Push $X$, `DUP4`, `MUL_F32` $\rightarrow X^2$
2. Push $Y$, `DUP4`, `MUL_F32` $\rightarrow Y^2$
3. `ADD_F32` $\rightarrow X^2 + Y^2$
4. Push $Z$, `DUP4`, `MUL_F32` $\rightarrow Z^2$
5. `ADD_F32` $\rightarrow X^2 + Y^2 + Z^2$
6. `SQRT_F32` $\rightarrow \sqrt{X^2 + Y^2 + Z^2}$

#### Implementation C: Batch Queuing Mode
In batch mode, we stream the entire opcode sequence in a single burst:

```z80
; ==============================================================================
; Vector3D_Norm_Batch
; Inputs:  HL -> pointer to {X, Y, Z} (12 bytes total, IEEE-754 f32)
;          DE -> pointer to 4-byte buffer for result
; ==============================================================================
Vector3D_Norm_Batch:
    ; 1. Enter Batch Mode
    LD   A, 0xFB            ; SET_BATCH
    OUT  (0x71), A

    ; 2. Queue OpCodes for: DUP4, MUL_F32, (push Y happens), DUP4, MUL_F32, ADD_F32...
    ; We push X, Y, Z to the operand stack, and queue the math ops
    LD   B, 4
    LD   C, 0x70
    OTIR                    ; Push X
    LD   A, 0xC0            ; DUP4
    OUT  (0x71), A
    LD   A, 0x11            ; MUL_F32
    OUT  (0x71), A

    LD   B, 4
    OTIR                    ; Push Y
    LD   A, 0xC0            ; DUP4
    OUT  (0x71), A
    LD   A, 0x11            ; MUL_F32
    OUT  (0x71), A
    LD   A, 0x01            ; ADD_F32
    OUT  (0x71), A

    LD   B, 4
    OTIR                    ; Push Z
    LD   A, 0xC0            ; DUP4
    OUT  (0x71), A
    LD   A, 0x11            ; MUL_F32
    OUT  (0x71), A
    LD   A, 0x01            ; ADD_F32
    OUT  (0x71), A
    LD   A, 0x21            ; SQRT_F32
    OUT  (0x71), A

    ; 3. Execute the entire batch at 80 MHz in one shot!
    LD   A, 0xFA            ; EXEC_BATCH
    OUT  (0x71), A          ; Coprocessor asserts ~WAIT until batch finishes

    ; 4. Pop 4-byte Result
    EX   DE, HL
    LD   B, 4
    LD   C, 0x70
    INIR                    ; Pop 4-byte result to [DE]

    ; 5. Restore Immediate Mode
    LD   A, 0xFC            ; SET_IMMEDIATE
    OUT  (0x71), A
    RET
```

---

### 6.3 Problem 3: Volume of a Sphere (`f32`)

$$V = \frac{4}{3} \pi r^3 = \frac{4}{3} \times \pi \times r \times r \times r$$

#### Stack Flow (RPN):
1. Push radius $r$
2. `DUP4` (now two copies of $r$ on stack)
3. `DUP4` (now three copies of $r$ on stack)
4. `MUL_F32` $\rightarrow r^2$
5. `MUL_F32` $\rightarrow r^3$
6. `PUSH_PI_32` (`0xA0`) $\rightarrow$ pushes $\pi$ directly from ROM
7. `MUL_F32` $\rightarrow \pi r^3$
8. Push constant $4.0$ (`0x40800000`)
9. `MUL_F32` $\rightarrow 4 \pi r^3$
10. Push constant $3.0$ (`0x40400000`)
11. `DIV_F32` $\rightarrow \frac{4}{3} \pi r^3$

#### Implementation: Immediate Blocking Mode
```z80
; ==============================================================================
; Sphere_Volume_f32
; Inputs:  HL -> pointer to 4-byte radius r (IEEE-754 f32)
;          DE -> pointer to 4-byte destination for Volume V
; ==============================================================================
Sphere_Volume_f32:
    ; 1. Push radius r to stack
    LD   B, 4
    LD   C, 0x70
    OTIR

    ; 2. Duplicate r twice to create 3 copies on stack
    LD   A, 0xC0            ; DUP4
    OUT  (0x71), A
    OUT  (0x71), A

    ; 3. Compute r^3
    LD   A, 0x11            ; MUL_F32
    OUT  (0x71), A          ; r * r = r^2
    OUT  (0x71), A          ; r^2 * r = r^3

    ; 4. Multiply by Pi (using on-chip constant ROM)
    LD   A, 0xA0            ; PUSH_PI_32
    OUT  (0x71), A          ; Pushes Pi to TOS
    LD   A, 0x11            ; MUL_F32
    OUT  (0x71), A          ; Pi * r^3

    ; 5. Multiply by 4.0 (0x40800000)
    LD   HL, Const_4_0
    LD   B, 4
    LD   C, 0x70
    OTIR
    LD   A, 0x11            ; MUL_F32
    OUT  (0x71), A          ; 4 * Pi * r^3

    ; 6. Divide by 3.0 (0x40400000)
    LD   HL, Const_3_0
    LD   B, 4
    LD   C, 0x70
    OTIR
    LD   A, 0x19            ; DIV_F32
    OUT  (0x71), A          ; (4 * Pi * r^3) / 3.0

    ; 7. Pop 4-byte volume result into [DE]
    EX   DE, HL
    LD   B, 4
    LD   C, 0x70
    INIR
    RET

Const_4_0:  DB  0x00, 0x00, 0x80, 0x40  ; 4.0f in Little-Endian
Const_3_0:  DB  0x00, 0x00, 0x40, 0x40  ; 3.0f in Little-Endian
```

---

### 6.4 Problem 4: Quadratic Polynomial Evaluation (`f32`)

$$y = A x^2 + B x + C = (A x + B) x + C \quad \text{(Horner's Rule)}$$

Using **User Storage Memory** slot `[0]` to hold $x$ avoids pushing $x$ repeatedly over the Z80 bus.

#### Stack Flow (RPN with User Storage):
1. Push $x$, execute `CP [0], TOS` (stashes $x$ in user slot 0 without removing it from stack)
2. Push $A$, `MUL_F32` $\rightarrow A x$
3. Push $B$, `ADD_F32` $\rightarrow A x + B$
4. Execute `CP TOS, [0]` (pushes cached $x$ back onto stack)
5. `MUL_F32` $\rightarrow (A x + B) x$
6. Push $C$, `ADD_F32` $\rightarrow (A x + B) x + C$
7. Pop 4-byte result $y$

#### Implementation: Immediate Blocking with User Storage
```z80
; ==============================================================================
; Eval_Quadratic_f32
; Inputs:  HL -> pointer to {x, A, B, C} (16 bytes total, IEEE-754 f32)
;          DE -> pointer to 4-byte buffer for result y
; ==============================================================================
Eval_Quadratic_f32:
    ; 1. Push x (4 bytes)
    LD   B, 4
    LD   C, 0x70
    OTIR

    ; 2. Stash x into internal user storage slot 0: CP [0], TOS (0xD0)
    LD   A, 0xD0            ; CP [0], TOS
    OUT  (0x71), A

    ; 3. Push A (4 bytes)
    LD   B, 4
    OTIR

    ; 4. Compute A * x
    LD   A, 0x11            ; MUL_F32
    OUT  (0x71), A

    ; 5. Push B (4 bytes)
    LD   B, 4
    OTIR

    ; 6. Compute (A * x) + B
    LD   A, 0x01            ; ADD_F32
    OUT  (0x71), A

    ; 7. Reload cached x from user slot 0: CP TOS, [0] (0xE0)
    LD   A, 0xE0            ; CP TOS, [0]
    OUT  (0x71), A

    ; 8. Compute ((A * x) + B) * x
    LD   A, 0x11            ; MUL_F32
    OUT  (0x71), A

    ; 9. Push C (4 bytes)
    LD   B, 4
    OTIR

    ; 10. Compute final sum: ((A * x) + B) * x + C
    LD   A, 0x01            ; ADD_F32
    OUT  (0x71), A

    ; 11. Pop 4-byte result into [DE]
    EX   DE, HL
    LD   B, 4
    LD   C, 0x70
    INIR
    RET
```
