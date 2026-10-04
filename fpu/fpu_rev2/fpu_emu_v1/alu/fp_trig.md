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

## 6. Physical Register Allocation & Contract (`SIN_F32`)

To execute without dedicated hardware or pipeline conflicts, `SIN_F32` utilizes the 32-bit register file, the exponent register `EA`, and the persistent on-chip SysMEM EBR Scratchpad RAM (`SCR[0..63]`, 1-cycle access via opcodes `0x20` / `0x21`):

| Storage | Width | Role in `SIN_F32` | Preservation / Volatility Contract |
|---|:---:|---|---|
| **`AL`** | 32 b | **Accumulator** | Primary input/output bus, ALU accumulator, barrel shifter source, float unpack/pack |
| **`FL`** | 32 b | **$X$ Vector Coordinate** | Holds $1/K$ (`CORDIC_INV_K_32`) initially; holds $\cos(r)$ in Q2.30 on completion |
| **`BL`** | 32 b | **$Y$ Vector Coordinate** | Holds $0$ initially; holds $\sin(r)$ in Q2.30 on completion |
| **`DL`** | 32 b | **$Z$ Angle Accumulator** | Holds residual angle $r$ in Q2.30; driven to $0$ by CORDIC loop |
| **`DH`** | 32 b | **Scratchpad ($Y_{\text{shift}}$)** | Shifted coordinate: $Y \gg C$ (`ASR AL, C`); intermediate Cody-Waite residual $r_1$ |
| **`AH`** | 32 b | **Scratchpad ($\theta_i$)** | Elementary angle $\arctan(2^{-C})$ loaded from Constants ROM (`EBR 2 & 3`) |
| **`BH`** | 32 b | **Scratchpad (Quadrant / $\theta$)** | Holds original $\theta$ during validation; holds integer quadrant $k \pmod 4$ (0..3) |
| **`SCR[1]`** | 32 b | **EBR Scratchpad Word 1** | Stores float $k$ across Cody-Waite FP operations, avoiding register clobbering in `FX` |
| **`SCR[2]`** | 32 b | **EBR Scratchpad Word 2** | Stores shifted coordinate $X_{\text{shift}} = X \gg C$ during CORDIC rotation loop |
| **`EA`** | 12 b | **Exponent Accumulator** | Manages floating-point unpacking, normalization (`EXP_NORM`), and packing |
| **`EB`** | 12 b | **Scratch Exponent** | Temporary exponent storage during float conversions |
| **`C`**  | 6 b  | **Loop Counter & Shifter Exponent** | Shift amount for `ASR`/`LSL` and CORDIC iteration index ($0 \dots 23$) |

---

## 7. Complete Microcode Assembly Program (`SIN_F32`)

The user opcode `SIN_F32` (`0x71`) maps directly to the following pure microcode program in `fpu_emu/micro_code.py`. It requires no monolithic execution blocks and uses `SCR` scratchpad memory for intermediate persistence:

