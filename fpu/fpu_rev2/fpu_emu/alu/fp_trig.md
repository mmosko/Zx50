# Floating-Point Trigonometric ALU Module (`alu/fp_trig.md`)

This document specifies the micro-architecture, mathematical theory, range reduction, CORDIC execution engine, register contracts, and microcode mapping for trigonometric operations in the **Zx50 FPU Rev 2**.

- **High-Level Coprocessor Architecture:** [FPU_REV2.md](../../FPU_REV2.md)
- **Low-Level Micro-Architecture:** [SystemDesign.md](../../SystemDesign.md)
- **Z80 Host Programming Guide:** [ProgrammersGuide.md](../../ProgrammersGuide.md)
- **Development Roadmap:** [TODO.md](../../TODO.md)

---

## 1. Scope & Operations Supported

The trigonometric ALU subsystem provides hardware-accelerated computation of circular functions for IEEE-754 Single-Precision (`f32`) and Double-Precision (`f64`) floating-point formats:

| User Opcode | Hex | Mnemonic | Precision | Input | Output | Latency (@80MHz) |
|---|:---:|---|:---:|---|---|:---:|
| `0b0111_0001` | `0x71` | **`SIN_F32`** | `f32` (32-bit) | $\theta$ (radians) | $\sin(\theta)$ | ~36 Cycles (450 ns) |
| `0b0111_0011` | `0x73` | **`SIN_F64`** | `f64` (64-bit) | $\theta$ (radians) | $\sin(\theta)$ | ~64 Cycles (800 ns) |
| `0b0111_1001` | `0x79` | **`COS_F32`** | `f32` (32-bit) | $\theta$ (radians) | $\cos(\theta)$ | ~36 Cycles (450 ns) |
| `0b0111_1011` | `0x7B` | **`COS_F64`** | `f64` (64-bit) | $\theta$ (radians) | $\cos(\theta)$ | ~64 Cycles (800 ns) |
| `0b1000_0001` | `0x81` | **`TAN_F32`** | `f32` (32-bit) | $\theta$ (radians) | $\tan(\theta)$ | ~52 Cycles (650 ns) |
| `0b1000_0011` | `0x83` | **`TAN_F64`** | `f64` (64-bit) | $\theta$ (radians) | $\tan(\theta)$ | ~90 Cycles (1.1 $\mu$s)|

### Architectural Mandate
Per `fpu_emu/agents.md`:
* **Zero Python `math` module in algorithm paths.**
* **Zero high-level arithmetic (`*`, `/`, `//`, `%`, `**`) in algorithm paths.**
* All range reduction, shift-and-add rotations, angle additions, and conversions must execute strictly using synthesizable ALU primitives, register transfers, and ROM lookups.

---

## 2. Mathematical Principles: Circular CORDIC

The trigonometric functions are evaluated using the **CORDIC (Coordinate Rotation DIgital Computer)** algorithm in **Circular Vectoring/Rotation Mode** with $Z \to 0$.

### 2.1 Rotation Equations
Starting with an initial planar vector $(X_0, Y_0)$ and angle accumulator $Z_0$, the vector is rotated through a sequence of elementary angles $\theta_i = \arctan(2^{-i})$ such that the angle accumulator $Z$ is driven toward zero:

$$\begin{aligned}
d_i &= \begin{cases} +1 & \text{if } Z_i \ge 0 \\ -1 & \text{if } Z_i < 0 \end{cases} \\
X_{i+1} &= X_i - d_i \cdot 2^{-i} \cdot Y_i \\
Y_{i+1} &= Y_i + d_i \cdot 2^{-i} \cdot X_i \\
Z_{i+1} &= Z_i - d_i \cdot \theta_i
\end{aligned}$$

Because each elementary rotation increases the vector length by $\sqrt{1 + 2^{-2i}}$, performing $N$ iterations scales the final vector by the cumulative gain $K_N$:

$$K_N = \prod_{i=0}^{N-1} \sqrt{1 + 2^{-2i}}$$

For $N \ge 24$, $K_N$ converges to the CORDIC constant:
$$K \approx 1.646760258121065648366...$$

To produce unit-magnitude trigonometric outputs, the initial $X_0$ coordinate is pre-scaled by the reciprocal gain $1/K$:
$$X_0 = \frac{1}{K} \approx 0.6072529350088812561694467...$$
$$Y_0 = 0$$
$$Z_0 = \theta_{\text{reduced}}$$

