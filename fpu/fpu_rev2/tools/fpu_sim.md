# ZX50 FPU Microcode Engine Hardware Reference Manual

## 1. Machine Architecture

The ZX50 Floating-Point Unit (FPU) coprocessor is a microcoded math execution engine built around an Atmel/Microchip
ATF1508AS CPLD. It operates on a dedicated 32 KB private memory bus (`CA[14:0]`, `CD[7:0]`) containing 32 KB High-Speed
Static RAM (`U12`) and 32 KB NOR Flash ROM (`U13`).

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
|  | - Read SRAM (TOS/NOS)| | - Add / Sub / Abs   |   | - ACC  (8-bit Accumulator)     |  |
|  | - Read Flash LUT   |   | - Shift Right / Left|   | - OPB  (8-bit Sec Operand)      |  |
|  | - Write SRAM       |   | - Swap / Pass       |   | - TMP0 (16-bit Scratch Pad 0)  |  |
|  +---------+----------+   +----------+----------+   | - TMP1 (16-bit Scratch Pad 1)  |  |
|            |                         |              +---------------+----------------+  |
|            +-------------------------+------------------------------+                   |
+-----------------------------------------------------------------------------------------+

```

### 1.1 CPLD Internal Register File

The CPLD hardware register file is strictly constrained by macrocell limits (128 macrocells total).

| Register Name     | Bit Width | Hardware Purpose / Functional Role                                                                                  |
|-------------------|-----------|---------------------------------------------------------------------------------------------------------------------|
| **`ACC`**         | 8 bits    | Primary Accumulator. Holds 8-bit operands, Flash table query keys, or low-byte math results.                        |
| **`OPB`**         | 8 bits    | Operand B Register. Holds secondary 8-bit operands or intermediate byte sums.                                       |
| **`TMP0`**        | 16 bits   | Scratchpad Register 0. Holds 16-bit sum results ($A+B$), Flash addresses, or partial products.                      |
| **`TMP1`**        | 16 bits   | Scratchpad Register 1. Holds 16-bit difference results ($\vert{}A-B\vert{}$), Flash table data, or partial carries. |
| **`SP`**          | 8 bits    | Hardware Stack Pointer. Points to the base of the active stack frame in SRAM.                                       |
| **`BYTE_CNT`**    | 2/3 bits  | Auto-incrementing byte counter offset (`0`..`3` or `0`..`7`) used during memory transfers.                          |
| **`U_PC`**        | 7 bits    | Microcode Program Counter. Pointers to the active microcode step in the sequence table.                             |
| **`CARRY_LATCH`** | 1 bit     | Preserves carry/borrow bits across multi-byte serial ALU iterations.                                                |

### 1.2 Status Flags

* **`BUSY` (Bit 7):** Asserted high during microcode execution; cleared automatically upon `SEQ_DONE`.


* **`ZERO` (Bit 1):** Set if the last ALU output evaluates to zero.
* **`SIGN` (Bit 2):** Reflects the most significant bit (MSB) of the last ALU result.
* **`CARRY` (Bit 3):** Holds the carry-out or borrow-out status of the last ALU cycle.
* **`ERR` (Bit 6):** Set high if an illegal opcode, division-by-zero, or math domain error occurs.

### 1.3 Memory Spaces

1. **Private SRAM (`32 KB` / `U12`):**

* **Scratchpad Region (`0x0000`–`0x0007`):** 8 bytes reserved for intermediate partial products, multi-byte carries, and
  operand stashing.

* **Math Stack Region (`0x0008`–`0x00FF`):** Managed relative to the Stack Pointer ($SP$).

* **Top of Stack (TOS):** Occupies $SP - 4$ through $SP - 1$ (4 bytes, Little-Endian).

* **Next on Stack (NOS):** Occupies $SP - 8$ through $SP - 5$ (4 bytes, Little-Endian).

2. **Private Flash ROM (`32 KB` / `U13`):**
   Stores pre-calculated lookup tables (LUTs) for high-speed mathematical acceleration:

| Lookup Table Name      | Base Address | Entry Size          | Function / Formula                                                                       |
|------------------------|--------------|---------------------|------------------------------------------------------------------------------------------|
| **`FLASH_QS_BASE`**    | `0x0000`     | 511 $\times$ 16-bit | Quarter-Square Table: $f(n) = \lfloor n^2 / 4 \rfloor$ for $n \in [0..510]$<br>          |
| **`FLASH_RECIP_BASE`** | `0x0400`     | 256 $\times$ 16-bit | Reciprocal Table: $f(x) = \lceil 65536 / x \rceil$ for $x \in [1..255]$<br>              |
| **`FLASH_SQRT_BASE`**  | `0x0600`     | 256 $\times$ 16-bit | Square Root Table: $f(x) = \sqrt{x} \times 256$ for $x \in [0..255]$<br>                 |
| **`FLASH_EXP2_BASE`**  | `0x0800`     | 256 $\times$ 16-bit | Base-2 Exponential: $f(x) = 2^{x/256} \times 256$ for $x \in [0..255]$<br>               |
| **`FLASH_LOG2_BASE`**  | `0x0A00`     | 256 $\times$ 16-bit | Base-2 Logarithm: $f(x) = \log_2(1 + x/256) \times 256$<br>                              |
| **`FLASH_SIN_BASE`**   | `0x0C00`     | 256 $\times$ 16-bit | Sine Table ($0^\circ$ to $90^\circ$): $f(x) = \sin(x/256 \cdot \pi/2) \times 256$<br>    |
| **`FLASH_COS_BASE`**   | `0x0E00`     | 256 $\times$ 16-bit | Cosine Table ($0^\circ$ to $90^\circ$): $f(x) = \cos(x/256 \cdot \pi/2) \times 256$<br>  |
| **`FLASH_TAN_BASE`**   | `0x1000`     | 256 $\times$ 16-bit | Tangent Table ($0^\circ$ to $45^\circ$): $f(x) = \tan(x/256 \cdot \pi/4) \times 256$<br> |
| **`FLASH_LN_BASE`**    | `0x1200`     | 256 $\times$ 16-bit | Natural Logarithm: $f(x) = \ln(1 + x/256) \times 256$<br>                                |
| **`FLASH_LOG10_BASE`** | `0x1400`     | 256 $\times$ 16-bit | Base-10 Logarithm: $f(x) = \log_{10}(1 + x/256) \times 256$<br>                          |

---

## 2. ALU Operations and Side Effects

The ALU core (`alu_core`) is a 16-bit combinational arithmetic unit. Inputs are selected via multiplexers `SRC_X` and
`SRC_Y`.

### 2.1 Datapath Source Mux Encodings (`SRC_X` / `SRC_Y`)

| Encoding | Mnemonic   | Selected Data Source           | Width   | Zero-Extension Behavior              |
|----------|------------|--------------------------------|---------|--------------------------------------|
| `2'b00`  | `MUX_ACC`  | Accumulator Register (`ACC`)   | 8 bits  | Zero-extended to 16 bits (`0x00ACC`) |
| `2'b01`  | `MUX_OPB`  | Secondary Operand (`OPB`)      | 8 bits  | Zero-extended to 16 bits (`0x00OPB`) |
| `2'b10`  | `MUX_TMP0` | Scratchpad Register 0 (`TMP0`) | 16 bits | Full 16-bit passthrough              |
| `2'b11`  | `MUX_TMP1` | Scratchpad Register 1 (`TMP1`) | 16 bits | Full 16-bit passthrough              |

