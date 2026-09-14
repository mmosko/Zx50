# Zx50 Am9511/Am9512 CPLD Math Coprocessor Architecture Specification

## 1. System Signal & Pin Mapping

The ATF1508AS CPLD (`U8`) bridges the Z80 backplane, dedicated stack SRAM (`U9`), and on-board memory chips (`U10`
SRAM0, `U11` SRAM1, `U12` Flash ROM)[cite: 1].

### Z80 Backplane Interface (`J1` / `U1` / `U4` / `U5`)[cite: 1]

* **Address Inputs:** `Z80_A[15:0]` (`U8` pins 1, 2, 5–10, 12–14, 16, 17, 19–21)[cite: 1].
* **Data Bus (Buffered):** `L_D[7:0]` (`U8` pins 24, 25, 27–32) connects to local bus `B.D[7:0]`[cite: 1].
* **Bus Control Outputs:**
    * `Z80_DATA_OE_n` (pin 23) drives `~Z80_D_OE` (`U4` pin 19)[cite: 1]. Set HIGH to isolate local data bus `B.D[7:0]`
      from backplane during calculation[cite: 1].
    * `L_DIR` (pin 22) controls `U4` direction (`DIR`)[cite: 1].
* **Z80 Control Inputs:** `Z80_RD_n` (33), `Z80_WR_n` (35), `Z80_MREQ_n` (37), `Z80_IORQ_n` (40), `Z80_M1_n` (41),
  `RESET_n` (89), `MCLK` (87, 40 MHz clock)[cite: 1].
* **Handshake Signals:** `Z80_WAIT_n` (pin 97, open-drain output to freeze CPU), `Z80_INT_n` (pin 96)[cite: 1].

### Dedicated Stack SRAM (`U9` - ISSI IS61C256)[cite: 1]

* **Dedicated Address Lines:** `ATL_A[4:0]` (`U8` pins 53–57) $\rightarrow$ 32-byte direct addressing[cite: 1].
* **Multiplexed Data/Address Lines:** `ATL_D[7:0]` (`U8` pins 58, 60, 61, 63, 64, 65, 67, 68)[cite: 1].
* **SRAM Control Outputs:** `ATL_CE_n` (71), `ATL_OE_n` (70), `ATL_WE_n` (69)[cite: 1].

### Main Board Memory (`U10` SRAM0, `U11` SRAM1, `U12` Flash ROM)[cite: 1]

* **Lower Address Lines:** `L_A[10:0]` (`U8` pins 72, 75–81, 83–85) drive `A[10:0]` on `U10`, `U11`, `U12`[cite: 1].
* **Upper Address Lines:** `A[18:11]` on `U10`, `U11`, `U12` are tied directly to `ATL_D[7:0]`[cite: 1].
* **Chip Enables:** `IO99` (`~CE0`, pin 99 $\rightarrow$ `U10`), `RAM_CE1_n` (`~CE1`, pin 92 $\rightarrow$ `U11`),
  `ROM_C2` (`~CE2`, pin 98 $\rightarrow$ `U12`)[cite: 1].
* **Read/Write Controls:** `RAM_OE_n` (93), `RAM_WE_n` (94)[cite: 1].

---

## 2. Bus Multiplexing & Bus Isolation Architecture

```
                       +-------------------------------+
                       |  Z80 Backplane Data Bus       |
                       +-------------------------------+
                                       |
                                  [U4 74ABT245]  <-- ~Z80_D_OE (Pin 23)
                                       |
 +-------------------------------------+-------------------------------------+
 | Local Bus B.D[7:0]                                                        |
 |    |                                |                                |    |
 | [U10 SRAM0]                   [U11 SRAM1]                      [U12 ROM]  |
 |    | A                       | A                       | A
 |    +--------------------------------+--------------------------------+    |
 |                                     |                                     |
 |                            +-----------------+                            |
 |                            |  ATL_D[7:0] Bus |                            |
 |                            +-----------------+                            |
 |                               ^           ^                               |
 |              Stack Data Bus   |           |  Direct Upper Address A|
 |                               v           v                               |
 |                         [U9 Stack SRAM]   |                               |
 |                       ATL_A[4:0] (5 Pins) |                               |
 |                               ^           |                               |
 +-------------------------------+-----------+-------------------------------+
                                 |           |
                           +-----------------------+
                           | ATF1508AS CPLD (U8)   |
                           | Direct ATL_D[7:0] Pin |
                           | Connection to A|
                           +-----------------------+
```