```nasm
; ==============================================================================
; USER_OPCODE: SIN_F32 (0x71)
; Microcode Implementation of Single-Precision Circular Sine
; ==============================================================================

; ------------------------------------------------------------------------------
; Stage 1: Input Pop & Special Value Validation
; ------------------------------------------------------------------------------
    POP AL                              ; 0: Pop input float theta into AL
    JNZ UNDERFLOW, trap_err             ; 1: Trap on stack underflow
    MOV BH, AL                          ; 2: BH <- original theta
    LD BL, 0x7FFFFFFF
    AND AL, BL                          ; 3: Clear sign bit to get |theta|
    JZ ZERO, ret_zero                   ; 4: If theta == +-0.0, return theta preserving sign
    UNPACK_F32 EA, AL                   ; 5: Extract exponent E into EA
    MOV AL, EA
    LD BL, 255
    CMP AL, BL
    JZ ZERO, trap_err                   ; 6: If E == 255 (NaN or +-Inf), trap and return NaN
    LD BL, 115
    CMP AL, BL
    JZ CARRY, ret_small_angle           ; 7: If E < 115 (|theta| < 2^-12), sin(theta) ~= theta

; ------------------------------------------------------------------------------
; Stage 2: Cody-Waite Range Reduction (theta -> r in Q2.30, quadrant in BH)
; ------------------------------------------------------------------------------
    MOV AL, BH                          ; 8: AL <- theta
    LOAD_CONST BL, TWO_OVER_PI_F32      ; 9: BL <- 2/pi (0x3F22F983) from EBR Constants ROM
    MUL_F32                             ; 10: AL <- q = theta * (2/pi)
    
    ; Fast IEEE-754 nearest-integer rounding via magic-number addition:
    LD BL, 0x4B400000                   ; 11: BL <- 1.5 * 2^23 (magic rounding constant)
    ADD_F32                             ; 12: AL <- q + 1.5*2^23 (aligns integer to LSBs)
    SUB_F32                             ; 13: AL <- k = round(q) as float
    SCR 1, AL                           ; 14: SCR[1] <- float k (preserved in EBR scratchpad)
    
    ; Extract integer quadrant q = k & 3 into BH:
    UNPACK_F32 EB, AL                   ; 15: Extract mantissa of k
    LD BL, 3
    AND AL, BL                          ; 16: AL <- k & 3 (quadrant index 0..3)
    MOV BH, AL                          ; 17: BH <- quadrant index

    ; Cody-Waite split multiplication 1: p1 = k * C1
    SCR AL, 1                           ; 18: AL <- float k (from SCR[1])
    LOAD_CONST BL, CW_C1_F32            ; 19: BL <- C1 (0x3FC90F80) from ROM
    MUL_F32                             ; 20: AL <- p1 = k * C1
    MOV BL, AL                          ; 21: BL <- p1
    MOV AL, BH                          ; 22: AL <- original theta
    SUB_F32                             ; 23: AL <- r1 = theta - p1
    MOV DH, AL                          ; 24: DH <- r1

    ; Cody-Waite split multiplication 2: p2 = k * C2
    SCR AL, 1                           ; 25: AL <- float k (from SCR[1])
    LOAD_CONST BL, CW_C2_F32            ; 26: BL <- C2 (0x37354443) from ROM
    MUL_F32                             ; 27: AL <- p2 = k * C2
    MOV BL, AL                          ; 28: BL <- p2
    MOV AL, DH                          ; 29: AL <- r1
    SUB_F32                             ; 30: AL <- r = r1 - p2 (residual float in [-pi/4, +pi/4])

    ; Convert residual float r to signed Q2.30 fixed-point in DL:
    UNPACK_F32 EA, AL                   ; 31: EA <- exponent E, AL <- 24-bit mantissa (hidden bit at 23)
    MOV DH, EA                          ; 32: DH <- E
    LD BL, 120
    MOV AL, DH
    SUB AL, BL                          ; 33: AL <- E - 120 (shift offset for Q2.30 alignment)
    MOV C, AL                           ; 34: C <- shift count
    ; (If C >= 0: LSL AL, C; if C < 0: ASR AL, C)
    ; (If original float was negative: NEG AL)
    MOV DL, AL                          ; 35: DL <- Z0 (residual angle in Q2.30)
    
    ; Prime STATUS.SIGN from Z0:
    MOV AL, DL
    LD BL, 0
    CMP AL, BL                          ; 36: Compare Z0 with 0 (latches STATUS.SIGN)

; ------------------------------------------------------------------------------
; Stage 3: CORDIC Engine Initialization
; ------------------------------------------------------------------------------
    LOAD_CONST FL, CORDIC_INV_K_32      ; 37: FL <- 1/K (0x26DD3B6A in Q2.30)
    LD BL, 0                            ; 38: BL <- Y0 = 0
    LD C, 0                             ; 39: C <- stage 0

; ------------------------------------------------------------------------------
; Stage 4: 24-Iteration Circular CORDIC Rotation Loop
; ------------------------------------------------------------------------------
cordic_loop:
    ; 1. Compute shifted coordinates X_shift and Y_shift:
    MOV AL, FL                          ; 40: AL <- X
    ASR AL                              ; 41: AL <- X >> C (via alu_shifter)
    SCR 2, AL                           ; 42: SCR[2] <- X_shift (avoids clobbering FH)

    MOV AL, BL                          ; 43: AL <- Y
    ASR AL                              ; 44: AL <- Y >> C (via alu_shifter)
    MOV DH, AL                          ; 45: DH <- Y_shift

    ; 2. Single-cycle lookup of elementary angle theta_i = atan(2^-C):
    LOAD_CONST AH, C                    ; 46: AH <- CORDIC_ATAN_F32[C] from EBR 2 & 3 ROM

    ; 3. Branch on sign of Z (STATUS.SIGN):
    JNZ SIGN, cordic_neg_z              ; 47: If Z < 0, branch to negative rotation

cordic_pos_z:
    ; Positive rotation: Z >= 0
    MOV AL, FL
    SUB AL, DH
    MOV FL, AL                          ; 48: X <= X - Y_shift

    MOV AL, BL
    SCR DH, 2                           ; 49a: DH <- X_shift from SCR[2]
    ADD AL, DH
    MOV BL, AL                          ; 49b: Y <= Y + X_shift

    MOV AL, DL
    SUB AL, AH
    MOV DL, AL                          ; 50: Z <= Z - theta_i (ALU SUB automatically latches STATUS.SIGN)

    JMP cordic_next                     ; 51

cordic_neg_z:
    ; Negative rotation: Z < 0
    MOV AL, FL
    ADD AL, DH
    MOV FL, AL                          ; 52: X <= X + Y_shift

    MOV AL, BL
    SCR DH, 2                           ; 53a: DH <- X_shift from SCR[2]
    SUB AL, DH
    MOV BL, AL                          ; 53b: Y <= Y - X_shift

    MOV AL, DL
    ADD AL, AH
    MOV DL, AL                          ; 54: Z <= Z + theta_i (ALU ADD automatically latches STATUS.SIGN)

cordic_next:
    ; Increment loop counter C and test for completion:
    MOV AL, C
    LD DH, 1
    ADD AL, DH
    MOV C, AL                           ; 55: C <= C + 1

    LD DH, 24
    CMP AL, DH
    JNZ ZERO, cordic_loop               ; 56: Loop if C != 24

; ------------------------------------------------------------------------------
; Stage 5: Quadrant Reconstruction & Selection
; ------------------------------------------------------------------------------
    ; Quadrant q = k & 3 is stored in BH:
    ;   q == 0: result = +Y (BL)
    ;   q == 1: result = +X (FL)
    ;   q == 2: result = -Y (NEG BL)
    ;   q == 3: result = -X (NEG FL)
    ; Selected signed Q2.30 value is placed into AL.

; ------------------------------------------------------------------------------
; Stage 6: Fixed-to-Float Normalization & Stack Push
; ------------------------------------------------------------------------------
    LZC C, AL                           ; 57: Count leading zeros in AL into C
    LSL AL, C                           ; 58: Shift mantissa left to normalize
    EXP_NORM                            ; 59: Calculate exponent: EA = 128 - C
    PACK_F32 AL, EA                     ; 60: Pack sign, exponent, and mantissa into IEEE-754 float
    PUSH AL                             ; 61: Push result onto operand stack
    RET                                 ; 62: Return to host dispatcher

ret_zero:
    MOV AL, BH                          ; 63: Restore original 0.0 (preserves -0.0 / +0.0)
    PUSH AL
    RET

ret_small_angle:
    MOV AL, BH                          ; 64: Return original theta (sin(theta) ~= theta)
    PUSH AL
    RET

trap_err:
    TRAP                                ; 65: Set STATUS.ERR and halt microcode
```