*Note:* An operation is evaluated in **8-bit mode** (`is_8bit = True`) if and only if both `SRC_X` and `SRC_Y` are 8-bit
registers (`ACC` or `OPB`). Otherwise, it executes in **16-bit mode**.

### 2.2 ALU Function Codes (`ALU_OP`)

| Code     | Mnemonic         | Mathematical Operation                            | Carry Latch Side Effect                           | Zero/Sign Flag Behavior          |
|----------|------------------|---------------------------------------------------|---------------------------------------------------|----------------------------------|
| `3'b000` | `ALU_PASS_X`     | $\text{OUT} = X$                                  | Preserves existing `CARRY_LATCH`<br>              | Set based on output $X$<br>      |
| `3'b001` | `ALU_ADD`        | $\text{OUT} = X + Y + \text{CARRY\_LATCH}$        | Sets `CARRY_LATCH` = 1 if result overflows limits | Set based on output sum          |
| `3'b010` | `ALU_SUB`        | $\text{OUT} = X - Y - \text{CARRY\_LATCH}$        | Sets `CARRY_LATCH` = 1 if result borrows ($< 0$)  | Set based on output difference   |
| `3'b011` | `ALU_ABS_DIFF`   | $\text{OUT} = \vert{}X - Y\vert{}$                | Clears `CARRY_LATCH` = 0                          | Set based on absolute difference |
| `3'b100` | `ALU_SHL`        | $\text{OUT} = (X \ll 1) \mid \text{CARRY\_LATCH}$ | Sets `CARRY_LATCH` = MSB of $X$ prior to shift    | Set based on shifted output      |
| `3'b101` | `ALU_SHR`        | $\text{OUT} = X \gg 1$                            | Sets `CARRY_LATCH` = LSB of $X$ prior to shift    | Set based on shifted output      |
| `3'b110` | `ALU_SWAP_BYTES` | $\text{OUT} = \{X[7:0], X[15:8]\}$                | Clears `CARRY_LATCH` = 0                          | Set based on byte-swapped word   |
| `3'b111` | `ALU_PASS_ZERO`  | $\text{OUT} = 16'\text{h}0000$                    | Clears `CARRY_LATCH` = 0                          | `ZERO` = 1, `SIGN` = 0           |