### Mode 1: Standard Memory Pass-Through Mode

* **Condition:** Normal Z80 memory read/write cycles (`Z80_MREQ_n` = 0)[cite: 1].
* **Transceiver (`U4`):** `Z80_DATA_OE_n` = 0 (enabled), `L_DIR` controlled by `Z80_RD_n`[cite: 1].
* **Lower Address (`A[10:0]`):** `L_A[10:0]` driven by CPLD from `Z80_A[10:0]`[cite: 1].
* **Upper Address (`A[18:11]`):** CPLD directly drives `A[18:11]` via `ATL_D[7:0]` using pass-through `Z80_A[18:11]`
  values while keeping `ATL_OE_n` = 1 (disabling `U9` stack SRAM output drivers)[cite: 1].
* **Chip Selects:** Decodes `Z80_A[18:11]` to assert one of `RAM_CE0_n`, `RAM_CE1_n`, or `ROM_C2`[cite: 1].

### Mode 2: Autonomous Math Execution & Local Bus Isolation

* **Condition:** Math Opcode received on I/O write[cite: 1].
* **Transceiver (`U4`):** `Z80_DATA_OE_n` = 1 (High-Z). Backplane isolated from card local bus `B.D[7:0]`[cite: 1].
* **CPU Hold:** `Z80_WAIT_n` pulled LOW to stall Z80 execution during local math execution[cite: 1].
* **Private Stack Operations (`U9`):** `ATL_A[4:0]` driven by internal CPLD 5-bit Stack Pointer counter
  ($0\dots 31$)[cite: 1]. `ATL_D[7:0]` operates as a bidirectional stack data bus directly between CPLD shift registers
  and `U9`[cite: 1].
* **Direct Upper Memory Address Driving (`A[18:11]`):** The `ATL_D[7:0]` pins on the CPLD connect **directly** to
  `A[18:11]` of `U10`, `U11`, and `U12`[cite: 1]. During internal execution, the CPLD synthesizes and drives upper
  memory addresses directly without requiring external latches.
* **Internal Table Lookup (`U11`/`U12` Read):**
    * `ATL_OE_n` = 1 (disables `U9` stack RAM output drivers to prevent bus contention)[cite: 1].
    * CPLD directly outputs the lookup table page address onto `A[18:11]` (via `ATL_D[7:0]`) and the table entry index
      onto `L_A[10:0]`[cite: 1].
    * CPLD reads lookup constants directly off `B.D[7:0]` into internal math registers[cite: 1].

---

## 3. Register & I/O Interface

The CPLD decodes base port `0x70` (or `0x71` selected via DIP switch `SW1`)[cite: 1].

| Port Address | Operation | Register Name | Description                                                                       |
|:------------:|:---------:|:-------------:|:----------------------------------------------------------------------------------|
|  **`0x70`**  |   Write   |  `DATA_PUSH`  | Pushes 1 byte to Top of Stack ($TOS$), auto-incrementing stack byte pointer.      |
|  **`0x70`**  |   Read    |  `DATA_POP`   | Reads 1 byte from Top of Stack ($TOS$), auto-decrementing stack byte pointer.     |
|  **`0x71`**  |   Write   |  `CMD_EXEC`   | Writes opcode to execution FSM, asserts `/WAIT`, and begins calculation[cite: 1]. |
|  **`0x71`**  |   Read    |   `STATUS`    | Returns status flags: `[BUSY, ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW, ERR, 0]`.   |

---

## 4. Stack Memory Architecture (32 Bytes in `U9`)

The 5-bit address bus `ATL_A[4:0]` maps 32 contiguous bytes in `U9`[cite: 1]. The pointer is managed by an up/down
counter in the CPLD.

```
       32-Bit Single Precision Stack                64-Bit Double / Complex Stack
   +------------------------------------+       +------------------------------------+
0x00| TOS  (Top of Stack) - Byte 0 (LSB) |   0x00| TOS  (Top of Stack) - Byte 0 (LSB) |
0x01| TOS                 - Byte 1     |   0x01| TOS                 - Byte 1     |
0x02| TOS                 - Byte 2     |   0x02| TOS                 - Byte 2     |
0x03| TOS                 - Byte 3 (MSB)|   ... | ...                                |
   +------------------------------------+   0x07| TOS                 - Byte 7 (MSB)|
0x04| NOS  (Next on Stack)- Byte 0      |       +------------------------------------+
... | ...                                |   0x08| NOS  (Next on Stack)- Byte 0      |
0x07| NOS                 - Byte 3      |   ... | ...                                |
   +------------------------------------+   0x0F| NOS                 - Byte 7      |
0x08| Stack Level 2                      |       +------------------------------------+
... | ...                                |   0x10| Stack Level 2                      |
0x1F| Stack Level 7 (8 Levels Max)     |   0x1F| Stack Level 3 (4 Levels Max)       |
   +------------------------------------+       +------------------------------------+
```

