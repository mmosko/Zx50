# ZX50 FPU Microarchitecture Specification (`u_arch.md`)

**Target Hardware:** ATF1508AS CPLD (`U11`), IS61C3216AL 12ns SRAM (`U12`), SST39SF040 55ns Flash ROM (`U13`)  
**Host Architecture:** Zx50 CPU Card (Rev C3) - Z80 System Bus  
**Status:** Live Architectural Specification & Machine Design Document  

---

## 1. Architectural Philosophy & Design Constraints

### 1.1 The CPLD Macrocell Budget & Sizing Analysis

The coprocessor execution engine targets an **Atmel/Microchip ATF1508AS-7 CPLD** in a PLCC-84 package.
* **Total Device Capacity:** **128 Macrocells** (each macrocell provides 1 D/T flip-flop, 5 product terms natively, and logic allocation).
* **Target Fit Threshold:** **< 115 Macrocells (< 90% utilization)** to guarantee successful routability in the global switch matrix without routing congestion or timing violations.

```text
===============================================================================
ATF1508AS CPLD Resource Utilization Estimate (Current Microarchitecture)
===============================================================================
Device:                     ATF1508AS-7 PLCC-84 (128 Macrocells, 64 I/O Pins)
Total Macrocells Estimated: 154 / 128   (120.3% — CURRENTLY OVERSUBSCRIBED)
Flip-Flops Required:         86 / 128   (67.2% Utilization)
Estimated Combinatorial MCs: 68 / 128   (Pin drivers, ALU, decoders, address mux)
===============================================================================
```

#### Detailed Macrocell Breakdown by Functional Submodule

| Submodule / Logic Block | FFs | Comb MCs | Total MCs | Details & Implementation Notes |
|---|:---:|:---:|:---:|---|
| **1. Register File** | **76** | **0** | **76** | |
| • `A` (Accumulator / high `AB`) | 8 | 0 | 8 | 8-bit registered macrocells |
| • `B` (Operand B / low `AB`) | 8 | 0 | 8 | 8-bit registered macrocells |
| • `L` (Product Low / Pointer L) | 8 | 0 | 8 | 8-bit registered macrocells |
| • `H` (Product High / Pointer H)| 8 | 0 | 8 | 8-bit registered macrocells |
| • `SP` (Stack Pointer word index) | 6 | 0 | 6 | 6-bit up/down counter ($0..63$) |
| • `loop_cnt` (Iteration counter)| 8 | 0 | 8 | 8-bit decrementer for `DJNZ` |
| • `u_pc` (Microcode Program Counter)| 11 | 0 | 11 | 11-bit micro-PC ($0x1000$–$0x17FF$) |
| • `ret_pc` (Hardware CALL return address)| 11 | 0 | 11 | 11-bit return PC latch for `CALL`/`RET` |
| • `STATUS` (Unified Status Register)| 7 | 0 | 7 | Bit 7 (`BUSY`), Bit 4 (`CARRY`), Bit 3 (`OVF`), Bit 2 (`UNF`), Bit 1 (`ERR`) (7 FFs; Bit 0 is 0; `ZERO`/`SIGN` evaluated combinatorially) |
| • `exec_sram` (Flash vs. SRAM flag)| 1 | 0 | 1 | 1-bit latch set by `SET_SRAM_EXEC` |
| **2. Stack Address Generation ($SP-1$, $SP-2$)** | **0** | **8** | **8** | |
| • $SP-1$ Borrow & Concatenation Logic | 0 | 4 | 4 | Evaluates $\{SP[5:0] - 1\}$ via 2-PT SOP chain (Section 2.4) |
| • $SP-2$ Shift & Concatenation Logic | 0 | 4 | 4 | Evaluates $\{SP[5:1] - 1, SP[0]\}$ via 2-PT SOP chain |
| **3. Private Memory Address Bus ($CA[14:0]$ Mux)** | **0** | **15** | **15** | Drives 15 physical output pins to SRAM/Flash. Muxes between instruction fetch (`{2'b00, exec_sram, 1'b0, u_pc}`), TOS (`{4'b0, SP-1, k}`), NOS (`{4'b0, SP-2, k}`), Scratchpad (`{7'b1, offset}`), Pointer `[HL]`, and host stack push/pop. High product-term fan-in. |
| **4. Memory Control Strobes & Buffer Control** | **0** | **6** | **6** | `M_CE_N`, `M_LB_N`, `M_UB_N`, `F_CE_N`, `C_OE_N`, `C_WE_N` generation |
| **5. 8-Bit Core ALU & Shifter** | **0** | **18** | **18** | |
| • 8-Bit Adder / Subtractor (`ADD`, `ADC`, `SUB`, `SBC`) | 0 | 10 | 10 | Fast carry chain, borrow logic, overflow detection |
| • Bitwise Logic Unit (`AND`, `OR`, `XOR`, `ABS_DIFF`) | 0 | 4 | 4 | Shared boolean logic multiplexers |
| • Shift Unit (`SHL`, `SHR` through Carry) | 0 | 4 | 4 | Bidirectional 1-bit shifter multiplexer |
| **6. Instruction Decoder & Branch Logic** | **0** | **12** | **12** | |
| • Opcode Decoder (5 bits $\rightarrow$ 32 control strobes) | 0 | 6 | 6 | Generates internal write-enables and mux selectors |
| • Branch Condition Logic (`JZ`, `JNZ`, `JC`, `JNC`, `DJNZ`) | 0 | 4 | 4 | Condition multiplexer driving `u_pc` load/increment |
| • Immediate / Format Field Extraction | 0 | 2 | 2 | Register destination and offset steering |
| **7. Z80 Host Interface & CDC Dispatch** | **10** | **9** | **19** | |
| • Z80 Port Address Decoder (`0x70`, `0x71`, `IORQ`, `RD`, `WR`) | 0 | 1 | 1 | Port select logic |
| • 4-Phase Level CDC Synchronizers (`ZCLK` $\leftrightarrow$ `MCLK`) | 4 | 0 | 4 | 2-stage synchronizers for `exec_req` and `done_ack` |
| • Dispatch FSM (`ST_IDLE`, `ST_EXEC`, `ST_DONE`, `ST_WAIT_ACK`) | 4 | 0 | 4 | Main command execution state machine |
| • Host 32-Bit Push/Pop Byte Sequencer ($0..3$) | 2 | 0 | 2 | 2-bit counter sequencing 4-byte stack transfers at port `0x70` |
| • Z80 Read Data Multiplexer (`Z80_D[7:0]` Output Pins) | 0 | 8 | 8 | Drives 8 bidirectional pins during `IN A, (0x70)` and `IN A, (0x71)` |
| • Open-Drain Handshake Drivers (`WAIT_N`, `INT_N`) | 0 | 2 | 2 | Asynchronous wait/interrupt assertion logic |
| **Grand Total Estimated Macrocells** | **86** | **68** | **154** | **Oversubscribed by 26 Macrocells (120.3%)** |

---

### 1.1.1 Macrocell Reduction Roadmap (Path to < 110 MCs / < 86% Fit)

To fit comfortably within the 128-macrocell ATF1508AS with safe routing margins, the following high-leverage optimizations can be applied:

1. **Eliminate Full `ret_pc` Register / Use Return Table or 1-to-2 Bit Return Tag (Save 9 to 11 Macrocells):**
   * *Rationale:* The microcode engine does not run arbitrary recursive software; shared helper routines (e.g., mantissa normalization, rounding, carry propagation) are invoked from only a handful of known call sites. Storing a full 11-bit return PC consumes 11 full macrocell flip-flops.
   * *Alternative A (Indexed Return Table):* A 1-bit or 2-bit return tag register (`ret_id[1:0]`, 2 FFs) records the caller index (supporting up to 4 call sites), and a small decode block jumps back to the appropriate return address, **saving 9 macrocells**.
   * *Alternative B (Inlining / Flat Dispatches):* Inline small routines and eliminate `CALL`/`RET` completely, **saving all 11 macrocells**.
   * *Alternative C (Relative / Local CALL within 32 Instructions):* Because CALL/RET is almost exclusively used by local helper blocks (e.g. cross-product routines in `MUL`) that reside within $\pm 32$ instructions of each other, upper PC bits remain identical and only the lower 5 bits of the return address (`ret_pc[4:0]`) need to be latched, **saving 6 macrocells** without requiring any return table logic. This shifts the constraint purely to microcode memory layout: the assembler enforces 32-instruction alignment (`.align 32` with occasional `NOP` padding), exchanging abundant SRAM memory space for scarce CPLD silicon.
2. **Narrow `loop_cnt` from 8 bits to 4 bits (Save 4 Macrocells):**
   * *Rationale:* Multi-byte serial iterations for 32-bit math require $N = 4$ iterations ($0..3$). A 4-bit counter ($0..15$) supports up to 128-bit operations with massive margin.
   * *Savings:* **-4 FFs / -4 MCs**.
3. **Right-Size `u_pc` Once Microcode is Written (Save 2 to 3 Macrocells):**
   * *Rationale:* The exact width of `u_pc` will be locked once the full microcode suite is assembled. If the instruction set fits in 512 words (9 bits) or 256 words (8 bits), narrowing `u_pc` directly trims 2 to 3 flip-flops and simplifies the branch target multiplexers.
   * *Savings:* **-2 to -3 FFs / MCs**.
4. **Streamline Host Stack Push/Pop Datapath (Save 6 Macrocells):**
   * *Rationale:* Currently, the host interface independently generates memory addresses to write to the SRAM stack during `OUT (0x70)`. If host push/pop writes directly into registers `HL`/`AB` or shares the execution datapath write cycle, dedicated host byte sequencers and address mux inputs collapse.
   * *Savings:* **-6 MCs**.
5. **Fold $SP-1$ / $SP-2$ Directly into Memory Address Multiplexer (Save 4 Macrocells):**
   * *Rationale:* Rather than generating intermediate boolean terms for $SP-1$ and $SP-2$ that consume macrocells, implement them directly as wired product-term inputs to the $CA[7:2]$ output pin macrocells.
   * *Savings:* **-4 MCs**.

**Net Post-Optimization Budget:**
$$148\text{ MCs} - 27\text{ MCs} = \mathbf{121\text{ MCs}} \quad (\mathbf{94.5\%}\text{ of 128 MCs})$$
Further combining ALU operations or trimming `u_pc` to 8 bits (256 instructions) brings total utilization to **~112 Macrocells (87.5%)**, guaranteeing an unconstrained fit.

---

### 1.2 Core Architectural Principles
1. **Lean 8-Bit Core with 16-Bit Register Pairs (`HL`, `AB`):**
   All core arithmetic operations and datapath ALU slices are 8 bits wide. Dedicated 16-bit register pairs `HL` (`{H, L}`) and `AB` (`{A, B}`) provide native 16-bit pointer addressing (`[HL]`) and single-cycle 16-bit word memory transfers over `CD[15:0]`.
2. **Pure Shadow-SRAM Architecture (Permanent Flash Disable):**
   At hardware reset, the CPLD boots out of Flash and runs a fast microcode loop that mirrors the active Flash contents (Math LUTs + Microcode) directly into SRAM at identical addresses (`0x0200`–`0x17FF`). Once copied:
   * **`f_ce_n` is locked HIGH (`1`) permanently**—Flash is completely disabled and put into standby.
   * **Zero Wait-State Controller:** All runtime accesses (instruction fetches, stack pushes/pops, scratchpad reads, and math table queries) target 12ns SRAM exclusively.
   * **Massive Simplification:** Completely eliminates dynamic wait-state counters (`flash_cnt`), clock-speed wait-state adaptation (`clk_spd`), and complex bus timing arbitration between 55ns Flash and 12ns SRAM.
3. **Sub-Millisecond Boot Time:**
   Copying the active 22 pages (`0x0200`–`0x17FF` = 5,632 bytes) takes $\approx 33,800$ clock cycles (**0.84 ms** at 40 MHz), completely invisible during host power-up.