### 2.3 Register Load Operations (`REG_LD`)

`REG_LD` controls which register latches data during the clock cycle. Data is sourced either from the Memory Read Bus
(if `MEM_CMD` is a read command) or directly from the ALU output bus.

| Code      | Mnemonic     | Target Register | Data Source           | Splicing & Side Effects                       |
|-----------|--------------|-----------------|-----------------------|-----------------------------------------------|
| `4'b0000` | `LD_NONE`    | None            | None                  | No register update.                           |
| `4'b0001` | `LD_ACC`     | `ACC`           | Mem / `ALU_OUT[7:0]`  | Overwrites 8-bit `ACC`.                       |
| `4'b0010` | `LD_OPB`     | `OPB`           | Mem / `ALU_OUT[7:0]`  | Overwrites 8-bit `OPB`.                       |
| `4'b0011` | `LD_TMP0`    | `TMP0`          | `ALU_OUT[15:0]`       | Overwrites full 16-bit `TMP0`.                |
| `4'b0100` | `LD_TMP1`    | `TMP1`          | `ALU_OUT[15:0]`       | Overwrites full 16-bit `TMP1`.                |
| `4'b0101` | `LD_TMP0_LO` | `TMP0[7:0]`     | Mem / `ALU_OUT[7:0]`  | Replaces `TMP0[7:0]`; preserves `TMP0[15:8]`. |
| `4'b0110` | `LD_TMP0_HI` | `TMP0[15:8]`    | Mem / `ALU_OUT[15:8]` | Replaces `TMP0[15:8]`; preserves `TMP0[7:0]`. |
| `4'b0111` | `LD_TMP1_LO` | `TMP1[7:0]`     | Mem / `ALU_OUT[7:0]`  | Replaces `TMP1[7:0]`; preserves `TMP1[15:8]`. |
| `4'b1000` | `LD_TMP1_HI` | `TMP1[15:8]`    | Mem / `ALU_OUT[15:8]` | Replaces `TMP1[15:8]`; preserves `TMP1[7:0]`. |

---

## 3. Memory (MEM) Operations and Side Effects

The memory bus engine controls access to private SRAM (`32 KB`) and Flash ROM (`32 KB`).

### 3.1 Memory Commands (`MEM_CMD`)

| Code       | Mnemonic             | Bus Action | Memory Space | Target Address Calculation                                                                      |
|------------|----------------------|------------|--------------|-------------------------------------------------------------------------------------------------|
| `4'b0000`  | `MEM_NOP`            | Idle Bus   | None         | None.                                                                                           |
| `4'b0001`  | `MEM_RD_TOS`         | Read Byte  | Private SRAM | $\text{Addr} = SP - 4 + \text{BYTE\_CNT}$<br>                                                   |
| `4'b0010`  | `MEM_RD_NOS`         | Read Byte  | Private SRAM | $\text{Addr} = SP - 8 + \text{BYTE\_CNT}$<br>                                                   |
| `4'b0011`  | `MEM_RD_FLASH_QS`    | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_QS\_BASE} + (X_{\text{val}}[8:0] \cdot 2) + \text{HI\_FLAG}$<br>    |
| `4'b0100`  | `MEM_RD_FLASH_REC`   | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_RECIP\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br> |
| `4'b0101`  | `MEM_RD_FLASH_SQRT`  | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_SQRT\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br>  |
| `4'b0110`  | `MEM_RD_FLASH_EXP2`  | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_EXP2\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br>  |
| `4'b0111`  | `MEM_RD_FLASH_LOG2`  | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_LOG2\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br>  |
| `4'b1000`  | `MEM_RD_FLASH_SIN`   | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_SIN\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br>   |
| `4'b1001`  | `MEM_RD_FLASH_COS`   | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_COS\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br>   |
| `4'b1010`  | `MEM_RD_FLASH_TAN`   | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_TAN\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br>   |
| `4'b1011`  | `MEM_RD_FLASH_LN`    | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_LN\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br>    |
| `4'b1100`  | `MEM_RD_FLASH_LOG10` | Read Byte  | Flash ROM    | $\text{Addr} = \text{FLASH\_LOG10\_BASE} + (X_{\text{val}}[7:0] \cdot 2) + \text{HI\_FLAG}$<br> |
| `4'b1101`  | `MEM_WR_NOS`         | Write Byte | Private SRAM | $\text{Addr} = SP - 8 + \text{BYTE\_CNT} \gets \text{ALU\_OUT}[7:0]$<br>                        |
| `4'b1110`  | `MEM_WR_TOS`         | Write Byte | Private SRAM | $\text{Addr} = SP - 4 + \text{BYTE\_CNT} \gets \text{ALU\_OUT}[7:0]$<br>                        |
| `4'b1111`  | `MEM_RD_SCRATCH`     | Read Byte  | Private SRAM | $\text{Addr} = 0x0000 + \text{BYTE\_CNT}$<br>                                                   |
| `4'b10000` | `MEM_WR_SCRATCH`     | Write Byte | Private SRAM | $\text{Addr} = 0x0000 + \text{BYTE\_CNT} \gets \text{ALU\_OUT}[7:0]$<br>                        |