Upon completion of $N$ iterations ($Z_N \approx 0$):
$$\begin{aligned}
X_N &= \cos(\theta_{\text{reduced}}) \\
Y_N &= \sin(\theta_{\text{reduced}}) \\
\tan(\theta_{\text{reduced}}) &= \frac{Y_N}{X_N} = \frac{\sin(\theta_{\text{reduced}})}{\cos(\theta_{\text{reduced}})}
\end{aligned}$$

---

## 3. Fixed-Point Formats & Constant Representations

To maintain full floating-point precision throughout the CORDIC rotation loop:

### 3.1 32-Bit Single Precision (`f32`)
* **Mantissa Precision:** 24 bits (23 explicit + 1 hidden bit).
* **CORDIC Datapath Format:** **Q2.30** signed fixed-point (2 integer bits, 30 fractional bits) in 32-bit registers.
  * Range: $[-2.0, +2.0)$.
  * 1 unit in the last place (ULP) $\approx 2^{-30} \approx 9.31 \times 10^{-10}$.
* **Iteration Count:** $N = 24$ rotation stages ($i = 0 \dots 23$).
* **CORDIC Scale Constant ($1/K$):**
  $$1/K \times 2^{30} = 652032874 \implies \text{Hex: } \mathbf{\text{0x26DD3B6A}}$$
* **Angle Units:** Radians in **Q2.30** format.
  * $\pi/2 \times 2^{30} = 1686629713 \implies \text{Hex: } \mathbf{\text{0x6487ED51}}$
  * $\pi/4 \times 2^{30} = 843314857 \implies \text{Hex: } \mathbf{\text{0x3243F6A9}}$

### 3.2 64-Bit Double Precision (`f64`)
* **Mantissa Precision:** 53 bits (52 explicit + 1 hidden bit).
* **CORDIC Datapath Format:** **Q2.62** signed fixed-point (2 integer bits, 62 fractional bits) in 64-bit paired registers (`{AH, AL}`).
  * 1 ULP $\approx 2^{-62} \approx 2.17 \times 10^{-19}$.
* **Iteration Count:** $N = 53$ rotation stages ($i = 0 \dots 52$).
* **CORDIC Scale Constant ($1/K$):**
  $$1/K \times 2^{62} = 2800454378170275817 \implies \text{Hex: } \mathbf{\text{0x26DD3B6A\_6F0CE559}}$$
* **Angle Units:** Radians in **Q2.62** format.
  * $\pi/2 \times 2^{62} = 7244019458077122842 \implies \text{Hex: } \mathbf{\text{0x6487ED51\_10B4611A}}$

---

## 4. Range Reduction & Quadrant Mapping

The basic CORDIC circular rotation algorithm converges strictly for $|Z_0| \le \theta_{\max} \approx 1.743$ radians ($\approx 99.88^\circ$). Input angles $\theta \in (-\infty, +\infty)$ must therefore be reduced to the primary range $[-\pi/4, +\pi/4]$ or $[0, \pi/2]$.

### 4.1 Range Reduction Modulo $\pi/2$
Any input angle $\theta$ can be expressed as:
$$\theta = k \cdot \frac{\pi}{2} + r$$
where $k = \lfloor \theta / (\pi/2) + 0.5 \rfloor \in \mathbb{Z}$ and residual angle $r \in [-\pi/4, +\pi/4]$.

The integer quadrant index $q = k \pmod 4 \in \{0, 1, 2, 3\}$ specifies the trigonometric quadrant:

| Quadrant $q$ | Nominal Range | $\sin(\theta)$ | $\cos(\theta)$ | $\tan(\theta)$ |
|:---:|:---:|:---:|:---:|:---:|
| **0** | $[-\pi/4, +\pi/4]$ | $+\sin(r)$ | $+\cos(r)$ | $+\tan(r)$ |
| **1** | $[\pi/4, 3\pi/4]$ | $+\cos(r)$ | $-\sin(r)$ | $-\cot(r) = -1/\tan(r)$ |
| **2** | $[3\pi/4, 5\pi/4]$ | $-\sin(r)$ | $-\cos(r)$ | $+\tan(r)$ |
| **3** | $[5\pi/4, 7\pi/4]$ | $-\cos(r)$ | $+\sin(r)$ | $-\cot(r) = -1/\tan(r)$ |