4. **Zero-Adder Direct Offset Addressing & Hardware Stack Protection:**
   * **Stack Region (`0x0000`–`0x00FF` / 256 bytes):**
     Divided into 64 32-bit (4-byte) operand slots, tracked by the 6-bit word pointer $SP \in [0..63]$.
     Accessing byte $k \in \{0, 1, 2, 3\}$ uses pure bitwise wiring without runtime addition:
     * $\text{TOS}[k] = \{7'\text{b}0000000, (SP - 1)[5:0], k[1:0]\}$
     * $\text{NOS}[k] = \{7'\text{b}0000000, (SP - 2)[5:0], k[1:0]\}$
     * **Trivial Underflow Check:** If $SP == 0$, the stack is empty! An attempt to pop or compute immediately sets `ERR` and `UNDERFLOW` in `STATUS`.
     * **Trivial Overflow Check:** If $SP == 63$, pushing a word triggers `OVERFLOW`.
   * **Scratchpad Region (`0x0100`–`0x01FF` / 256 bytes):**
     Addresses are formed directly from the 8-bit immediate offset embedded in the instruction word:
     * $\text{SCRATCH}[k] = \{7'\text{b}0000001, k[7:0]\} = 0x0100 + k[7:0]$
     * **Zero Added Registers:** Requires 0 extra pointer registers in the CPLD; any of the 256 scratchpad bytes is accessible directly in 1 cycle.
5. **Primary Word Formats:**
   * **`i32`:** 32-bit two's-complement signed integer (4 bytes, little-endian).
   * **`f32`:** IEEE-754 single-precision floating-point (4 bytes, little-endian: 1 sign bit, 8 exponent bits, 23 mantissa bits).

---

## 2. Hardware Registers & Datapath

### 2.1 CPLD Internal Register File

| Register Name | Width | Macrocells | Functional Purpose |
|---|---|---|---|
| **`A`** | 8 bits | 8 | Primary 8-bit Accumulator. Holds ALU operand/result, LUT index, and high byte of `AB`. |
| **`B`** | 8 bits | 8 | Secondary 8-bit Operand / Stash Register, and low byte of `AB`. |
| **`L`** | 8 bits | 8 | Low byte of 16-bit math / pointer `HL`. |
| **`H`** | 8 bits | 8 | High byte of 16-bit math / pointer `HL`. |
| **`AB`** | 16 bits | (0 extra) | Virtual 16-bit register pair `{A, B}` for single-cycle 16-bit memory transfers. |
| **`HL`** | 16 bits | (0 extra) | 16-bit register pair `{H, L}` for math product and memory pointer `[HL]`. |
| **`SP`** | 6 bits | 6 | Stack Pointer (6-bit word index for 64 words of 4 bytes). Bottom 2 bits provided by `offset[1:0]`. |
| **`u_pc`** | 11 bits | 11 | Microcode Program Counter (addresses `0x1000`–`0x17FF` in Flash or SRAM). |
| **`loop_cnt`** | 8 bits | 8 | Multi-byte serial loop counter ($0..255$). Used by `DJNZ`. |
| **`ret_pc`** | 11 bits | 11 | 1-level hardware subroutine return address (for calling subroutines). |
| **`STATUS`** | 8 bits | 7 | Unified Status Register: `[BUSY, ZERO, SIGN, CARRY, OVERFLOW, UNDERFLOW, ERR, 0]` (7 FFs; Bit 0 is 0; `ZERO`/`SIGN` evaluated combinatorially). |
| **`exec_sram`** | 1 bit | 1 | 0 = Fetch microcode from Flash (at reset); 1 = Fetch microcode from SRAM. |
| **Total Engine Registers** | | **76 FFs** | Primary target for optimization (see Section 1.1.1 Reduction Roadmap). |

### 2.2 Unified Status Register (`STATUS` / Port `0x71` Read)

There is **only one** status register in the CPLD. It is shared directly between internal microcode execution and the host Z80 interface (read at `CPORT` `0x71`):

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`BUSY`** | **`ZERO`** | **`SIGN`** | **`CARRY`** | **`OVERFLOW`** | **`UNDERFLOW`** | **`ERR`** | Reserved (0) |

* **Single Register, Zero Macrocell Duplication:**
  * **Bit 7 (`BUSY`):** Managed by the CDC / dispatch FSM. Set to `1` when an opcode is written to port `0x71`; cleared to `0` by the `DONE` micro-instruction.
  * **Bits 6:3 (`ZERO`, `SIGN`, `CARRY`, `OVERFLOW`):** Updated directly by the 8-bit ALU on arithmetic operations (`ADD`, `ADC`, `SUB`, `SBC`, etc.). 
  * **Microcode Branching:** Conditional jumps (`JZ`, `JNZ`, `JC`, `JNC`) test these exact same register bits (`STATUS[6]` for zero, `STATUS[4]` for carry).
  * **Bit 1 (`ERR`):** Set on illegal opcodes, divide-by-zero, or domain errors.
  * **Host Read:** When the Z80 reads port `0x71`, it reads `STATUS[7:0]` directly. While the engine runs, `BUSY` is `1`. When `BUSY` drops to `0`, the flags already contain the final operation outcome without any latching or transfer cycles.

* **Z80 Polling Fast-Path:**
  Testing Bit 7 (`BUSY`) takes only 1 byte and 4 T-states on the Z80:
  ```z80
  wait_fpu:
      IN   A, (0x71)       ; Read Status Register
      OR   A               ; Test Bit 7 (sets Sign flag if BUSY == 1)
      JP   M, wait_fpu     ; Loop if still busy (A >= 0x80)
  ```

### 2.3 Datapath Block Diagram

```text
                     +-----------------------------------+
                     |       PRIVATE SRAM (64 KB)        |
                     |       IS61C3216AL (32K x 16)      |
                     | - Stack (0x0000 - 0x00FF)         |
                     | - Scratchpad (0x0100 - 0x01FF)    |
                     | - QS Table & LUTs (0x0200-0x0FFF) |
                     | - Microcode RAM (0x1000 - 0x17FF) |
                     +-----------------+-----------------+
                                       | CD[15:0] (Native 16-bit word bus)
                                       v
+-----------------------------------------------------------------------------------+
|                                 ATF1508AS CPLD                                    |
|                                                                                   |
|            +---------+       +---------+       +---------+       +---------+      |
|            |  REG A  |       |  REG B  |       |  REG H  |       |  REG L  |      |
|            | (8-bit) |       | (8-bit) |       | (8-bit) |       | (8-bit) |      |
|            +----+----+       +----+----+       +----+----+       +----+----+      |
|                 |                 |                 |                 |           |
|                 +--------+--------+                 +--------+--------+           |
|                          |                                   |                    |
|                          v                                   v                    |
|                   16-bit AB Pair                      16-bit HL Pair              |
|                          |                                   |                    |
|                          v                                   v                    |
|            +---------------------------+             +---------------+            |
|            |       8-BIT CORE ALU      |             | 16-bit Pointer|            |
|            | ADD / SUB / ABS_DIFF / SH |             |  Address [HL] |            |
|            +-------------+-------------+             +---------------+            |
|                          |                                   ^                    |
|                          v                                   |                    |
+--------------------------+-----------------------------------+--------------------+
                           |                                   |
                           v                                   |
                     +-----+-----------------------------------+-----+
                     |               PRIVATE FLASH ROM (32 KB)       |
                     | - Bootloader ROM (0x0000 - 0x01FF)            |
                     | - QS Table & LUTs Master (0x0200 - 0x0FFF)    |
                     | - Microcode Flash Master Image (0x1000-0x17FF)|
                     +-----------------------------------------------+
```

### 2.4 Zero-Adder SP Decrement Logic ($SP - 1$ and $SP - 2$ SOP Optimization)

The bit concatenation trick (`{SP[5:0], offset[1:0]}`) is an excellent architectural move for CPLD designs—it completely eliminates the 8-bit adder needed for memory offset calculations.

Furthermore, **a full adder tree (XOR / carry-lookahead) is not needed to compute $SP - 1$ or $SP - 2$.** Because subtraction by 1 and 2 has predictable borrow propagation, both operations can be implemented using a minimal Sum-of-Products (SOP) boolean chain that fits inside a single CPLD macrocell layer with zero expander term penalties.

#### Trick 1: $SP - 2$ is just $SP - 1$ shifted by 1 bit

Mathematically, subtracting 2 from a binary number leaves the least significant bit ($SP[0]$) completely untouched:

$$SP - 2 = ((SP[5:1] - 1) \ll 1) \mid SP[0]$$

* **Bit 0 ($SP[0]$):** Passed through directly ($Z_0 = SP[0]$).
* **Bits 5:1 ($SP[5:1]$):** Simply a 5-bit decrement-by-1 operation on the upper 5 bits!

This cuts the borrow-chain depth for $SP - 2$ from 6 bits down to 5 bits.

#### Trick 2: The 2-Product-Term (2-PT) Borrow Chain

In CPLD architectures like the ATF1508AS, macrocells evaluate Sum-of-Products (SOP) expressions. A standard adder/subtractor uses XOR trees that can blow up Product Term (PT) counts.

However, decrementing by 1 only flips bit $k$ if all lower bits $0 \dots k-1$ are `0`. Expressed as a boolean equation:

$$\text{Bit}_k = SP[k] \oplus (\bar{SP}[0] \cdot \bar{SP}[1] \dots \bar{SP}[k-1])$$

Expanding the XOR into SOP ($A \oplus B = A\bar{B} + \bar{A}B$):

$$\text{Bit}_k = SP[k] \cdot (SP[0] + SP[1] + \dots + SP[k-1]) + \bar{SP}[k] \cdot \bar{SP}[0] \cdot \bar{SP}[1] \dots \bar{SP}[k-1]$$

Every single bit of a decrementer requires **at most 2 Product Terms**! Since an ATF1508AS macrocell provides 5 PTs natively, every output bit fits into a single macrocell without needing expander terms or incurring extra $t_{PD}$ propagation delay.

#### Product Term (PT) Cost Breakdown

##### For $SP - 1$ (6-bit Output $Y[5:0]$):

* $Y[0] = \bar{SP}[0]$ **(1 PT)**
* $Y[1] = SP[1] \cdot SP[0] + \bar{SP}[1] \cdot \bar{SP}[0]$ **(2 PTs)**
* $Y[2] = SP[2] \cdot (SP[0] + SP[1]) + \bar{SP}[2] \cdot \bar{SP}[0] \cdot \bar{SP}[1]$ **(2 PTs)**
* $Y[3] = SP[3] \cdot (SP[0] + SP[1] + SP[2]) + \bar{SP}[3] \cdot \bar{SP}[0] \cdot \bar{SP}[1] \cdot \bar{SP}[2]$ **(2 PTs)**
* $Y[4] = SP[4] \cdot (SP[0] + SP[1] + SP[2] + SP[3]) + \bar{SP}[4] \cdot \bar{SP}[0] \cdot \bar{SP}[1] \cdot \bar{SP}[2] \cdot \bar{SP}[3]$ **(2 PTs)**
* $Y[5] = SP[5] \cdot (SP[0] + \dots + SP[4]) + \bar{SP}[5] \cdot \bar{SP}[0] \dots \bar{SP}[4]$ **(2 PTs)**

> **Total Cost for $SP - 1$:** **11 Product Terms** across 6 macrocells.

##### For $SP - 2$ (6-bit Output $Z[5:0]$):

* $Z[0] = SP[0]$ **(1 PT - wire passthrough)**
* $Z[1] = \bar{SP}[1]$ **(1 PT)**
* $Z[2] = SP[2] \cdot SP[1] + \bar{SP}[2] \cdot \bar{SP}[1]$ **(2 PTs)**
* $Z[3] = SP[3] \cdot (SP[1] + SP[2]) + \bar{SP}[3] \cdot \bar{SP}[1] \cdot \bar{SP}[2]$ **(2 PTs)**
* $Z[4] = SP[4] \cdot (SP[1] + SP[2] + SP[3]) + \bar{SP}[4] \cdot \bar{SP}[1] \cdot \bar{SP}[2] \cdot \bar{SP}[3]$ **(2 PTs)**
* $Z[5] = SP[5] \cdot (SP[1] + \dots + SP[4]) + \bar{SP}[5] \cdot \bar{SP}[1] \dots \bar{SP}[4]$ **(2 PTs)**

> **Total Cost for $SP - 2$:** **10 Product Terms** across 6 macrocells.

#### Optimized Synthesizable Verilog Implementation

Direct structural/reduction Verilog guarantees synthesis compilers (WinCUPL, ProChip, Quartus) synthesize this into single AND/NOR planes without inferring full adder blocks:

```verilog
module sp_decrementation (
    input  wire [5:0] sp,
    output wire [5:0] sp_minus_1,
    output wire [5:0] sp_minus_2
);

    // =========================================================================
    // SP - 1 Implementation
    // =========================================================================
    assign sp_minus_1[0] = ~sp[0];
    assign sp_minus_1[1] = sp[1] ^ (~sp[0]);
    assign sp_minus_1[2] = sp[2] ^ (~|sp[1:0]);
    assign sp_minus_1[3] = sp[3] ^ (~|sp[2:0]);
    assign sp_minus_1[4] = sp[4] ^ (~|sp[3:0]);
    assign sp_minus_1[5] = sp[5] ^ (~|sp[4:0]);

    // =========================================================================
    // SP - 2 Implementation (Bit 0 passthrough + 5-bit decrement)
    // =========================================================================
    assign sp_minus_2[0] = sp[0];
    assign sp_minus_2[1] = ~sp[1];
    assign sp_minus_2[2] = sp[2] ^ (~sp[1]);
    assign sp_minus_2[3] = sp[3] ^ (~|sp[2:1]);
    assign sp_minus_2[4] = sp[4] ^ (~|sp[3:1]);
    assign sp_minus_2[5] = sp[5] ^ (~|sp[4:1]);

endmodule
```

#### Key Architectural Takeaways

1. **Zero Adder Overhead:** The `~|sp[k:0]` NOR reduction operator synthesizes directly into single NOR terms ($\bar{SP}[0] \cdot \bar{SP}[1] \dots$), mapping 1:1 into CPLD AND planes.
2. **Deterministic Speed:** Because every bit logic depth is 1 level of SOP gates, propagation delay is fixed at $1 \cdot t_{PD}$ (e.g., $7.5\text{ ns}$ on an ATF1508AS-7).
3. **Term Sharing:** Synthesis tools will recognize that the NOR terms ($\bar{SP}[1]$, $\bar{SP}[2] \cdot \bar{SP}[1]$, etc.) are identical between the $SP-1$ and $SP-2$ paths, collapsing global product term usage even further.

---

## 3. Memory Map & Address Spaces

### 3.1 Private SRAM Memory Map (`32 KB` / `IS61C256AL` / Single-Cycle 12ns)
*All runtime math, stack, tables, and microcode execute exclusively from this single-cycle memory.*

| Address Range | Allocation | Size | Description |
|---|---|---|---|
| `0x0000`–`0x00FF` | **`STACK`**     | 256 bytes| **Math Stack:** 64 operand slots of 32 bits (4 bytes), indexed by $SP[5:0]$. Underflow when $SP=0$. |
| `0x0100`–`0x01FF` | **`SCRATCH`**   | 256 bytes| **Scratchpad:** Multi-byte accumulator (`ACC64`), stash registers (`OP_A`, `OP_B`), float unpack fields, temporary variables. Addressed directly by immediate 8-bit offset `[k]` in instruction word (`0x0100 + k`). |
| `0x0200`–`0x05FD` | **`SRAM_QS_LUT`**| 1022 bytes| **Shadowed Quarter-Square Table** ($f(n) = \lfloor n^2 / 4 \rfloor$). **1-cycle read!** |
| `0x0600`–`0x07FF` | **`SRAM_RECIP`** | 512 bytes | **Shadowed Reciprocal Seed Table**. **1-cycle read!** |
| `0x0800`–`0x09FF` | **`SRAM_SQRT`**  | 512 bytes | **Shadowed Square Root Seed Table**. **1-cycle read!** |
| `0x0A00`–`0x0FFF` | **`SRAM_CONST`** | 1.5 KB   | **Shadowed Transcendental constants**. **1-cycle read!** |
| `0x1000`–`0x17FF` | **`UCODE_RAM`** | 2 KB     | **Microcode RAM execution space**. **1-cycle fetch!** |
| `0x1800`–`0x7FFF` | **Reserved**    | 26 KB    | Free expansion memory. |

### 3.2 Private Flash ROM Memory Map (`32 KB` / `SST39SF040` / 55ns)
*Accessed ONLY during the 0.84 ms boot phase. Disabled permanently via `f_ce_n = 1` during all runtime operations.*

| Address Range | Table Name | Entry Size | Description |
|---|---|---|---|
| `0x0000`–`0x01FF` | **`BOOT_ROM`**       | 512 bytes            | Reset vector & ROM-to-RAM boot copy routine. |
| `0x0200`–`0x05FD` | **`FLASH_QS_TABLE`** | 511 $\times$ 16-bit  | Quarter-Square Table master image. |
| `0x0600`–`0x07FF` | **`FLASH_RECIP`**    | 256 $\times$ 16-bit  | Reciprocal Table master image. |
| `0x0800`–`0x09FF` | **`FLASH_SQRT`**     | 256 $\times$ 16-bit  | Square Root Seed master image. |
| `0x0A00`–`0x0FFF` | **`FLASH_CONST`**    | 1.5 KB               | Transcendental Constants master image. |
| `0x1000`–`0x17FF` | **`UCODE_FLASH`**    | 2 KB                 | Microcode master image. |
| `0x1800`–`0x7FFF` | **Unused**           | 26 KB                | Unused Flash space. |

---

## 4. Micro-Instruction Set Architecture (ISA)

Micro-instructions are uniformly **16 bits wide (2 bytes in SRAM)**, decoded in three clean formats:

```text
Format A (ALU / 2-Register Ops):
 15          11 10      8 7       5 4            0
+--------------+---------+---------+--------------+
|    OPCODE    |   DST   |   SRC   |    UNUSED    |
|   (5 bits)   | (3 bits)| (3 bits)|   (5 bits)   |
+--------------+---------+---------+--------------+

Format B (Memory / Scratch / Immediate Ops):
 15          11 10      8 7                            0
+--------------+---------+------------------------------+
|    OPCODE    | DST/SRC |      OFFSET / IMMEDIATE      |
|   (5 bits)   | (3 bits)|          (8 bits)            |
+--------------+---------+------------------------------+

Format C (Control Flow / Branches):
 15          11 10                                     0
+--------------+----------------------------------------+
|    OPCODE    |             TARGET ADDRESS             |
|   (5 bits)   |               (11 bits)                |
+--------------+----------------------------------------+
```

> [!NOTE]
> **Instruction Fetch & Branch Target Addressing (`ca[14:0] = {2'b00, exec_sram, 1'b0, u_pc[10:0]}`):**  
> The physical memory address for instruction fetches and Format C branch targets is formed unconditionally at all times by direct bit-concatenation—requiring **zero multiplexers, conditionals, or adders**:
> $$\text{ca}[14:0] = \{2'\text{b}00, \text{exec\_sram}, 1'\text{b}0, u\_pc[10:0]\}$$
> * **Bit 12 (`exec_sram`):** Provides the binary weight $2^{12} = 4096 = \mathbf{0x1000}$.
> * **Bit 11 (`1'b0`):** Fixed to zero, matching the base address offset.
> * **Bits 10:0 (`u_pc[10:0]`):** 11-bit counter spanning $0$ to $2047$ (`0x000` to `0x7FF`).
> * **Bootloader Flash Phase (`exec_sram == 0`):** Addresses evaluate directly to `0x0000`–`0x07FF` in Flash (the reset bootloader simply stays within $u\_pc < 0x200$, i.e. `0x0000`–`0x01FF`).
> * **Runtime SRAM Execution (`exec_sram == 1`):** Addresses evaluate directly to $0x1000 + u\_pc[10:0]$, spanning exactly **`0x1000` to `0x17FF`** (2 KB / 1,024 instructions) in SRAM.

### 4.1 Register Encoding Fields (`DST` / `SRC`)

The 3-bit register field (`[10:8]` in Format B, `[10:8]` and `[7:5]` in Format A) maps orthogonal registers for arithmetic, control, and memory access:

| Code | Memory Ops (`LD` / `ST`) | Immediate / ALU Ops | Description |
|:---:|:---:|:---:|---|
| `3'b000` | `REG_NONE` | `REG_NONE` | No register writeback (discard / comparison only) |
| `3'b001` | **`REG_A`** | **`REG_A`** | 8-bit Accumulator (high byte of `AB`) |
| `3'b010` | **`REG_B`** | **`REG_B`** | 8-bit Secondary Operand / Stash (low byte of `AB`) |
| `3'b011` | **`REG_L`** | **`REG_L`** | 8-bit Product / Pointer Low |
| `3'b100` | **`REG_H`** | **`REG_H`** | 8-bit Product / Pointer High |
| `3'b101` | **`REG_HL`** *(16-bit)* | **`REG_SP`** | **Implied 16-bit Pair `{H, L}`** (Memory) / 6-bit Stack Pointer (Immediate) |
| `3'b110` | **`REG_AB`** *(16-bit)* | **`REG_LOOP`** | **Implied 16-bit Pair `{A, B}`** (Memory) / 8-bit Loop Counter (Immediate) |
| `3'b111` | Reserved | **`REG_STATUS`** | 8-bit Unified Status Register (`[BUSY, ZERO, SIGN, CARRY, OVF, UNF, ERR, 0]`) |

*Implied 16-Bit vs. 8-Bit Memory Transfer Rules:*
* When `DST` / `SRC` specifies **`REG_HL`** or **`REG_AB`**, the memory operation is **implicitly 16-bit wide**:
  * Asserts **both** `M_LB_N = 0` and `M_UB_N = 0` simultaneously.
  * A full 16-bit word transfers between SRAM and the register pair in a **single clock cycle (25 ns)**!
  * `CD[7:0]` maps to the low register (`L` or `B`); `CD[15:8]` maps to the high register (`H` or `A`).
* When `DST` / `SRC` specifies an 8-bit register (**`A`**, **`B`**, **`L`**, **`H`**):
  * The memory operation is an **8-bit byte access**:
  * Even byte address / offset ($A_0 == 0$): Asserts `M_LB_N = 0, M_UB_N = 1` $\rightarrow$ transfers `CD[7:0]`.
  * Odd byte address / offset ($A_0 == 1$): Asserts `M_LB_N = 1, M_UB_N = 0` $\rightarrow$ transfers `CD[15:8]`.

*Microcode Flag Manipulation:*  
Because `STATUS` is a first-class register (`REG_STATUS`), microcode can directly read, set, or clear flags using standard bitwise ALU instructions:
* **Set Error:** `OR STATUS, 0x02` (sets `ERR` bit 1 on divide-by-zero or domain errors).
* **Set Overflow:** `OR STATUS, 0x08` (sets `OVERFLOW` bit 3).
* **Clear Carry:** `AND STATUS, 0xEF` (clears `CARRY` bit 4, equivalent to `CLR_C`).
* **Clear Busy:** `AND STATUS, 0x7F` (clears `BUSY` bit 7 upon completion).

### 4.2 Instruction Opcodes

#### Memory Operations
* **`0x01: LD_TOS DST, [offset]`**: Loads from TOS into `DST` in 1 cycle.
  * If `DST == HL`: Loads lower 16-bit word (bytes 0 & 1) of TOS into `HL`.
  * If `DST == AB`: Loads upper 16-bit word (bytes 2 & 3) of TOS into `AB`.
  * If `DST == A/B/L/H`: Loads individual byte at byte offset $0..3$ ($offset \in 0..3$ in bits [1:0]).
* **`0x02: LD_NOS DST, [offset]`**: Loads from NOS into `DST` in 1 cycle (16-bit word for `HL`/`AB`, or 8-bit byte for `A`/`B`/`L`/`H`).
* **`0x03: ST_NOS [offset], SRC`**: Stores `SRC` into NOS in 1 cycle (16-bit word for `HL`/`AB`, or 8-bit byte for `A`/`B`/`L`/`H`).
* **`0x04: LD_SCR DST, [offset]`**: Loads from Scratchpad into `DST` in 1 cycle.
  * If `DST == HL` or `AB`: Loads 16-bit word from scratchpad offset.
  * If `DST == A/B/L/H`: Loads 8-bit byte from scratchpad offset. Full 8-bit $offset \in 0..255$ in bits [7:0].
* **`0x05: ST_SCR [offset], SRC`**: Stores `SRC` into Scratchpad in 1 cycle (16-bit word for `HL`/`AB`, or 8-bit byte for `A`/`B`/`L`/`H`).
* **`0x06: LD_IMM DST, imm8`**: Loads immediate 8-bit constant into `DST` (`A`, `B`, `L`, `H`, `SP`, `LOOP`, `STATUS`).
* **`0x07: LD_FL DST, [HL]`**: Loads `DST <= Flash[HL]`. Reads Flash byte at pointer address `HL = {H, L}` using fixed 3-cycle Flash timing. Data drives `CD[7:0]`.
* **`0x08: ST_RAM [HL], SRC`**: Stores into `SRAM[HL]` in 1 cycle.
  * If `SRC == HL` or `AB`: Writes 16-bit word into SRAM with `M_LB_N = 0, M_UB_N = 0`.
  * If `SRC == A/B/L/H`: Writes 8-bit byte into SRAM lane selected by $HL_0$.
* **`0x09: LD_RAM DST, [HL]`**: Loads from `SRAM[HL]` in 1 cycle.
  * If `DST == HL` or `AB`: Reads 16-bit word from SRAM into register pair. (Used for single-cycle Quarter-Square LUT lookups!).
  * If `DST == A/B/L/H`: Reads 8-bit byte from SRAM lane selected by $HL_0$.

#### Arithmetic & Logic Unit (ALU) Operations
All arithmetic operations update `STATUS` flags: `ZERO` (bit 6), `SIGN` (bit 5), `CARRY` (bit 4).
* **`0x0A: ADD DST, SRC`**: `DST <= DST + SRC` (Clears Carry before add).
* **`0x0B: ADC DST, SRC`**: `DST <= DST + SRC + C` (Add with Carry).
* **`0x0C: SUB DST, SRC`**: `DST <= DST - SRC` (Clears Borrow before sub).
* **`0x0D: SBC DST, SRC`**: `DST <= DST - SRC - C` (Subtract with Borrow).
* **`0x0E: ABS_DIFF DST, SRC`**: `DST <= |DST - SRC|` (Unsigned magnitude, resets `C`).
* **`0x0F: AND DST, SRC`**: Bitwise AND.
* **`0x10: OR DST, SRC`**: Bitwise OR.
* **`0x11: XOR DST, SRC`**: Bitwise XOR.
* **`0x12: SHL DST`**: Logical Shift Left through Carry: `DST <= (DST << 1) | C`.
* **`0x13: SHR DST`**: Logical Shift Right through Carry: `DST <= (DST >> 1)`.
* **`0x14: MUL8`**: Executes hardware 8x8 Quarter-Square lookup sequence on inputs in `A` and `B`. Results load directly into 16-bit register pair `HL` (`{H, L}`).
* **`0x15: OR_IMM DST, imm8`**: Bitwise OR with 8-bit immediate (bits [7:0] encode `imm8`). Useful for setting flags: `OR_IMM STATUS, 0x02` sets `ERR`.
* **`0x16: AND_IMM DST, imm8`**: Bitwise AND with 8-bit immediate (bits [7:0] encode `imm8`). Useful for clearing flags: `AND_IMM STATUS, 0x7F` clears `BUSY`.

#### Program Control Flow
All branch instructions (`0x18`–`0x1E`) take an 11-bit `target` offset relative to base address **`0x1000`** (evaluating to physical address `0x1000 + target` during normal SRAM execution):
* **`0x17: SET_SRAM_EXEC`**: Sets `exec_sram <= 1`. Switches instruction fetch multiplexer from Flash ROM to single-cycle 40 MHz SRAM and locks `f_ce_n = 1`.
* **`0x18: JMP target`**: Unconditional branch to 11-bit microcode address (`0x1000 + target`).
* **`0x19: JZ target`**: Branch if Zero flag `Z == 1`.
* **`0x1A: JNZ target`**: Branch if Zero flag `Z == 0`.
* **`0x1B: JC target`**: Branch if Carry flag `C == 1`.
* **`0x1C: JNC target`**: Branch if Carry flag `C == 0`.
* **`0x1D: DJNZ target`**: Decrement `loop_cnt`; branch to `target` if `loop_cnt != 0`.
* **`0x1E: CALL target`**: Saves `ret_pc <= u_pc + 1` and branches to `target`.
* **`0x1F: RET`**: Returns to `u_pc <= ret_pc`.
* **`0x00: DONE`**: Signals execution complete, de-asserts `BUSY`, asserts CDC acknowledge, adjusts $SP$, and idles.

---

## 5. Mathematical Algorithms & Firmware Routines

### 5.0 Bootloader & ROM-to-RAM Copy (`0x0000`)

Upon hardware reset, `exec_sram` is `0`, causing the CPLD to fetch instructions directly from Flash starting at reset vector `0x0000`. The bootloader uses standard `LD_FL` and `ST_RAM` instructions with the 8-bit ALU to mirror the active 22 pages of Flash (LUTs + microcode from `0x0200` to `0x17FF`) into SRAM, leaving SRAM Stack (`0x0000`–`0x00FF`) and Scratchpad (`0x0100`–`0x01FF`) completely pristine:

```text
; =========================================================================
; Reset Bootloader (Executes directly out of Flash at 0x0000 on power-up)
; =========================================================================
boot_entry:
    LD_IMM   H, 0x02         ; HL = 0x0200 (Start of Quarter-Square LUT)
    LD_IMM   L, 0x00
    LD_IMM   B, 22           ; Copy 22 pages * 256 = 5632 bytes (0x0200 - 0x17FF)
page_loop:
    LD_FL    A, [HL]         ; 1. Read byte from Flash[HL] into A (3 cycles)
    ST_RAM   [HL], A         ; 2. Write byte from A into SRAM[HL] (1 cycle)
    ADD      L, 1            ; 3. Increment low byte of pointer (ALU sets Z on rollover)
    JNZ      page_loop       ; 4. Inner loop: repeat 256 times until L wraps to 0x00
    ADD      H, 1            ; Increment page (high byte of pointer)
    SUB      B, 1            ; Decrement page counter
    JNZ      page_loop       ; Outer loop: repeat until all 22 pages copied
    SET_SRAM_EXEC            ; Lock f_ce_n HIGH permanently! Switch fetches to 40MHz SRAM!
    JMP      fpu_idle        ; Jump to SRAM command dispatcher
```

**Key Advantages:**
* **Preserves Stack & Scratchpad:** SRAM Stack (`0x0000`–`0x00FF`) and Scratchpad (`0x0100`–`0x01FF`) are untouched by the copy loop.
* **No Shared Strobe Hazards:** Separating the Flash read (`LD_FL`) and SRAM write (`ST_RAM`) into distinct instructions ensures `C_WE_N` is asserted only while `F_CE_N = 1`, completely avoiding accidental Flash write cycles.
* **Zero Dedicated Copy Hardware:** Reuses the standard register `A`, pointer `HL`, and 8-bit ALU. No special hardware state machines, adders, or DMA counters needed in the CPLD.
* **Boot Overhead:** 22 pages (5,632 bytes) takes $\approx 33,800$ cycles = **$0.84\text{ ms}$ at 40 MHz** (under 1 millisecond).

---

### 5.1 The 8x8 Quarter-Square Hardware Primitive (`MUL8`)

Quarter-Square multiplication computes exact $A \times B$ in 16 bits using:
$$A \times B = \lfloor (A + B)^2 / 4 \rfloor - \lfloor |A - B|^2 / 4 \rfloor$$

Because tables are shadowed in 16-bit SRAM (`IS61C3216AL`), table lookups complete in **single-cycle 12ns 16-bit SRAM reads** with zero wait states:

**Execution Steps during `MUL8`:**
1. Compute $S = A + B$. $S \in [0..510]$ (9 bits).
2. Compute $D = |A - B|$. $D \in [0..255]$ (8 bits).
3. Query **SRAM** Quarter-Square Table for $S$ (Word Address: `0x0100 + S`):
   * Cycle 1: `LD_RAM HL, [S_addr]` $\rightarrow$ Reads full 16-bit entry $QS[S]$ into `HL` in **1 single clock cycle**!
4. Query **SRAM** Quarter-Square Table for $D$ (Word Address: `0x0100 + D`):
   * Cycle 2: `LD_RAM AB, [D_addr]` $\rightarrow$ Reads full 16-bit entry $QS[D]$ into `AB` in **1 single clock cycle**!
5. 16-bit Subtract: $HL - AB$:
   * Cycle 3: `SUB L, B` $\rightarrow$ $L \Leftarrow L - B$ (resets Carry, sets borrow).
   * Cycle 4: `SBC H, A` $\rightarrow$ $H \Leftarrow H - A - \text{borrow}$.
6. **Output:** `HL = {H, L}` contains the exact 16-bit unsigned product $A \times B$.
7. **Total `MUL8` Duration:** **5 to 6 clock cycles ($125\text{ ns}$ to $150\text{ ns}$ at 40 MHz)**!

---

### 5.2 32-Bit Integer Multiplication (`i32_mul`)

Multiplication of two 32-bit integers $A = (a_3, a_2, a_1, a_0)$ and $B = (b_3, b_2, b_1, b_0)$ producing the lowest 32 bits of the product requires **10 cross-products**:

$$\text{Result}[k] = \sum_{i+j=k} a_i \cdot b_j + \text{carries}$$

```text
Byte 0:  a0*b0
Byte 1:  a0*b1 + a1*b0
Byte 2:  a0*b2 + a1*b1 + a2*b0
Byte 3:  a0*b3 + a1*b2 + a2*b1 + a3*b0
```

#### Microcode Flow:
1. **Stash Operands (Fast 16-Bit Transfers):**
   * Load lower words: `LD_TOS HL, [0]` (loads $a_0, a_1$ into `HL` in 1 cycle); store into `OP_A_STASH`.
   * Load upper words: `LD_TOS AB, [1]` (loads $a_2, a_3$ into `AB` in 1 cycle); store into `OP_A_STASH`.
   * Load $b_0..b_3$ from `NOS` into `OP_B_STASH[0..3]`.
   * Clear accumulator: `ACC64 <= 0`.
2. **Execute Cross-Products & Accumulate:**
   * For each pair $(i, j)$ where $i + j < 4$:
     * `A <= OP_A_STASH[i]`
     * `B <= OP_B_STASH[j]`
     * `MUL8` $\rightarrow$ 16-bit product in `HL` (`H`, `L`).
     * Add `L` to `ACC64[i + j]` with carry propagation through higher bytes.
     * Add `H` to `ACC64[i + j + 1]` with carry propagation through higher bytes.
3. **Writeback:**
   * Store `ACC64` into `NOS` (two 16-bit word writes with `ST_NOS`).
   * `DONE`.

---

### 5.3 32-Bit Single-Precision Float Multiplication (`f32_mul`)

IEEE-754 format: `[Sign: 1 bit | Exponent: 8 bits | Mantissa: 23 bits]`
Implicit leading 1 gives a **24-bit significand**: $M = 1.f$ (3 bytes: $m_2, m_1, m_0$).

#### Microcode Flow:
1. **Unpack:**
   * Compute Result Sign: $s_R = \text{TOS}[3][7] \oplus \text{NOS}[3][7]$.
   * Extract Exponents:
     * $e_A = (\text{TOS}[3][6:0] \ll 1) \mid (\text{TOS}[2][7])$.
     * $e_B = (\text{NOS}[3][6:0] \ll 1) \mid (\text{NOS}[2][7])$.
     * $e_R = e_A + e_B - 127$.
   * Extract 24-bit Mantissas into `FP_UNPACK`:
     * $M_A = \{1'\text{b}1, \text{TOS}[2][6:0], \text{TOS}[1], \text{TOS}[0]\}$.
     * $M_B = \{1'\text{b}1, \text{NOS}[2][6:0], \text{NOS}[1], \text{NOS}[0]\}$.
2. **$24 \times 24$-bit Mantissa Cross-Multiply:**
   $M_A$ and $M_B$ are each 3 bytes ($a_2, a_1, a_0$ and $b_2, b_1, b_0$).
   Their product is 48 bits (6 bytes: $p_5, p_4, p_3, p_2, p_1, p_0$), requiring exactly **9 cross-products** ($3 \times 3$):
   * $k = 0$: $a_0 b_0$
   * $k = 1$: $a_0 b_1, a_1 b_0$
   * $k = 2$: $a_0 b_2, a_1 b_1, a_2 b_0$
   * $k = 3$: $a_1 b_2, a_2 b_1$
   * $k = 4$: $a_2 b_2$
   Accumulate into `ACC64[0..5]`.
3. **Normalize & Round:**
   * If product MSB (bit 47, i.e., bit 7 of `ACC64[5]`) is `1`:
     * Mantissa is $\ge 2.0$. Shift 48-bit product right by 1 bit.
     * Increment exponent: $e_R = e_R + 1$.
   * Take 23 bits following the implicit leading 1 (bits [46:24]) as the fractional mantissa.
4. **Pack IEEE-754 Word:**
   * Assemble into 4 bytes:
     * Byte 0: Mantissa bits [7:0]
     * Byte 1: Mantissa bits [15:8]
     * Byte 2: $\{e_R[0], \text{Mantissa}[22:16]\}$
     * Byte 3: $\{s_R, e_R[7:1]\}$
   * Store into `NOS[0..3]`.
   * `DONE`.

---

## 6. Execution Timing Estimates (40 MHz MCLK)

Because all Quarter-Square table lookups execute from 12ns SRAM at **1 cycle per byte** (instead of 3-cycle Flash lookups), math operations run over 2x faster:

| Operation | Total Cycles | Execution Time @ 40 MHz | Comparison: Z80 Software @ 5 MHz | Speedup |
|---|---|---|---|---|
| **`i32_add` / `i32_sub`** | ~16 cycles | $0.4\ \mu\text{s}$ | ~80 cycles ($16\ \mu\text{s}$) | **~40x** |
| **`i32_mul`** (10 cross-products) | ~100 cycles | $2.5\ \mu\text{s}$ | ~1,500 cycles ($300\ \mu\text{s}$) | **~120x** |
| **`f32_mul`** (9 cross-products + pack) | ~115 cycles | $2.9\ \mu\text{s}$ | ~4,500 cycles ($900\ \mu\text{s}$) | **~310x** |
| **`f32_add` / `f32_sub`** | ~80 cycles | $2.0\ \mu\text{s}$ | ~2,500 cycles ($500\ \mu\text{s}$) | **~250x** |

---

## 7. Python Machine Simulator Architecture Plan

The simulator suite in `fpu/fpu_rev1/tools/` will be structured as follows:

1. **`build_flash.py`:** Generates the Flash binary (`fpu_flash.bin`) containing the Quarter-Square table and master microcode image.
2. **`fpu_sim_isa.py`:** Formal binary constants, opcode defines, and micro-assembler for generating 16-bit micro-instructions.
3. **`zx50_fpu_machine.py`:** Cycle-accurate Python machine model implementing:
   * 8-bit core registers (`A`, `B`, `L`, `H`, `u_pc`, `loop_cnt`, `ret_pc`, `STATUS`) and 16-bit pairs (`HL`, `AB`).
   * Bootloader copying Flash image to SRAM on reset.
   * Direct offset memory address decoding.
   * 16-bit micro-instruction execution engine.
4. **`fpu_sim_microcode.py`:** Assembly/microcode source routines for `i32_add`, `i32_sub`, `i32_mul`, `f32_add`, `f32_mul`.
5. **`fpu_sim_test.py`:** Comprehensive test suite validating arithmetic against reference values across edge cases.

---

## 8. Hardware Requirements (CPU Rev C3 & IS61C3216AL Integration)

### 8.1 CPLD Pin Reallocations (ATF1508AS PLCC-84)

The transition to a native 16-bit local memory bus (`CD[15:0]`) is achieved by freeing 10 unused pins on the CPLD without sacrificing any functionality. All active-low signals use `_N` notation for consistency across KiCad schematics and Verilog code.

| CPLD Pin(s) | Rev C2 Assignment | Rev C3 Assignment | Direction | Description |
|---|---|---|---|---|
| **Pins 4, 5, 6, 8, 9, 10, 79, 80** | `Z80_A[15:8]` | **`CD[15:8]`** | Bidirectional | **SRAM High Data Byte:** Connects to `I/O[15:8]` of `IS61C3216AL`. |
| **Pin 81** | `CLK_SPD` (Jumper J8) | **`M_LB_N`** | Output | **SRAM Lower Byte Enable:** Controls `CD[7:0]` byte lane. |
| **Pin 75** | `Z80_MREQ_N` | **`M_UB_N`** | Output | **SRAM Upper Byte Enable:** Controls `CD[15:8]` byte lane. |

#### Rationales:
1. **Dropping `Z80_A[15:8]`:** The Z80 I/O port instructions (`IN`/`OUT`) place the 8-bit port address (`0x70`/`0x71`) solely onto `A[7:0]`. Upper address lines `A[15:8]` are not decoded for I/O and are completely redundant for a dedicated coprocessor.
2. **Dropping `CLK_SPD`:** With runtime memory running 100% out of 12ns SRAM, dynamic wait-state switching is eliminated.
3. **Dropping `Z80_MREQ_N`:** Port decoding uses `Z80_IORQ_N` and `Z80_M1_N`. Interrupt Acknowledge (`INTACK`) on the Z80 is uniquely identified by `!Z80_M1_N && !Z80_IORQ_N` (where `Z80_MREQ_N` remains inactive high). `Z80_MREQ_N` is completely unused.

---

### 8.2 Fixed 3-Cycle Flash Access Timing

During reset boot, the CPLD fetches from the `SST39SF040` Flash using a hardcoded **3-cycle wait period**:
* **At 40 MHz ($25\text{ ns}$ cycle):** $3 \times 25\text{ ns} = \mathbf{75\text{ ns}}$, satisfying the 55ns / 70ns Flash access time ($t_{\text{ACC}}$).
* **At 20 MHz ($50\text{ ns}$ cycle):** $3 \times 50\text{ ns} = \mathbf{150\text{ ns}}$, offering even wider margin.
* Because Flash is accessed **only once during the initial 0.84 ms boot copy** and permanently disabled (`F_CE_N = 1`) thereafter, a fixed 3-cycle delay is universally compatible with both 20 MHz and 40 MHz clock modules.

---

### 8.3 16-Bit SRAM Subsystem (`IS61C3216AL-12TLI`)

* **Device:** ISSI `IS61C3216AL-12TLI` (32K $\times$ 16, 12ns access, 5.0V TTL/CMOS, TSOP-II-44).
* **Bus Wiring:**
  * Address: `CA[14:0]` drives `A[14:0]`.
  * Data: `CD[15:0]` drives `I/O[15:0]`.
  * Strobes: `C_OE_N` drives `~OE`, `C_WE_N` drives `~WE`.
  * Chip Enable: `M_CE_N` drives `~CE` (or `~CE` tied to GND).
  * Byte Enables: `M_LB_N` drives `~LB`, `M_UB_N` drives `~UB`.
* **Byte vs. Word Operation:**
  * **16-Bit Microcode Fetch / QS Lookup:** Assert `M_LB_N = 0` and `M_UB_N = 0` (1 single clock cycle).
  * **8-Bit Stack Push / Scratchpad Byte Access:** Assert `M_LB_N = 0, M_UB_N = 1` (even bytes) or `M_LB_N = 1, M_UB_N = 0` (odd bytes). Eliminates read-modify-write hazards.

---

### 8.4 Flash ROM Subsystem (`SST39SF040`)

* **Bus Wiring:**
  * Address: `CA[14:0]` drives `A[14:0]` (higher Flash address pins tied to GND).
  * Data: Connects exclusively to `CD[7:0]` (lower data byte).
  * Chip Enable: `F_CE_N` driven by CPLD Pin 68.
  * Write Enable (`WE_N`): Tie permanently to $V_{CC}$ (or via jumper). Because Flash is programmed off-board and only read during boot, pulling `WE_N` high prevents any risk of accidental write cycles from shared `C_WE_N` strobes.

---

### 8.5 Additional KiCad PCB & Netlist Recommendations for CPU Rev C3

1. **High-Speed Decoupling on TSOP-44 SRAM:**
   * Switching 16 data lines simultaneously at 40 MHz generates significant transient current ($di/dt$).
   * Place a low-ESR $0.1\ \mu\text{F}$ ceramic capacitor in parallel with a $1.0\ \mu\text{F}$ ceramic capacitor as close as physically possible to the $V_{DD}$ and $GND$ pins of the TSOP-II footprint.
2. **Flash `WE_N` Pull-Up:**
   * Tie Flash `WE_N` to $V_{CC}$ with a 10kΩ pull-up resistor. This decouples `C_WE_N` from the Flash completely.
3. **Pull-Up Resistors on Open-Drain Outputs:**
   * Ensure `Z80_WAIT_N` (Pin 70) and `Z80_INT_N` (Pin 69) have suitable pull-ups (e.g., 2.2kΩ to 4.7kΩ) either on-board or via the Zx50 backplane.
4. **Clock Routing:**
   * `MCLK` (40 MHz) must connect to CPLD Global Clock Pin `GCLK1` (Pin 83).
   * `ZCLK` (5/10 MHz) must connect to CPLD Global Clock Pin `GCLK2` (Pin 2).
5. **ATF1508AS JTAG Header:**
   * Retain the dedicated 10-pin or 6-pin Atmel JTAG header (`TCK`, `TDI`, `TDO`, `TMS`, $V_{CC}$, $GND$) with 10kΩ pull-up on `TMS` and `TDI`, and pull-down on `TCK` for reliable in-system reprogramming.