---

## 5. Binary Formats & Matrix Opcode Decoding

### Field Extraction Architecture

Opcodes written to Port `0x71` are split directly into bitfields:

* `format = opcode[7:4]` (High Nibble)
* `operation = opcode[3:0]` (Low Nibble)

```verilog
wire [3:0] fmt = opcode[7:4];
wire [3:0] op  = opcode[3:0];
```

### Format Field (`opcode[7:4]`)

| Value | Identifier |            Data Type            |      Size / Operand       | Stack Stride  |
|:-----:|:----------:|:-------------------------------:|:-------------------------:|:-------------:|
| `0x0` |   `i16`    |      16-Bit Signed Integer      |          2 Bytes          | $\pm 2$ Bytes |
| `0x1` |   `i32`    |      32-Bit Signed Integer      |          4 Bytes          | $\pm 4$ Bytes |
| `0x2` |   `i64`    |      64-Bit Signed Integer      |          8 Bytes          | $\pm 8$ Bytes |
| `0x3` |  `float`   |      32-Bit IEEE-754 Float      |          4 Bytes          | $\pm 4$ Bytes |
| `0x4` |  `dfloat`  |      64-Bit IEEE-754 Float      |          8 Bytes          | $\pm 8$ Bytes |
| `0x5` |  `cfloat`  | 32-Bit Complex Float ($a + bi$) | 8 Bytes (4 Real + 4 Imag) | $\pm 8$ Bytes |
| `0xE` | `special`  |      Reserved / Extensions      |          Custom           |    Custom     |
| `0xF` |   `mgmt`   |   Hardware / Stack Management   |          0 Bytes          |     None      |

### Operation Field (`opcode[3:0]`) Matrix

|  Op Value   |  Mnemonic  | Supported Formats | Description                                       |   Latency (40 MHz)   |
|:-----------:|:----------:|:-----------------:|:--------------------------------------------------|:--------------------:|
|    `0x0`    |   `ADD`    |    `0x0`–`0x5`    | Addition ($TOS = NOS + TOS$)                      |   160 ns – 650 ns    |
|    `0x1`    |   `SUB`    |    `0x0`–`0x5`    | Subtraction ($TOS = NOS - TOS$)                   |   160 ns – 650 ns    |
|    `0x2`    |   `MUL`    |    `0x0`–`0x5`    | Multiplication ($TOS = NOS \times TOS$)           | 400 ns – 1.60 $\mu$s |
|    `0x3`    |   `DIV`    |    `0x0`–`0x5`    | Division ($TOS = NOS / TOS$)                      | 420 ns – 1.68 $\mu$s |
|    `0x4`    |   `SQRT`   |    `0x0`–`0x4`    | Square Root ($\sqrt{TOS}$)                        | 400 ns – 1.33 $\mu$s |
|    `0x5`    |   `CHS`    |    `0x0`–`0x5`    | Change Sign / Negate ($TOS = -TOS$)               |        25 ns         |
|    `0x6`    |   `SIN`    |       `0x3`       | Sine ($\sin(TOS)$ via Table + Interp MAC)         |     1.10 $\mu$s      |
|    `0x7`    |   `COS`    |       `0x3`       | Cosine ($\cos(TOS)$ via Table + Interp MAC)       |     1.10 $\mu$s      |
|    `0x8`    |   `EXP`    |       `0x3`       | Exponential ($e^{TOS}$ via Table + Interp)        |     1.20 $\mu$s      |
|    `0x9`    |    `LN`    |       `0x3`       | Natural Logarithm ($\ln(TOS)$ via Table + Interp) |     1.25 $\mu$s      |
|    `0xA`    |  `LOG10`   |       `0x3`       | Base-10 Logarithm ($\log_{10}(TOS)$ via Table)    |     1.25 $\mu$s      |
| `0xB`–`0xE` | `RESERVED` |         —         | Unused                                            |          —           |

### Management Opcodes (`Format = 0xF`)

