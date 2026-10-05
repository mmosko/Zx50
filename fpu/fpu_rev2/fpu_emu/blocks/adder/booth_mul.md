# Radix-4 Modified Booth Multiplier Architecture & Design Plan

## 1. Overview & Z80 Clock Domain Context

The Zx50 FPU Rev2 features a hardware **Radix-4 Modified Booth Multiplier** co-located with the Adder Block.

### Clock Domain Ratios
- **FPGA Frequency:** 80 MHz – 120 MHz ($\approx 8.3 \text{ ns} - 12.5 \text{ ns}$ cycle time).
- **Z80 Frequency:** 4 MHz – 10 MHz ($\approx 100 \text{ ns} - 250 \text{ ns}$ clock; $4 \text{ T-states} \approx 400 \text{ ns} - 1000 \text{ ns}$ per M-cycle, or $\approx 2.25 \text{ MHz}$ effective instruction cycle).
- **Ratio:** 1 Z80 machine cycle corresponds to **30 – 50 FPGA clock cycles**.
- Even a 16-cycle or 32-cycle multi-cycle operation in the FPGA completes within **barely 1 to 2 Z80 bus cycles**, making multi-cycle FPGA execution virtually instantaneous from the perspective of the host CPU.

---

## 2. Multiplier Requirements & Stack Semantics

| Operation | Inputs | Product Width (Internal) | Stack Result Width | Multiplier Mode | Execution Strategy |
|---|---|:---:|:---:|---|---|
| **`MUL_I32`** | 32-bit signed $\times$ 32-bit signed | 64 bits | **32 bits** (`AL`) + `VF` | Signed (`MUL`) | 16-cycle single pass $\to$ $\{AH, AL\}$. Pops 2 words, pushes `AL`. `VF=1` on overflow. |
| **`MUL_F32`** | 24-bit mantissa $\times$ 24-bit mantissa | 48 bits | **32 bits** (IEEE-754) | Unsigned (`MULU`) | Single pass using 32-bit unsigned multiplier. Fits in 64 bits. Normalizes mantissa & adjusts exp. |
| **`MUL_I64`** | 64-bit signed $\times$ 64-bit signed | 128 bits | **64 bits** (`AX`) + `VF` | Unsigned (`MULU`) | Microcode cross-products $\to$ `ADD`/`ADC` sum $\to$ pushes 64-bit result. `VF=1` if true product $> 2^{63}-1$ or $< -2^{63}$. |
| **`MUL_F64`** | 53-bit mantissa $\times$ 53-bit mantissa | 106 bits | **64 bits** (IEEE-754) | Unsigned (`MULU`) | Split 53-bit mantissas into 32-bit LO and 21-bit HI $\to$ 4 unsigned $32 \times 32 \to 64$ passes $\to$ `ADD`/`ADC` accumulation. |

### Stack Invariants & Widening Multiplication ($32 \times 32 \to 64$)
* **Stack Invariant:** Binary arithmetic operations are stack-neutral: `( a: i32, b: i32 -- res: i32 )` and `( a: i64, b: i64 -- res: i64 )`. This prevents type proliferation and maintains Forth RPN composability.
* **Widening Multiplication:** When a non-truncated 64-bit product of two 32-bit operands is required:
  - **Signed:** Convert both operands with `CONV_I32_I64` ($0xC8$) and execute `MUL_I64` ($0x12$).
  - **Unsigned:** Convert both operands with `CONV_U32_U64` ($0xC2$) and execute `MUL_I64` ($0x12$).

---

## 3. 32-Bit Multiplier Core Architecture (`BoothMulCore`)

### Datapath Specification
- **Inputs:**
  - $Q$ (Multiplier): 32 bits from `HA_MUX` (typically register `AL`).
  - $M$ (Multiplicand): 32 bits from `HB_MUX` (any register in `HB_MUX`).
  - `signed: bool`: Selects signed vs. unsigned operation.
- **Outputs (`BoothMulResult`):**
  - `res`: 8 bytes (`bytearray`) in Little-Endian format (bytes 0..3: low 32 bits, bytes 4..7: high 32 bits).
  - `cf`: `False` (always cleared).
  - `zf`: `True` if entire 64-bit product is zero.
  - `sf`: `True` if MSB of product (bit 63) is 1.
  - `vf`: Signed overflow flag (for signed: high 32 bits $\neq$ sign extension of low 32 bits; for unsigned: high 32 bits $\neq 0$).

### Mathematical Algorithm: Unified Radix-4 Booth (Signed & Unsigned)
1. **Multiplicand Setup:**
   - Signed mode: $M$ is interpreted as 32-bit two's complement ($[-2^{31}, 2^{31}-1]$).
   - Unsigned mode: $M$ is interpreted as unsigned 32-bit ($[0, 2^{32}-1]$) with bit 32 = 0.
2. **16-Step Radix-4 Iterations:**
   - Window: $\{Q_{2k+1}, Q_{2k}, q_{-1}\}$ with $q_{-1} = 0$ initially.
   - Operations on accumulator $P$:
     - $0b000 \to +0$
     - $0b001, 0b010 \to +M$
     - $0b011 \to +2M$
     - $0b100 \to -2M$
     - $0b101, 0b110 \to -M$
     - $0b111 \to +0$
   - Combined arithmetic right shift $\{P, Q\} \gg 2$.
3. **Unsigned Post-Correction:**
   - If `signed == False` and $Q_{\text{orig}}[31] == 1$:
     $$P = (P + M) \pmod{2^{32}}$$
   - Cancels out the $-2^{31} \cdot M$ weight from Booth recoding, seamlessly producing the exact unsigned product.

---

## 4. Hardware Resource Budget (MachXO2-2000HC)

- **Shift Register $\{P[32:0], Q[31:0], q_{-1}\}$:** 66 FFs
- **CCU2C Fast Carry Adder (34-bit):** 17 slices
- **Booth Recoder & 5:1 MUX Logic:** ~57 LUT4s
- **Output MUX:** 16 LUT4s
- **Total FPGA Cost:** ~77 LUT4s, 17 CCU2C slices, 75 FFs (3.6% of LUTs, 1.6% of slices, 3.5% of FFs).
- **Execution Latency:** 16 clock cycles.

---

## 5. Division (DIV) Consideration

- Integer and floating-point division (`DIV_I32`, `DIV_I64`, `DIV_F32`, `DIV_F64`) will be implemented as a separate non-restoring / SRT digit recurrence divider or through Newton-Raphson iterations using the multiplier.
- Having clean signed and unsigned modes in `BoothMulCore` directly facilitates reciprocal multiplication ($A / B = A \times (1/B)$) if desired.