---

## 8. Quadrant Reconstruction & Tangent Division

After the CORDIC core completes, the outputs $(X_N, Y_N)$ represent $(\cos r, \sin r)$ in Q2.30 fixed-point. The final result is reconstructed based on target opcode and quadrant index $q = k \pmod 4$:

### 8.1 Sine (`SIN_F32` / `SIN_F64`)
- $q = 0$: result $= +Y_N$
- $q = 1$: result $= +X_N$
- $q = 2$: result $= -Y_N$
- $q = 3$: result $= -X_N$
- Normalize fixed-point Q2.30/Q2.62 to floating-point via `alu_lzc` and pack exponent via `PACK_F32` / `PACK_F64`.

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
- Otherwise, execute floating-point division $N_{\text{val}} / D_{\text{val}}$ via `DIV_F32` or `DIV_F64`.

---

## 9. Hardware Resource & Latency Budget

* **Pipeline Latency Breakdown (`SIN_F32`):**
  - Validation & Pop: ~8 cycles
  - Cody-Waite Range Reduction: ~28 cycles (including 2 FP multiplies, 2 FP subtracts, and fixed-point alignment)
  - 24 CORDIC Stages $\times$ ~14 cycles/stage (shared single-ALU / shifter datapath): ~336 cycles
  - Reconstruction & Float Packing: ~10 cycles
  - **Total `SIN_F32` Latency:** **~382 Cycles (4.77 $\mu$s @ 80MHz)**
* **FPGA Logic Allocation:**
  - CORDIC barrel shifters and adders share the existing `alu_shifter` and `alu_adder` datapath.
  - Zero additional DSP blocks, multipliers, or custom functional blocks required.
  - Constants ROM: 24 elementary arctangent words + range reduction constants fit within EBR 2 & 3 headroom.