| Full Opcode | Mnemonic  | Description                                                    | Latency |
|:-----------:|:---------:|:---------------------------------------------------------------|:-------:|
| **`0xF0`**  | `CLR_STK` | Clears Stack Pointer counter (`ATL_A[4:0] = 0x00`)             |  25 ns  |
| **`0xF1`**  | `POP_TOS` | Drops $TOS$ without computing (decrements SP by active stride) |  25 ns  |
| **`0xF2`**  | `DUP_TOS` | Duplicates $TOS$ entry on stack                                | 100 ns  |
| **`0xFF`**  |  `RESET`  | Soft reset math state machine and clear status flags           |  25 ns  |

---

## 6. Execution FSM State Machine Logic

```
                    +--------------------+
                    |     ST_IDLE        |
                    +--------------------+
                              |
                     Opcode Write (0x71)
                              |
                              v
                    +--------------------+
                    |     ST_ISOLATE     |  Z80_DATA_OE_n <= 1
                    +--------------------+  Z80_WAIT_n    <= 0
                              |
                              v
                    +--------------------+
                    |     ST_ALIGN       |  If Float: Align exponents, fetch operands
                    +--------------------+  If Int: Bypass exponent logic, load shifters
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
   +--------------------+            +--------------------+
   |   ST_BIT_SERIAL    |            |   ST_TABLE_FETCH   |
   | (ADD/SUB/MUL/DIV)  |            |   (Transcendental) |
   +--------------------+            +--------------------+
   | 16/24/32/53/64     |            | Fetch Y0, Y1 from  |
   | Clock Steps        |            | U11/U12 local RAM  |
   +--------------------+            +--------------------+
             |                                 |
             +----------------+----------------+
                              |
                              v
                    +--------------------+
                    |    ST_NORMALIZE    |  If Float: Normalize result mantissa
                    +--------------------+  If Int: Pass-through raw accumulator
                              |
                              v
                    +--------------------+
                    |    ST_WRITEBACK    |  Write result back to U9 TOS;
                    +--------------------+  Update SP pointer by byte stride
                              |
                              v
                    +--------------------+
                    |     ST_RELEASE     |  Z80_DATA_OE_n <= 0
                    +--------------------+  Z80_WAIT_n    <= 1 (Z80 Resumes)
```

### Detailed FSM Sequence

1. **`ST_IDLE`:** CPLD listens on I/O ports. Transceiver enabled (`Z80_DATA_OE_n` = 0)[cite: 1].
2. **`ST_ISOLATE`:** Triggered by write to port `0x71`[cite: 1]. `Z80_WAIT_n` pulled LOW to stall Z80[cite: 1].
   `Z80_DATA_OE_n` set to 1 to isolate backplane[cite: 1].
3. **`ST_ALIGN`:** Extract `fmt = opcode[7:4]`. For floating-point formats (`0x3`, `0x4`, `0x5`), CPLD reads exponents
   of $TOS$ and $NOS$ from `U9` into internal counters to compute mantissa alignment shifts[cite: 1]. For integer
   formats (`0x0`, `0x1`, `0x2`), exponent alignment is bypassed.
4. **`ST_BIT_SERIAL` / `ST_TABLE_FETCH`:**
    * **Arithmetic:** Execute 16-cycle (`i16`), 24-cycle (`float`), 32-cycle (`i32`), 53-cycle (`dfloat`), or 64-cycle
      (`i64`) bit-serial accumulator loops at 40 MHz clock.
    * **Complex (`cfloat`):** Executes dual 32-bit float arithmetic passes for Real and Imaginary components
      ($a+bi, c+di$).
    * **Transcendental:** Drive `ATL_D[7:0]` with upper 8 bits of mantissa (table page) and `L_A[10:0]` with mid 11
      bits[cite: 1]. Read $Y_0$ and $Y_1$ directly from local memory into shift registers, then perform interpolation
      multiply-add.
5. **`ST_NORMALIZE`:** For floating-point results, check leading bit of mantissa, shift, and adjust exponent register.
   Check for overflow/underflow. Integer results skip normalization.
6. **`ST_WRITEBACK`:** Write byte sequence back to $TOS$ in `U9` via `ATL_A[4:0]` and update Stack Pointer according to
   the format's byte stride ($\pm 2, \pm 4, \text{ or } \pm 8$)[cite: 1].
7. **`ST_RELEASE`:** Re-enable backplane transceivers (`Z80_DATA_OE_n` = 0) and release `/WAIT` line (`Z80_WAIT_n` =
   1)[cite: 1]. Z80 resumes execution seamlessly.