### 4.2 Algorithm Steps for Range Reduction
1. **Unpack Floating-Point Input:** Extract sign $S$, exponent $E$, and mantissa $M$ into register pair `{EA, AL}` (or `{EA, AX}`).
2. **Domain & Special Value Validation:**
   - If $\theta = \pm 0.0$: return $\sin(\pm 0) = \pm 0.0$, $\cos(0) = 1.0$, $\tan(\pm 0) = \pm 0.0$.
   - If $\theta$ is $\pm\infty$ or $\text{NaN}$: set $ERR \leftarrow 1$, return $\text{NaN}$ (`0x7FC00000` / `0x7FF8000000000000`).
   - If $|\theta| < 2^{-12}$ (for `f32`) or $< 2^{-27}$ (for `f64`):
     - $\sin(\theta) \approx \theta$
     - $\cos(\theta) \approx 1.0$
     - $\tan(\theta) \approx \theta$
3. **Integer Quadrant Calculation:**
   - Multiply $|\theta| \times (2/\pi)$ using synthesizable Booth multiplication / fixed-point division to obtain integer quotient $k$ and fractional remainder $f \in [0.0, 1.0)$.
   - Compute residual angle $r = f \times (\pi/2)$.
   - Adjust for initial sign: if $\theta < 0$, $k \leftarrow -k$, $r \leftarrow -r$.
4. **Convert Residual to Fixed-Point Q2.30 / Q2.62:**
   - Load $Z_0 \leftarrow r_{\text{fixed}}$.

---

## 5. CORDIC Elementary Angle ROM Tables

The arctangent angles $\theta_i = \arctan(2^{-i})$ are stored in dedicated on-chip EBR ROM (EBR 2 & 3, Constants ROM).

### 5.1 F32 Arctangent Table (24 Entries, Q2.30)
```text
Table: CORDIC_ATAN_F32 (24 x 32-bit words)
 i   tan(2^-i)   Angle (Radians)     Q2.30 Hex Value
------------------------------------------------------
 0   1.000000    0.785398163         0x3243F6A9  (pi/4)
 1   0.500000    0.463647609         0x1DAC6706
 2   0.250000    0.244978663         0x0FAADDB0
 3   0.125000    0.124354995         0x07F56EA1
 4   0.062500    0.062418810         0x03FEAB77
 5   0.031250    0.031239833         0x01FFD55B
 6   0.015625    0.015623729         0x00FFFAAB
 7   0.007812    0.007812341         0x007FFF55
 8   0.003906    0.003906230         0x003FFFEA
 9   0.001953    0.001953123         0x001FFFFD
10   0.000977    0.000976562         0x000FFFFF
11   0.000488    0.000488281         0x00080000
12   0.000244    0.000244141         0x00040000
13   0.000122    0.000122070         0x00020000
14   0.000061    0.000061035         0x00010000
15   0.000031    0.000030518         0x00008000
16   0.000015    0.000015259         0x00004000
17   0.000008    0.000007629         0x00002000
18   0.000004    0.000003815         0x00001000
19   0.000002    0.000001907         0x00000800
20   0.000001    0.000000954         0x00000400
21   0.000000    0.000000477         0x00000200
22   0.000000    0.000000238         0x00000100
23   0.000000    0.000000119         0x00000080
```
*(Notice that for $i \ge 11$, $\arctan(2^{-i}) \approx 2^{-i}$ to 32-bit precision, collapsing to a single bit).*

---

## 6. Physical Register Mapping & Contract

To prevent clobbering registers during multi-word execution, the CORDIC engine adheres strictly to the register contract defined in `SystemDesign.md §2.3`:

| Register | Width | CORDIC Role | Preservation / Volatility Contract |
|---|:---:|---|---|
| **`AX`** (`{AH, AL}`) | 64 / 32 b | **$X$ Vector Coordinate** | Holds $1/K$ initially; holds $\cos(r)$ on return. |
| **`BX`** (`{BH, BL}`) | 64 / 32 b | **$Y$ Vector Coordinate** | Holds $0$ initially; holds $\sin(r)$ on return. |
| **`DX`** (`{DH, DL}`) | 64 / 32 b | **$Z$ Angle Accumulator** | Holds residual angle $r$; driven to $0$ by CORDIC loop. |
| **`FX`** (`{FH, FL}`) | 64 / 32 b | **Scratchpad Staging** | Used for shifted values ($X \gg i$, $Y \gg i$) and ROM table loads. |
| **`EA`** | 12 b | **Exponent Accumulator** | Manages floating-point unpacking and packing exponents. |
| **`C`** | 6 b | **Iteration Counter** | Loop counter: initialized to $0$, increments up to $N-1$. |