### 3.2 Address Calculation & `BYTE_CNT` Rules

1. **Auto-Incrementing Pointer Behavior:**

* Any active SRAM read or write command (`MEM_RD_TOS`, `MEM_RD_NOS`, `MEM_RD_SCRATCH`, `MEM_WR_TOS`, `MEM_WR_NOS`,
  `MEM_WR_SCRATCH`) automatically increments `BYTE_CNT <= BYTE_CNT + 1` at the end of the clock cycle.

2. **Target-Switch Reset Rule (CRITICAL HARDWARE RULE):**

* If `MEM_CMD` changes from one non-NOP memory target to another non-NOP memory target (e.g., switching from
  `MEM_RD_SCRATCH` to `MEM_WR_SCRATCH`), hardware resets `BYTE_CNT <= 0`.

* Intervening `MEM_NOP` cycles **do not** reset `BYTE_CNT` or break the current active memory target context.

3. **Flash ROM Addressing:**

* Flash table reads evaluate address indexing directly from `SRC_X`.

* `FLASH_QS_BASE` uses a 9-bit mask (`0x1FF`) allowing input values up to 510. All other Flash tables use an 8-bit mask
  (`0xFF`).

* `HI_FLAG` is set to `1` if `REG_LD` targets an upper-byte register (`LD_TMP0_HI` or `LD_TMP1_HI`), selecting the high
  byte of the 16-bit Flash table word.

---

## 4. Microcode Sequence Control (`SEQ_CTRL`) & `U_PC`

Every microcode instruction specifies a 2-bit sequence control code (`SEQ_CTRL`) to dictate `U_PC` branching.

| Code    | Mnemonic   | Sequence Behavior      | `U_PC` Next State                                                                                                                 |
|---------|------------|------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| `2'b00` | `SEQ_NEXT` | Linear Step Advance    | `U_PC <= U_PC + 1`<br>                                                                                                            |
| `2'b01` | `SEQ_LOOP` | Multi-Byte Serial Loop | If `BYTE_CNT < max_bytes`, loops `U_PC` back to routine entry point; else advances `U_PC <= U_PC + 1` and resets `BYTE_CNT <= 0`. |
| `2'b10` | `SEQ_DONE` | Execution Complete     | De-asserts `BUSY` status flag, triggers completion pulse, and resets `U_PC <= 0`.                                                 |

### Micro-Instruction Control Word Definition

Every cycle in the execution table (`UROM`) is defined by a 15-bit micro-instruction control word:

$$\text{Control Word} = [\text{ALU\_OP} (3) \mid \text{SRC\_X} (2) \mid \text{SRC\_Y} (2) \mid \text{MEM\_CMD} (4) \mid \text{REG\_LD} (4) \mid \text{SEQ\_CTRL} (2)]$$

---

## 5. Microcode Authoring Rules & Design Patterns

1. **Non-Destructive Operand Rule:**
   Operands residing in $NOS$ ($a_0..a_3$) and $TOS$ ($b_0..b_3$) must **never** be overwritten until all multi-pass
   cross-multiplication or partial product steps requiring those original bytes have completed reading.

2. **Scratchpad Stashing Pattern:**
   For multi-byte operations requiring re-reads of $NOS$ or $TOS$ (such as $32 \times 32$ integer multiplication or
   fixed-point division), microcode must stash operand bytes into $SCRATCH[0..3]$ before performing arithmetic writes.

3. **Managing `BYTE_CNT` Overheads:**
   Because `BYTE_CNT` resets to `0` when switching memory targets, accessing $SCRATCH[n]$ requires reading $n$ dummy
   bytes first if starting a new read sequence.

4. **Stack Frame Adjustment Post-Operation:**

* **Binary Operations (`ADD`, `SUB`, `MUL`, `DIV`, `POW`):** Consume 2 stack frames ($NOS$ and $TOS$) and return 1
  result frame. Upon completion, hardware adjusts the stack pointer $SP \gets \max (0x08, SP - 4)$. The written result
  in $NOS$ ($SP - 8$) automatically becomes the new $TOS$ ($SP_{\text{new}} - 4$).

* **Unary Operations (`CHS`, `SQRT`, `SIN`, `COS`, etc.):** Consume 1 frame and return 1 frame. $SP$ remains unchanged.
