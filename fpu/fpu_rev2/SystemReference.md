# Microcode Instruction Reference Manual

### Block 0 (0b000): Arithmetic / Adder Block

```
================================================================================
ADD dst, src / ADD AX, src — ADD REGISTER TO ACCUMULATOR
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  X  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if unsigned carry out occurred ($sum > 2^{32}-1$ or $2^{64}-1$); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31:0] <- AL [31:0] + src [31:0]
    UPC       <- UPC + 1
else:
    Cycle 1: AL [31:0] <- AL [31:0] + src_L [31:0], latch Carry_out
    Cycle 2: AH [31:0] <- AH [31:0] + src_H [31:0] + Carry_in
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Adds the contents of `src` to accumulator `dst` (`AL` or `AX`) using `alu_adder32` with carry chain. When `W = 1`, the operation executes across two consecutive cycles, adding the low halves (`AL + src_L`) in cycle 1 and the high halves with carry (`AH + src_H + C`) in cycle 2.

#### Concrete Numeric Example
```text
Suppose AL = 0x7FFFFFFF, BL = 0x00000001 (W = 0).
After execution of ADD AL, BL:
  AL + BL = 0x7FFFFFFF + 0x00000001 = 0x80000000
  Bit 31 = 1: sets SIGN (S) to 1
  No unsigned carry (0x80000000 <= 0xFFFFFFFF): sets CARRY (C) to 0
  Non-zero result: sets ZERO (Z) to 0
  Positive + Positive = Negative: sets OVERFLOW (V) to 1
```

---

```
================================================================================
ADC dst, src / ADC AX, src — ADD WITH CARRY TO ACCUMULATOR
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  X  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if unsigned carry out occurred; reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31:0] <- AL [31:0] + src [31:0] + STATUS.C
    UPC       <- UPC + 1
else:
    Cycle 1: AL [31:0] <- AL [31:0] + src_L [31:0] + STATUS.C, latch Carry_out
    Cycle 2: AH [31:0] <- AH [31:0] + src_H [31:0] + Carry_in
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Adds the contents of `src` and the carry flag `C` to accumulator `dst`. Used primarily for multi-word synthesis beyond 64 bits.

#### Concrete Numeric Example
```text
Suppose AL = 0x00000001, BL = 0x00000002, STATUS.C = 1.
After execution of ADC AL, BL:
  AL + BL + C = 1 + 2 + 1 = 0x00000004
  Bit 31 = 0: sets SIGN (S) to 0
  No carry: sets CARRY (C) to 0
  Non-zero result: sets ZERO (Z) to 0
  No signed overflow: sets OVERFLOW (V) to 0
```

---

```
================================================================================
SUB dst, src / SUB AX, src — SUBTRACT REGISTER FROM ACCUMULATOR
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  X  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero ($dst == src$); reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred ($dst < src$ unsigned); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31:0] <- AL [31:0] - src [31:0]
    UPC       <- UPC + 1
else:
    Cycle 1: AL [31:0] <- AL [31:0] - src_L [31:0], latch Borrow_out
    Cycle 2: AH [31:0] <- AH [31:0] - src_H [31:0] - Borrow_in
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Subtracts `src` from `dst`. Evaluated as $dst + \overline{src} + 1$ using `alu_adder32` with subtract control asserted. In 64-bit mode (`W = 1`), subtraction proceeds across 2 cycles ($AL - src_L$, then $AH - src_H - \text{Borrow}$).

#### Concrete Numeric Example
```text
Suppose AL = 0x00000005, BL = 0x00000008.
After execution of SUB AL, BL:
  AL - BL = 5 - 8 = -3 = 0xFFFFFFFD
  Bit 31 = 1: sets SIGN (S) to 1
  Borrow occurred (5 < 8): sets CARRY (C) to 1
  Non-zero result: sets ZERO (Z) to 0
  No signed overflow: sets OVERFLOW (V) to 0
```

---

```
================================================================================
SBB dst, src / SBB AX, src — SUBTRACT WITH BORROW FROM ACCUMULATOR
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  X  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred; reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31:0] <- AL [31:0] - src [31:0] - STATUS.C
    UPC       <- UPC + 1
else:
    Cycle 1: AL [31:0] <- AL [31:0] - src_L [31:0] - STATUS.C, latch Borrow_out
    Cycle 2: AH [31:0] <- AH [31:0] - src_H [31:0] - Borrow_in
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000011`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Subtracts `src` and incoming borrow `C` from accumulator `dst`.

#### Concrete Numeric Example
```text
Suppose AL = 0x00000005, BL = 0x00000002, STATUS.C = 1.
After execution of SBB AL, BL:
  AL - BL - C = 5 - 2 - 1 = 0x00000002
  Bit 31 = 0: sets SIGN (S) to 0
  No borrow: sets CARRY (C) to 0
  Non-zero result: sets ZERO (Z) to 0
  No signed overflow: sets OVERFLOW (V) to 0
```

---

```
================================================================================
CMP dst, src / CMP AX, src — COMPARE REGISTER WITH ACCUMULATOR
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  X  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if $dst == src$; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of $(dst - src)$ is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred ($dst < src$ unsigned); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
Discard (dst - src) -> RES_SEL = NONE (no register write)
Update STATUS flags [6:3] <- {Z, S, C, V}
UPC <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000100`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = 0b1111` (`NONE`), `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Compares `dst` with `src` by computing $dst - src$ on `alu_adder32` and updating status flags `Z, S, C, V`. No register is written (`EXEC_WB` pulses with `RES_SEL = NONE`).

#### Concrete Numeric Example
```text
Suppose AL = 0x00000010, BL = 0x00000010.
After execution of CMP AL, BL:
  AL - BL = 0x00000000
  Result is zero: sets ZERO (Z) to 1
  Bit 31 = 0: sets SIGN (S) to 0
  No borrow (16 >= 16): sets CARRY (C) to 0
  No overflow: sets OVERFLOW (V) to 0
  AL remains 0x00000010 unchanged.