---

## 7. Detailed Step-by-Step CORDIC Core Loop

```text
================================================================================
Algorithm: CORDIC_CORE_F32 (AX = X, BX = Y, DX = Z)
================================================================================
Inputs:
  AX <- 0x26DD3B6A (1/K in Q2.30)
  BX <- 0x00000000 (0 in Q2.30)
  DX <- residual angle r in Q2.30
  C  <- 0

For stage i = 0 to 23:
  1. Test Sign of DX (Z):
     d = (DX >= 0) ? +1 : -1

  2. Compute Shifted Operands (via alu_shifter):
     X_shift = ASR(AX, i)
     Y_shift = ASR(BX, i)

  3. Load Elementary Angle from ROM:
     theta_i = CORDIC_ATAN_F32[i]

  4. Parallel or 3-step Register Update (via alu_adder):
     If d == +1:
       AX <= AX - Y_shift
       BX <= BX + X_shift
       DX <= DX - theta_i
     Else:
       AX <= AX + Y_shift
       BX <= BX - X_shift
       DX <= DX + theta_i

  5. C <= C + 1
End For

Outputs:
  AX holds cos(r) in Q2.30
  BX holds sin(r) in Q2.30
```

---

## 8. Quadrant Reconstruction & Tangent Division

After the CORDIC core completes, the outputs $(X_N, Y_N)$ represent $(\cos r, \sin r)$. The final result is reconstructed based on target opcode and quadrant index $q = k \pmod 4$:

### 8.1 Sine (`SIN_F32` / `SIN_F64`)
- $q = 0$: result $= +Y_N$
- $q = 1$: result $= +X_N$
- $q = 2$: result $= -Y_N$
- $q = 3$: result $= -X_N$
- Normalize fixed-point Q2.30/Q2.62 to floating-point via `alu_lzc` and pack exponent via `pack_f32` / `pack_f64`.

### 8.2 Cosine (`COS_F32` / `COS_F64`)
- $q = 0$: result $= +X_N$
- $q = 1$: result $= -Y_N$
- $q = 2$: result $= -X_N$
- $q = 3$: result $= +Y_N$
- Normalize and pack.

### 8.3 Tangent (`TAN_F32` / `TAN_F64`)
- Compute numerator $N_{\text{val}}$ and denominator $D_{\text{val}}$ from $(X_N, Y_N)$ according to quadrant $q$.
- **Asymptote Overflow Check:** If $|D_{\text{val}}| == 0$ or $|N_{\text{val}} / D_{\text{val}}|$ exceeds maximum representable float:
  - Set `STATUS.OVERFLOW = 1`, `STATUS.ERR = 1`.
  - Return signed infinity ($\pm \infty$).
- Otherwise, execute floating-point division $N_{\text{val}} / D_{\text{val}}$ via `div_f32` or `div_f64`.

---

## 9. Hardware Resource & Latency Budget

* **Pipeline Latency:**
  - Range Reduction: ~6 cycles
  - 24 CORDIC Stages $\times$ 1 cycle/stage (pipelined) or 2 cycles/stage (shared adder): ~24–28 cycles
  - Quadrant Reconstruction & Normalization: ~4 cycles
  - **Total `SIN_F32` / `COS_F32` Latency:** **~36 Cycles (450 ns @ 80MHz)**
  - **Total `TAN_F32` Latency:** **~52 Cycles (650 ns @ 80MHz)** (includes 16-cycle FP divide)
* **FPGA Logic Allocation:**
  - CORDIC barrel shifters and adders share the existing `alu_shifter` and `alu_adder` datapath.
  - Zero additional DSP blocks or multipliers required for circular rotation.
  - ROM table: 24 words $\times$ 32 bits = 96 bytes (comfortably fits in EBR 2 & 3 constants headroom).