```

---

```
================================================================================
EXP_ADD EA, src — EXPONENT 12-BIT ADDITION
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  X  |  X  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if 12-bit result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if bit 11 (sign bit of 12-bit signed exponent) is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflow occurred ($EA + src > +1023$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflow occurred ($EA + src < -1022$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
EA [11:0] <- (EA [11:0] + src [11:0]) & 0x0FFF
UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000101`. `W = 0` (always 1 cycle). `RES_SEL = EA`, `HA_MUX = EA`, `HB_MUX = src` (`EB` or `IMM`).

#### Description
Performs 12-bit signed addition on the exponent registers using `alu_exp12`. Automatically checks IEEE exponent limits ($\pm 1023$ / $\pm 1022$), asserting `VF` on overflow and `UF` on underflow.

#### Concrete Numeric Example
```text
Suppose EA = 1000, EB = 50.
After execution of EXP_ADD EA, EB:
  EA + EB = 1050 > +1023
  EA becomes 1050
  Overflow detected: sets OVERFLOW (V) to 1
  Underflow clear: sets UNDERFLOW (U) to 0
  Non-zero result: sets ZERO (Z) to 0, SIGN (S) to 0
```

---

```
================================================================================
EXP_SUB EA, src — EXPONENT 12-BIT SUBTRACTION
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  X  |  X  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if 12-bit result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if bit 11 is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflow occurred ($EA - src > +1023$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflow occurred ($EA - src < -1022$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
EA [11:0] <- (EA [11:0] - src [11:0]) & 0x0FFF
UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000110`. `W = 0` (always 1 cycle). `RES_SEL = EA`, `HA_MUX = EA`, `HB_MUX = src` (`EB` or `IMM`).

#### Description
Performs 12-bit signed subtraction on the exponent registers using `alu_exp12`. Asserts `VF` on overflow and `UF` on underflow.

#### Concrete Numeric Example
```text
Suppose EA = -1000, EB = 50.
After execution of EXP_SUB EA, EB:
  EA - EB = -1050 < -1022
  Underflow detected: sets UNDERFLOW (U) to 1
  Overflow clear: sets OVERFLOW (V) to 0
  Bit 11 = 1: sets SIGN (S) to 1
```

---

```
================================================================================
MUL dst, src / MUL AX, src — MULTIPLY (RADIX-4 BOOTH MULTIPLIER)
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  0  |  X  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if entire product is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of product is 1; reset to 0 otherwise.
* **`C`**: Always cleared to 0.
* **`V`**: Set to 1 if product exceeds single-word capacity ($AH \neq 0$ for 32-bit, or $DX \neq 0$ for 64-bit); reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
# Hardware Booth Multiplier Core (W = 0, 16 cycles):
{AH [31:0], AL [31:0]} <- AL [31:0] * src [31:0]
UPC                    <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000111` (`MUL` / `MULU`). `W = 0` (32-bit $\times$ 32-bit $\to$ 64-bit product, 16 cycles). `RES_SEL = dst` (must be `AL` on `HA_MUX`), `HB_MUX = src`.
* `MicroOp.MUL`: Signed two's-complement multiplication.
* `MicroOp.MULU`: Unsigned multiplication.

#### Description
Performs Radix-4 Booth multiplication using the shared multiplier core co-located with the adder block. The engine computes 2 bits per cycle over 16 clock cycles, placing the full 64-bit product into `{AH, AL}`.

* **Flag Behavior:**
  - `VF` is asserted if the product cannot be represented within 32 bits (for signed `MUL`, when `AH` is not a sign-extension of `AL`; for unsigned `MULU`, when `AH != 0`).
  - `ZF` is asserted if the full 64-bit product is zero.
  - `SF` reflects MSB (bit 63) of the product.
  - `CF` is cleared to 0.

* **User Opcode Stack Semantics & Result Widths:**
  - **`MUL_I32` ($32 \times 32 \to 32 + \text{VF}$):** Consumes two 32-bit integers from the stack, runs `MicroOp.MUL`, and pushes the 32-bit low product (`AL`) back onto the stack. `VF` is retained in the status register.
  - **`MUL_I64` ($64 \times 64 \to 64 + \text{VF}$):** Consumes two 64-bit integers from the stack and orchestrates partial cross-products ($A_L \times B_L$, $A_L \times B_H$, $A_H \times B_L$) via microcode over 32-bit multiplier cycles, pushing a 64-bit product to the stack and asserting `VF` if the mathematical product exceeds 64 bits.
  - **Widening Multiplication ($32 \times 32 \to 64$):** If the programmer requires a wide 64-bit product without truncation risk, operands are converted before multiplying:
    - *Signed:* Convert operands with `CONV_I32_I64`, then execute `MUL_I64`.
    - *Unsigned:* Convert operands with `CONV_U32_U64`, then execute `MUL_I64`.

#### Concrete Numeric Example
```text
Suppose AL = 0x00010000 (65536), BL = 0x00020000 (131072), W = 0.
After execution of MUL AL, BL (16 cycles):
  Product = 65536 * 131072 = 8,589,934,592 = 0x00000002_00000000
  AH = 0x00000002, AL = 0x00000000
  Upper half AH != 0: sets OVERFLOW (V) to 1
  Full 64-bit product is non-zero: sets ZERO (Z) to 0
  MSB of product (bit 63) = 0: sets SIGN (S) to 0
  Carry flag: cleared to 0
```

---

### Block 1 (0b001): Math / Float / Divider Block

```
================================================================================
PACK dst, exp — PACK IEEE-754 FLOATING-POINT NUMBER
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  X  |  X  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if packed float is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if sign bit of packed float is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflowed to $\pm\infty$ ($exp \ge \text{MAX\_EXP}$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflowed ($exp \le 0$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:  # Float32
    dst [31:0] <- { STATUS.S, exp [7:0], dst [22:0] }
    UPC        <- UPC + 1
else:       # Float64
    {dst_H [31:0], dst_L [31:0]} <- { STATUS.S, exp [10:0], dst_H [19:0], dst_L [31:0] }
    UPC        <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 001000`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 2 cycles). `RES_SEL = dst`, `HA_MUX = exp`, `HB_MUX = dst`.

#### Description
Assembles an IEEE-754 floating-point value from its components: sign bit from `STATUS.S`, biased exponent from `exp` (`EA`), and normalized mantissa from `dst` (`AL` or `AX`), stripping the implicit hidden bit. Asserts `VF` on exponent overflow (saturating to infinity) or `UF` on exponent underflow (flushing to signed zero).

#### Concrete Numeric Example
```text
Suppose STATUS.S = 0, EA = 127 (0x7F, unbiased 0), AL mantissa = 0x00000000 (representing 1.0).
After execution of PACK AL, EA (W = 0):
  AL = {0, 0x7F, 23'd0} = 0x3F800000 (+1.0f)
  Sign = 0: sets SIGN (S) to 0
  Non-zero float: sets ZERO (Z) to 0
  Valid exponent range: sets OVERFLOW (V) to 0, UNDERFLOW (U) to 0
```

---

```
================================================================================
UNPACK dst, exp — UNPACK IEEE-754 FLOATING-POINT NUMBER
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if input float is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if float sign bit is 1; reset to 0 otherwise.
* **`C`, `V`, `U`, `ERR`**: Unaffected.
* **`D`**: Set to `STATUS.S ^ dst.sign` (computes operand sign difference for add/sub alignment).

#### Register Transfer & Datapath Flow
```text
if W == 0:  # Float32
    exp [11:0] <- zero_extend(dst [30:23])
    dst [31:0] <- { 8'b0, 1'b1, dst [22:0] }  # restore hidden bit
    STATUS.D   <- STATUS.S ^ dst [31]
    STATUS.S   <- dst [31]
    UPC        <- UPC + 1
else:       # Float64
    exp [11:0] <- zero_extend(dst_H [30:20])
    dst_H [31:0] <- { 11'b0, 1'b1, dst_H [19:0] }
    # dst_L remains unchanged
    STATUS.D   <- STATUS.S ^ dst_H [31]
    STATUS.S   <- dst_H [31]
    UPC        <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 001001`. `W = 0` (Float32) or `W = 1` (Float64). `RES_SEL = dst`, `HA_MUX = exp`, `HB_MUX = dst`.

#### Description
Splits an IEEE-754 floating-point number into its constituent fields: extracts biased exponent into `exp` (`EA` or `EB`), inserts the hidden bit into `dst` mantissa, updates `STATUS.S` with operand sign, and calculates `DIFF_SIGN` (`STATUS.D = sign_A ^ sign_B`) to steer downstream addition/subtraction.

#### Concrete Numeric Example
```text
Suppose AL = 0x3F800000 (+1.0f), STATUS.S = 1 (previous operand was negative).
After execution of UNPACK AL, EA (W = 0):
  EA <- 0x007F (127)
  AL <- 0x00800000 (normalized mantissa with hidden bit 23 set)
  Sign bit of AL is 0: sets SIGN (S) to 0
  DIFF_SIGN: 1 ^ 0 = 1: sets DIFF_SIGN (D) to 1 (different signs)
  Non-zero float: sets ZERO (Z) to 0
```

---

```
================================================================================
DIV dst, src / DIV AX, src — INTEGER DIVISION
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  X  |  -  |  X  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if quotient is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of quotient is 1; reset to 0 otherwise.
* **`C`, `U`, `D`**: Unaffected.
* **`V`**: Set to 1 on divide-by-zero or signed overflow (`0x80000000 / -1`); reset to 0 otherwise.
* **`ERR`**: Set to 1 on divide-by-zero ($src == 0$); reset to 0 otherwise.

#### Register Transfer & Datapath Flow
```text
if src == 0:
    STATUS.ERR <- 1
    STATUS.V   <- 1
    UPC        <- UPC + 1
elif W == 0:  # 32-bit divide (32 cycles)
    AL [31:0] <- AL [31:0] / src [31:0]  (quotient)
    DL [31:0] <- AL [31:0] % src [31:0]  (remainder)
    UPC       <- UPC + 1
else:         # 64-bit divide (64 cycles)
    AX [63:0] <- AX [63:0] / src [63:0]  (quotient)
    DX [63:0] <- AX [63:0] % src [63:0]  (remainder)
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 001010`. `W = 0` (32-bit, 32 cycles) or `W = 1` (64-bit, 64 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Performs integer division of `dst` by `src` using a multi-cycle non-restoring divider engine co-located in the arithmetic block. Produces both quotient (written back to `dst`) and remainder (latched into `DL` or `DX`). If `src == 0`, the operation aborts without modifying `dst` or `DL`, asserting `ERR = 1` and `V = 1`.

#### Concrete Numeric Example
```text
Suppose AL = 0x00000017 (23), BL = 0x00000005 (5), W = 0.
After execution of DIV AL, BL (32 cycles):
  Quotient: 23 / 5 = 4 -> AL = 0x00000004
  Remainder: 23 % 5 = 3 -> DL = 0x00000003
  Non-zero quotient: sets ZERO (Z) to 0
  Positive quotient: sets SIGN (S) to 0
  Valid division: sets OVERFLOW (V) to 0, ERR to 0
```

---

```
================================================================================
MOD dst, src / MOD AX, src — INTEGER MODULO / REMAINDER
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  X  |  -  |  X  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if remainder is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of remainder is 1; reset to 0 otherwise.
* **`C`, `U`, `D`**: Unaffected.
* **`V`**: Set to 1 on divide-by-zero; reset to 0 otherwise.
* **`ERR`**: Set to 1 on divide-by-zero ($src == 0$); reset to 0 otherwise.

#### Register Transfer & Datapath Flow
```text
if src == 0:
    STATUS.ERR <- 1
    STATUS.V   <- 1
    UPC        <- UPC + 1
elif W == 0:  # 32-bit modulo (32 cycles)
    dst [31:0] <- dst [31:0] % src [31:0]
    UPC        <- UPC + 1
else:         # 64-bit modulo (64 cycles)
    dst [63:0] <- dst [63:0] % src [63:0]
    UPC        <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 001011`. `W = 0` (32-bit, 32 cycles) or `W = 1` (64-bit, 64 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Returns the remainder of dividing `dst` by `src`, writing the remainder directly to `dst`. If `src == 0`, asserts `ERR = 1` and `V = 1`.

#### Concrete Numeric Example
```text
Suppose AL = 0x00000017 (23), BL = 0x00000005 (5), W = 0.
After execution of MOD AL, BL:
  AL <- 23 % 5 = 3 = 0x00000003
  Non-zero remainder: sets ZERO (Z) to 0
  Positive remainder: sets SIGN (S) to 0
  Valid division: sets OVERFLOW (V) to 0, ERR to 0
```

---

### Block 2 (0b010): Logic Block

```
================================================================================
AND dst, src / AND AX, src — BITWISE LOGICAL AND
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  0  |  0  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Cleared to 0.
* **`V`**: Cleared to 0.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31:0] <- AL [31:0] & src [31:0]
    UPC       <- UPC + 1
else:
    Cycle 1: AL [31:0] <- AL [31:0] & src_L [31:0]
    Cycle 2: AH [31:0] <- AH [31:0] & src_H [31:0]
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 010000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Performs bitwise logical AND between `dst` and `src`. Always resets `C` and `V` to 0.

#### Concrete Numeric Example
```text
Suppose AL = 0x0000FFFF, BL = 0x00FF00FF.
After execution of AND AL, BL:
  AL <- 0x000000FF
  Bit 31 = 0: sets SIGN (S) to 0
  Non-zero result: sets ZERO (Z) to 0
  Clears CARRY (C) to 0, OVERFLOW (V) to 0
```

---

```
================================================================================
OR dst, src / OR AX, src — BITWISE LOGICAL OR
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  0  |  0  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Cleared to 0.
* **`V`**: Cleared to 0.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31:0] <- AL [31:0] | src [31:0]
    UPC       <- UPC + 1
else:
    Cycle 1: AL [31:0] <- AL [31:0] | src_L [31:0]
    Cycle 2: AH [31:0] <- AH [31:0] | src_H [31:0]
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 010001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Performs bitwise logical OR between `dst` and `src`. Resets `C` and `V` to 0.

#### Concrete Numeric Example
```text
Suppose AL = 0x12000000, BL = 0x00000034.
After execution of OR AL, BL:
  AL <- 0x12000034
  Bit 31 = 0: sets SIGN (S) to 0
  Non-zero result: sets ZERO (Z) to 0
  Clears CARRY (C) to 0, OVERFLOW (V) to 0
```

---

```
================================================================================
XOR dst, src / XOR AX, src — BITWISE LOGICAL EXCLUSIVE OR
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  0  |  0  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Cleared to 0.
* **`V`**: Cleared to 0.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31:0] <- AL [31:0] ^ src [31:0]
    UPC       <- UPC + 1
else:
    Cycle 1: AL [31:0] <- AL [31:0] ^ src_L [31:0]
    Cycle 2: AH [31:0] <- AH [31:0] ^ src_H [31:0]
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 010010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src`.

#### Description
Performs bitwise logical XOR between `dst` and `src`. Clearing a register (`XOR AL, AL`) produces zero and asserts `ZF = 1`. Resets `C` and `V` to 0.

#### Concrete Numeric Example
```text
Suppose AL = 0xAAAAAAAA, BL = 0xAAAAAAAA.
After execution of XOR AL, BL:
  AL <- 0x00000000
  Result is zero: sets ZERO (Z) to 1
  Bit 31 = 0: sets SIGN (S) to 0
  Clears CARRY (C) to 0, OVERFLOW (V) to 0
```

---

```
================================================================================
FABS dst — FLOATING-POINT ABSOLUTE VALUE
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  0  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if float magnitude is zero; reset to 0 otherwise.
* **`S`**: Always cleared to 0 (positive).
* **`C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31]   <- 1'b0  # Clear float32 sign bit
    UPC       <- UPC + 1
else:
    AH [31]   <- 1'b0  # Clear float64 sign bit
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 010011`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 1 cycle). `RES_SEL = dst`, `HA_MUX = n/a`, `HB_MUX = dst`.

#### Description
Clears the sign bit (bit 31 of `AL` for 32-bit, or bit 31 of `AH` for 64-bit), producing the positive absolute value of the floating-point operand. Always clears `STATUS.S` to 0.

#### Concrete Numeric Example
```text
Suppose AL = 0xBF800000 (-1.0f).
After execution of FABS AL:
  AL becomes 0x3F800000 (+1.0f)
  Sign cleared: sets SIGN (S) to 0
  Non-zero magnitude: sets ZERO (Z) to 0
```

---

```
================================================================================
FCHS dst — FLOATING-POINT CHANGE SIGN (NEGATE)
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`S`**: Inverted: `STATUS.S <- ~STATUS.S`.
* **`Z`, `C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31]   <- ~AL [31]  # Invert float32 sign bit
    STATUS.S  <- AL [31]
    UPC       <- UPC + 1
else:
    AH [31]   <- ~AH [31]  # Invert float64 sign bit
    STATUS.S  <- AH [31]
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 010100`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 1 cycle). `RES_SEL = dst`, `HA_MUX = n/a`, `HB_MUX = dst`.

#### Description
Inverts the sign bit of a floating-point operand in place and updates the sign flag `STATUS.S`.

#### Concrete Numeric Example
```text
Suppose AL = 0x3F800000 (+1.0f).
After execution of FCHS AL:
  AL becomes 0xBF800000 (-1.0f)
  Sign inverted: sets SIGN (S) to 1
```

---

```
================================================================================
NOT dst / NOT AX — BITWISE LOGICAL COMPLEMENT
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if inverted result is zero (original was all 1s); reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of inverted result is 1; reset to 0 otherwise.
* **`C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    AL [31:0] <- ~AL [31:0]
    UPC       <- UPC + 1
else:
    Cycle 1: AL [31:0] <- ~AL [31:0]
    Cycle 2: AH [31:0] <- ~AH [31:0]
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 010101`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = n/a`, `HB_MUX = dst`.

#### Description
Performs one's-complement bitwise inversion on all bits of `dst`.

#### Concrete Numeric Example
```text
Suppose AL = 0x00000000.
After execution of NOT AL:
  AL <- 0xFFFFFFFF
  Bit 31 = 1: sets SIGN (S) to 1
  Non-zero result: sets ZERO (Z) to 0
```

---

### Block 6 (0b110): Shifter / LZC Block

```
================================================================================
LSL dst[, src] / LSL AX[, src] — LOGICAL SHIFT LEFT
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if shifted result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of shifted result is 1; reset to 0 otherwise.
* **`C`**: Set to the last bit shifted out (MSB of operand); reset to 0 if shift count is 0.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
count = src[5:0] if src provided else C[5:0]
if W == 0:
    STATUS.C  <- (count > 0) ? AL [32 - count] : STATUS.C
    AL [31:0] <- AL [31:0] << count
    UPC       <- UPC + 1
else:
    STATUS.C  <- (count > 0) ? AH [64 - count - 32] : STATUS.C
    AX [63:0] <- AX [63:0] << count
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 110000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle barrel shifter). `RES_SEL = dst`, `HA_MUX = src` (or `C`), `HB_MUX = dst`.

#### Description
Performs logical shift left by the specified count using a single-cycle barrel shifter. Zeros are shifted into the least significant bit positions. The carry flag captures the last bit shifted out.

#### Concrete Numeric Example
```text
Suppose AL = 0x80000001, C = 1 (count = 1).
After execution of LSL AL:
  AL <- 0x00000002
  Bit 31 shifted out: sets CARRY (C) to 1
  Bit 31 of result = 0: sets SIGN (S) to 0
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
LSR dst[, src] / LSR AX[, src] — LOGICAL SHIFT RIGHT
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  0  |  X  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if shifted result is zero; reset to 0 otherwise.
* **`S`**: Cleared to 0 (since zeros are shifted into the MSB).
* **`C`**: Set to the last bit shifted out (LSB of operand); reset to 0 if shift count is 0.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
count = src[5:0] if src provided else C[5:0]
if W == 0:
    STATUS.C  <- (count > 0) ? AL [count - 1] : STATUS.C
    AL [31:0] <- AL [31:0] >> count  (zero-fill MSB)
    UPC       <- UPC + 1
else:
    STATUS.C  <- (count > 0) ? AX [count - 1] : STATUS.C
    AX [63:0] <- AX [63:0] >> count
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 110001`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst`, `HA_MUX = src` (or `C`), `HB_MUX = dst`.

#### Description
Performs logical shift right by the specified count using the barrel shifter, inserting zeros into the most significant bits. The carry flag captures the last bit shifted out.

#### Concrete Numeric Example
```text
Suppose AL = 0x00000005, C = 1 (count = 1).
After execution of LSR AL:
  AL <- 0x00000002
  Bit 0 shifted out (1): sets CARRY (C) to 1
  MSB is 0: sets SIGN (S) to 0
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
ASL dst[, src] / ASL AX[, src] — ARITHMETIC SHIFT LEFT
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  X  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to the last bit shifted out.
* **`V`**: Set to 1 if the sign bit changed at any point during the shift; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
count = src[5:0] if src provided else C[5:0]
AL [31:0] <- AL [31:0] << count
STATUS.V  <- 1 if sign changed during shift else 0
UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 110010`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst`, `HA_MUX = src` (or `C`), `HB_MUX = dst`.

#### Description
Performs arithmetic shift left. Identical to logical shift left, with the addition of tracking signed overflow (`VF = 1` if sign bit ever differs from original).

#### Concrete Numeric Example
```text
Suppose AL = 0x40000000, C = 1 (count = 1).
After execution of ASL AL:
  AL <- 0x80000000
  Sign changed from 0 to 1: sets OVERFLOW (V) to 1
  Bit 31 = 1: sets SIGN (S) to 1
  Bit 30 shifted out (0): sets CARRY (C) to 0
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
ASR dst[, src] / ASR AX[, src] — ARITHMETIC SHIFT RIGHT
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Preserves operand sign bit.
* **`C`**: Set to the last bit shifted out (LSB).
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
count = src[5:0] if src provided else C[5:0]
if W == 0:
    STATUS.C  <- (count > 0) ? AL [count - 1] : STATUS.C
    AL [31:0] <- AL [31:0] >> count  (sign-extended)
    UPC       <- UPC + 1
else:
    STATUS.C  <- (count > 0) ? AX [count - 1] : STATUS.C
    AX [63:0] <- AX [63:0] >> count  (sign-extended)
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 110011`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst`, `HA_MUX = src` (or `C`), `HB_MUX = dst`.

#### Description
Performs arithmetic shift right by replicating the sign bit into the vacated high-order bit positions.

#### Concrete Numeric Example
```text
Suppose AL = 0xFFFFFFF8 (-8), C = 1 (count = 1).
After execution of ASR AL:
  AL <- 0xFFFFFFFC (-4)
  Bit 0 shifted out (0): sets CARRY (C) to 0
  Sign bit is 1: sets SIGN (S) to 1
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
RRC dst / RRC AX — ROTATE RIGHT THROUGH CARRY
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if rotated result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if new MSB is 1; reset to 0 otherwise.
* **`C`**: Set to the old LSB shifted out.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:  # 33-bit rotation
    old_c     = STATUS.C
    STATUS.C  <- AL [0]
    AL [31:0] <- { old_c, AL [31:1] }
    UPC       <- UPC + 1
else:       # 65-bit rotation
    old_c     = STATUS.C
    STATUS.C  <- AX [0]
    AX [63:0] <- { old_c, AX [63:1] }
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 110100`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle). `RES_SEL = dst`, `HA_MUX = n/a`, `HB_MUX = dst`.

#### Description
Rotates `dst` right through the carry flag by 1 bit: `STATUS.C` enters MSB (bit 31 or 63), and LSB (bit 0) enters `STATUS.C`.

#### Concrete Numeric Example
```text
Suppose AL = 0x00000001, STATUS.C = 1.
After execution of RRC AL:
  AL <- 0x80000000
  Bit 0 enters carry: sets CARRY (C) to 1
  Bit 31 is 1: sets SIGN (S) to 1
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
RLC dst / RLC AX — ROTATE LEFT THROUGH CARRY
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if rotated result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if new MSB is 1; reset to 0 otherwise.
* **`C`**: Set to the old MSB shifted out.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:  # 33-bit rotation
    old_c     = STATUS.C
    STATUS.C  <- AL [31]
    AL [31:0] <- { AL [30:0], old_c }
    UPC       <- UPC + 1
else:       # 65-bit rotation
    old_c     = STATUS.C
    STATUS.C  <- AX [63]
    AX [63:0] <- { AX [62:0], old_c }
    UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 110101`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle). `RES_SEL = dst`, `HA_MUX = n/a`, `HB_MUX = dst`.

#### Description
Rotates `dst` left through the carry flag by 1 bit: `STATUS.C` enters LSB (bit 0), and MSB enters `STATUS.C`.

#### Concrete Numeric Example
```text
Suppose AL = 0x80000000, STATUS.C = 0.
After execution of RLC AL:
  AL <- 0x00000000
  Bit 31 enters carry: sets CARRY (C) to 1
  Bit 31 is 0: sets SIGN (S) to 0
  Result is zero: sets ZERO (Z) to 1
```

---

```
================================================================================
LZC dst, src / LZC AX, src — LEADING ZERO COUNT
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if `src == 0` (all leading zeros: count is 32 or 64); reset to 0 otherwise.
* **`S`, `C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    dst [31:0] <- count_leading_zeros(src [31:0])  # 0 to 32
    STATUS.Z   <- (src [31:0] == 0)
    UPC        <- UPC + 1
else:
    dst [63:0] <- count_leading_zeros(src [63:0])  # 0 to 64
    STATUS.Z   <- (src [63:0] == 0)
    UPC        <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 110110`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst` (typically `C` register), `HA_MUX = n/a`, `HB_MUX = src`.

#### Description
Counts the number of consecutive leading zero bits starting from the most significant bit of `src` using dedicated LUT tree logic. Typically written directly to counter `C` for floating-point normalization shifts.

#### Concrete Numeric Example
```text
Suppose AL = 0x00080000 (bit 19 set, bits 31..20 are zeros -> 12 leading zeros), W = 0.
After execution of LZC C, AL:
  C <- 12 (0x0C)
  Source is non-zero: sets ZERO (Z) to 0
```

---

### Block 4 & 5 (0b100 / 0b101): Memory & Storage Block

```
================================================================================
PUSH src / PUSH AX — PUSH REGISTER ONTO OPERAND STACK
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  X  |  -  |  X  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`V`**: Set to 1 if operand stack overflow occurred ($OSP > 28$ for 32-bit or $> 24$ for 64-bit); reset to 0 otherwise.
* **`ERR`**: Set to 1 on stack overflow; reset to 0 otherwise.
* **`Z`, `S`, `C`, `U`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:  # 32-bit push (4 bytes)
    if OSP + 4 > 32:
        STATUS.V   <- 1
        STATUS.ERR <- 1
    else:
        STACK_RAM [OSP .. OSP+3] <- src [31:0]
        OSP                      <- OSP + 4
        TOS                      <- src [31:0]
    UPC <- UPC + 1
else:       # 64-bit push (8 bytes)
    if OSP + 8 > 32:
        STATUS.V   <- 1
        STATUS.ERR <- 1
    else:
        STACK_RAM [OSP .. OSP+7] <- { src_H [31:0], src_L [31:0] }
        OSP                      <- OSP + 8
        TOS                      <- src_L [31:0]
    UPC <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 100000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = TOS`, `HA_MUX = n/a`, `HB_MUX = src`.

#### Description
Pushes register `src` onto the 32-byte operand stack, updates `TOS` cache register, and advances `OSP[4:0]`. If pushing exceeds the 32-byte physical depth, `VF` and `ERR` flags are raised.

#### Concrete Numeric Example
```text
Suppose OSP = 0x00, AL = 0x12345678, W = 0.
After execution of PUSH AL:
  STACK_RAM[0..3] <- 0x12345678
  TOS <- 0x12345678
  OSP <- 0x04
  No overflow: OVERFLOW (V) = 0, ERR = 0
```

---

```
================================================================================
POP dst / POP AX — POP REGISTER FROM OPERAND STACK
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  X  |  X  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`U`**: Set to 1 if operand stack underflow occurred ($OSP < 4$ for 32-bit or $< 8$ for 64-bit); reset to 0 otherwise.
* **`ERR`**: Set to 1 on stack underflow; reset to 0 otherwise.
* **`Z`, `S`, `C`, `V`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
if W == 0:  # 32-bit pop
    if OSP < 4:
        STATUS.U   <- 1
        STATUS.ERR <- 1
    else:
        OSP         <- OSP - 4
        dst [31:0]  <- STACK_RAM [OSP .. OSP+3]
        TOS         <- (OSP >= 4) ? STACK_RAM [OSP-4 .. OSP-1] : 0
    UPC <- UPC + 1
else:       # 64-bit pop
    if OSP < 8:
        STATUS.U   <- 1
        STATUS.ERR <- 1
    else:
        OSP                    <- OSP - 8
        {dst_H, dst_L}         <- STACK_RAM [OSP .. OSP+7]
        TOS                    <- dst_L
    UPC <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 100001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = n/a`, `HB_MUX = TOS`.

#### Description
Pops the top value from the operand stack into `dst` and decrements `OSP`. If popping from an empty stack ($OSP < 4$), `UF` and `ERR` flags are raised.

#### Concrete Numeric Example
```text
Suppose OSP = 0x04, STACK_RAM[0..3] = 0x12345678, W = 0.
After execution of POP BL:
  BL <- 0x12345678
  OSP <- 0x00
  No underflow: UNDERFLOW (U) = 0, ERR = 0
```

---

```
================================================================================
LDC dst, addr — LOAD FROM CONSTANT ROM
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    dst [31:0] <- CONST_ROM [addr]
    UPC        <- UPC + 1
else:
    {dst_H, dst_L} <- { CONST_ROM [addr+1], CONST_ROM [addr] }
    UPC            <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 100010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Loads a 32-bit or 64-bit IEEE-754 constant (such as $0.0, 1.0, \pi, \ln(2), \dots$) from on-chip Constant ROM into `dst`.

#### Concrete Numeric Example
```text
Suppose CONST_ROM[0x02] = 0x3F800000 (+1.0f).
After execution of LDC AL, 0x02:
  AL <- 0x3F800000
  Flags are unaffected.
```

---

```
================================================================================
LDI dst, imm — LOAD IMMEDIATE 10-BIT SIGN-EXTENDED VALUE
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
dst [31:0] <- sign_extend(INSTR[9:0])
UPC        <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 100011`. `W = 0` (1 cycle). `RES_SEL = dst`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Loads a 10-bit signed immediate constant (`INSTR[9:0]`) sign-extended to 32 bits into `dst`. Also used when `IMM` is multiplexed with `HOST_IN` during host write sequences.

#### Concrete Numeric Example
```text
Suppose INSTR[9:0] = 0x3FF (-1).
After execution of LDI BL, 0x3FF:
  BL <- 0xFFFFFFFF (-1)
  Flags are unaffected.
```

---

```
================================================================================
LD dst, addr — LOAD FROM SCRATCHPAD MEMORY
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    dst [31:0] <- SCRATCHPAD [addr [5:0]]
    UPC        <- UPC + 1
else:
    // 64-bit load requires an even base memory address (addr % 2 == 0)
    dst_L      <- SCRATCHPAD [addr [5:0]]
    dst_H      <- SCRATCHPAD [(addr [5:0]) | 1]
    UPC        <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 100100`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Loads 32 or 64 bits from the internal scratchpad memory (used by microcode routines for temporaries) into `dst`. For 64-bit operations (`W = 1`), `addr` must be an even base address (`addr % 2 == 0`, bit 0 is 0); `dst_L` is loaded from `addr` and `dst_H` from `addr | 1`.

#### Concrete Numeric Example
```text
Suppose SCRATCHPAD[0x04] = 0xCAFEBABE.
After execution of LD AL, 0x04:
  AL <- 0xCAFEBABE
  Flags are unaffected.
```

---

```
================================================================================
STO addr, src — STORE TO SCRATCHPAD MEMORY
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    SCRATCHPAD [addr [5:0]] <- src [31:0]
    UPC                     <- UPC + 1
else:
    // 64-bit store requires an even base memory address (addr % 2 == 0)
    SCRATCHPAD [addr [5:0]]       <- src_L [31:0]
    SCRATCHPAD [(addr [5:0]) | 1] <- src_H [31:0]
    UPC                           <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 100101`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = IMM`, `HA_MUX = n/a`, `HB_MUX = src`.

#### Description
Stores 32 or 64 bits from register `src` into internal scratchpad memory at `addr`. For 64-bit operations (`W = 1`), `addr` must be an even base address (`addr % 2 == 0`, bit 0 is 0); `src_L` is stored into `addr` and `src_H` into `addr | 1`.

#### Concrete Numeric Example
```text
Suppose AL = 0xDEADBEEF.
After execution of STO 0x08, AL:
  SCRATCHPAD[0x08] <- 0xDEADBEEF
  Flags are unaffected.
```

---

```
================================================================================
LDU dst, addr — LOAD FROM HOST USER BUFFER
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    dst [31:0] <- USER_BUFFER [addr [5:0]]
    UPC        <- UPC + 1
else:
    {dst_H, dst_L} <- { USER_BUFFER [addr+1], USER_BUFFER [addr] }
    UPC            <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 101000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Loads a word from the host-accessible user buffer into `dst`.

#### Concrete Numeric Example
```text
Suppose USER_BUFFER[0x00] = 0x12345678.
After execution of LDU AL, 0x00:
  AL <- 0x12345678
  Flags are unaffected.
```

---

```
================================================================================
STU addr, src — STORE TO HOST USER BUFFER
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    USER_BUFFER [addr [5:0]] <- src [31:0]
    UPC                      <- UPC + 1
else:
    { USER_BUFFER [addr+1], USER_BUFFER [addr] } <- { src_H [31:0], src_L [31:0] }
    UPC                      <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 101001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = IMM`, `HA_MUX = n/a`, `HB_MUX = src`.

#### Description
Stores `src` into the host-accessible user buffer at `addr`.

#### Concrete Numeric Example
```text
Suppose AL = 0xAABBCCDD.
After execution of STU 0x00, AL:
  USER_BUFFER[0x00] <- 0xAABBCCDD
  Flags are unaffected.
```

---

```
================================================================================
MOV dst, src / MOV AX, src — REGISTER-TO-REGISTER MOVE
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
if W == 0:
    dst [31:0] <- src [31:0]
    UPC        <- UPC + 1
else:
    dst [63:0] <- src [63:0]
    UPC        <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 100110`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle via dual writeback). `RES_SEL = dst`, `HA_MUX = n/a`, `HB_MUX = src`.

#### Description
Transfers data directly from `src` to `dst` across the internal data bus without changing any status flags.

#### Concrete Numeric Example
```text
Suppose BL = 0x11223344.
After execution of MOV AL, BL:
  AL <- 0x11223344
  Flags are unaffected.
```

---

```
================================================================================
SWAP dst, src / SWAP AX, src — REGISTER EXCHANGE
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
temp       <- dst
dst [31:0] <- src [31:0]
src [31:0] <- temp
UPC        <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 100111`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle). `RES_SEL = dst`, `HA_MUX = n/a`, `HB_MUX = src`.

#### Description
Exchanges the contents of registers `dst` and `src` using the internal staging register in a single cycle.

#### Concrete Numeric Example
```text
Suppose AL = 0xAAAAAAAA, BL = 0x55555555.
After execution of SWAP AL, BL:
  AL <- 0x55555555
  BL <- 0xAAAAAAAA
  Flags are unaffected.
```

---

### Block 3 (0b011): Control Block

```
================================================================================
JMP addr — UNCONDITIONAL JUMP
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
UPC [9:0] <- INSTR [9:0]  (addr)
```

#### Instruction Word Format
`OPCODE = 011000`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Forces microprogram control to jump unconditionally to the microcode target address specified in `INSTR[9:0]`.

#### Concrete Numeric Example
```text
Suppose current UPC = 0x015, INSTR[9:0] = 0x040.
After execution of JMP 0x040:
  UPC <- 0x040
  Flags are unaffected.
```

---

```
================================================================================
JNZ [src,] addr — JUMP IF NOT ZERO
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

If `src` is omitted, the source is the `ZF` flag.  Otherwise, `src` may be any other flag.

#### Register Transfer & Datapath Flow
```text
if src == 0:
    UPC [9:0] <- INSTR [9:0]  (addr)
else:
    UPC [9:0] <- UPC [9:0] + 1
```

#### Instruction Word Format
`OPCODE = 011001`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Branches to `addr` if the zero flag (`STATUS.Z`) is 0. If `STATUS.Z` is 1, execution falls through to `UPC + 1`.
If `src` is specified, it is used instead of `STATUS.Z`.  It may be any other status flag.

#### Concrete Numeric Example
```text
Suppose STATUS.Z = 0, current UPC = 0x010, INSTR[9:0] = 0x030.
After execution of JNZ 0x030:
  Branch taken: UPC <- 0x030
  Flags are unaffected.
```

#### Examples:
```text
JNZ 0x32 ; uses STATUS.Z
JNZ VF, 0x10; uses OVERLOW
```
---

```
================================================================================
JZ [src,] addr — JUMP IF ZERO
================================================================================
```

As with `JNZ`, the optional `src` may be any status flag.  If not present, the `ZF` is used.

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
if STATUS.Z == 1:
    UPC [9:0] <- INSTR [9:0]  (addr)
else:
    UPC [9:0] <- UPC [9:0] + 1
```

#### Instruction Word Format
`OPCODE = 011010`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Branches to `addr` if the zero flag (`STATUS.Z`) is 1. If `STATUS.Z` is 0, execution falls through to `UPC + 1`.

#### Concrete Numeric Example
```text
Suppose STATUS.Z = 1, current UPC = 0x010, INSTR[9:0] = 0x050.
After execution of JZ 0x050:
  Branch taken: UPC <- 0x050
  Flags are unaffected.
```

---

```
================================================================================
DJNZ addr — DECREMENT COUNTER C AND JUMP IF NOT ZERO
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if updated counter `C == 0`; reset to 0 otherwise.
* **`S`, `C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
C [31:0] <- C [31:0] - 1
STATUS.Z <- (C [31:0] == 0)
if STATUS.Z == 0:
    UPC [9:0] <- INSTR [9:0]  (addr)
else:
    UPC [9:0] <- UPC [9:0] + 1
```

#### Instruction Word Format
`OPCODE = 011011`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Decrements the loop counter register `C` by 1 and updates `STATUS.Z`. If `C` has not reached zero (`STATUS.Z == 0`), branches to `addr`. When `C` reaches zero, branches are skipped and execution falls through to `UPC + 1`.

#### Concrete Numeric Example
```text
Suppose C = 3, current UPC = 0x020, INSTR[9:0] = 0x01A.
After execution of DJNZ 0x01A:
  C becomes 2
  C != 0: sets ZERO (Z) to 0
  Branch taken: UPC <- 0x01A
```

---

```
================================================================================
CALL addr — SUBROUTINE CALL
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
RETURN_REG [9:0] <- UPC [9:0] + 1
UPC [9:0]        <- INSTR [9:0]  (addr)
```

#### Instruction Word Format
`OPCODE = 011100`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description
Saves the address of the next sequential instruction (`UPC + 1`) into the dedicated micro-return register and jumps to subroutine `addr`.

#### Concrete Numeric Example
```text
Suppose current UPC = 0x025, INSTR[9:0] = 0x080.
After execution of CALL 0x080:
  RETURN_REG <- 0x026
  UPC <- 0x080
  Flags are unaffected.
```

---

```
================================================================================
RET — SUBROUTINE RETURN
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: None affected.

#### Register Transfer & Datapath Flow
```text
UPC [9:0] <- RETURN_REG [9:0]
```

#### Instruction Word Format
`OPCODE = 011101`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = n/a`, `HB_MUX = n/a`.

#### Description
Restores microprogram execution flow to the return address latched during the preceding `CALL`.

#### Concrete Numeric Example
```text
Suppose RETURN_REG = 0x026.
After execution of RET:
  UPC <- 0x026
  Flags are unaffected.
```

---

```
================================================================================
NOP — NO OPERATION (PIPELINE BUBBLE)
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **Flags**: All flags unaffected.

#### Register Transfer & Datapath Flow
```text
EXEC_WB     <- 1'b0
STATUS_WREN <- 8'h00
RES_SEL     <- 4'hF (NONE)
EXEC_DONE   <- 1'b1
UPC [9:0]   <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 011110`. `W = 0` (1 cycle). `RES_SEL = NONE`, `HA_MUX = n/a`, `HB_MUX = n/a`.

#### Description
Performs no operation. Used as a 1-cycle pipeline bubble / flush slot on branch mispredictions or when delaying for multi-cycle memory alignment. Advances `UPC` without modifying any registers or flags.

#### Concrete Numeric Example
```text
After execution of NOP:
  Registers and STATUS remain unchanged.
  UPC advances by 1.
```

---

```
================================================================================
HALT — NORMAL EXECUTION TERMINATION
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR    D
+-----+-----+-----+-----+-----+-----+-----+-----+
|  0  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```
* **`BSY`**: Cleared to 0 (operation completed successfully).
* **`ERR`, `Z`, `S`, `C`, `V`, `U`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow
```text
STATUS.BSY <- 1'b0
EXEC_DONE  <- 1'b1  (pulse)
UPC [9:0]  <- 10'd0 (idle loop)
```

#### Instruction Word Format
`OPCODE = 011111`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = n/a`, `HB_MUX = n/a`.

#### Description
Halts the microprogram normally by resetting `STATUS.BSY = 0`, pulses `EXEC_DONE` to notify host or dispatcher that execution completed successfully, and vectors `UPC` back to the dispatch/idle state.

#### Concrete Numeric Example
```text
After execution of HALT:
  STATUS.BSY <- 0
  EXEC_DONE pulses for 1 cycle.
  UPC vectors to 0x000 (idle state).
```