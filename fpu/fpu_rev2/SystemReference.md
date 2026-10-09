# Microcode Instruction Reference Manual

Instructions are of these forms:

- Nullary, e.g. `RET`
- Unary, e.g. `POP AL` such that `AL <- TOS`
- Binary, e.g. `ADD AL, BL` such that `AL <- AL + BL`
- Ternary, e.g. `ADD AL, BL, DL` such that `AL <- BL + DL`

The physical registers are 32-bits each (unless stated otherwise):

- AL and AH (Accumulator / Working registers)
- BL and BH (Operand / Working registers)
- DL and DH (Multiplier / Divider registers)
- FL and FH (Staging / Working registers)
- EA (12-bit exponent register)
- EB (12-bit exponent register)
- C (8-bit loop / shift counter)
- SP (8-bit hardware math stack pointer)
- OSP (5-bit batch operation stack pointer)
- UPC (10-bit microcode program counter, addressing 1,024 words in CODE_ROM)
- RET (10-bit return address register)
- STATUS (8-bit status flags register)

In the assembly, pseudo-registers AX, BX, DX, and FX denote 64-bit operations, e.g `ADD AX, BX`.

When resolving an instruction, the destination (`dst`) can be any of the physical registers. The other two
are sources: `src1` and `src2`. `src1` can be any of AL, AH, BL, BH, C, and an immediate value (IMM).
`src2` can be any of the physical registers, or an immediate value (IMM).

### Block 0 (0b000): Arithmetic / Adder Block

```
================================================================================
ADD dst, src2 / ADD AX, src2 — ADD REGISTER TO ACCUMULATOR
ADD dst, src1, src2 — ADD REGISTER TO REGISTER
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
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
    dst [31:0] <- (src1 or dst) [31:0] + src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_L [31:0] <- (src1_L or dst_L) [31:0] + src2_L [31:0], latch Carry_out
    Cycle 2: dst_H [31:0] <- (src1_H or dst_H) [31:0] + src2_H [31:0] + Carry_in
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`
in 3-operand form), `HB_MUX = src2`.

#### Description

Adds the contents of `src2` to accumulator `dst` (`AL` or `AX`), or adds `src1` and `src2` writing to `dst` in ternary
form (`ADD dst, src1, src2`), using `alu_adder32` with carry chain. When `W = 1`, the operation executes across two
consecutive cycles, adding the low halves in cycle 1 and the high halves with carry in cycle 2.

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
ADC dst, src2 / ADC AX, src2 — ADD WITH CARRY TO ACCUMULATOR
ADC dst, src1, src2 — ADD WITH CARRY REGISTER TO REGISTER
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
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
    dst [31:0] <- (src1 or dst) [31:0] + src2 [31:0] + STATUS.C
    UPC        <- UPC + 1
else:
    Cycle 1: dst_L [31:0] <- (src1_L or dst_L) [31:0] + src2_L [31:0] + STATUS.C, latch Carry_out
    Cycle 2: dst_H [31:0] <- (src1_H or dst_H) [31:0] + src2_H [31:0] + Carry_in
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Adds the contents of `src2` and the carry flag `C` to accumulator `dst`, or adds `src1 + src2 + C` writing to `dst` in
ternary form. Used primarily for multi-word synthesis beyond 64 bits.

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
SUB dst, src2 / SUB AX, src2 — SUBTRACT REGISTER FROM ACCUMULATOR
SUB dst, src1, src2 — SUBTRACT REGISTER FROM REGISTER
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred ($dst < src2$ or $src1 < src2$ unsigned); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- (src1 or dst) [31:0] - src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_L [31:0] <- (src1_L or dst_L) [31:0] - src2_L [31:0], latch Borrow_out
    Cycle 2: dst_H [31:0] <- (src1_H or dst_H) [31:0] - src2_H [31:0] - Borrow_in
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Subtracts `src2` from `dst` (or computes $src1 - src2$ into `dst` in ternary form). Evaluated
as $(src1\text{ or }dst) + \overline{src2} + 1$ using `alu_adder32` with subtract control asserted. In 64-bit mode
(`W = 1`), subtraction proceeds across 2 cycles.

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
SBB dst, src2 / SBB AX, src2 — SUBTRACT WITH BORROW FROM ACCUMULATOR
SBB dst, src1, src2 — SUBTRACT WITH BORROW REGISTER FROM REGISTER
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
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
    dst [31:0] <- (src1 or dst) [31:0] - src2 [31:0] - STATUS.C
    UPC        <- UPC + 1
else:
    Cycle 1: dst_L [31:0] <- (src1_L or dst_L) [31:0] - src2_L [31:0] - STATUS.C, latch Borrow_out
    Cycle 2: dst_H [31:0] <- (src1_H or dst_H) [31:0] - src2_H [31:0] - Borrow_in
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000011`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Subtracts `src2` and incoming borrow `C` from accumulator `dst` (or computes $src1 - src2 - C$ into `dst` in ternary
form).

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
CMP src1, src2 — COMPARE TWO REGISTERS
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if $src1 == src2$; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of $(src1 - src2)$ is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred ($src1 < src2$ unsigned); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
Discard (src1 - src2) -> RES_SEL = NONE (no register write)
Update STATUS flags: sets ZF and SF (and CF, VF)
UPC <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000100`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = 0b1111` (`NONE`),
`HA_MUX = src1`, `HB_MUX = src2`.

#### Description

Compares `src1` with `src2` by computing $src1 - src2$ on `alu_adder32` and updating status flags `Z` and `S` (along
with `C` and `V`). No register is written (`EXEC_WB` pulses with `RES_SEL = NONE`).

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
EXP_ADD dst, src2 / EXP_ADD EA, src2 — EXPONENT 12-BIT ADDITION
EXP_ADD dst, src1, src2 — EXPONENT 12-BIT ADDITION (REGISTER TO REGISTER/IMMEDIATE)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  X  |  X  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if 12-bit result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if bit 11 (sign bit of 12-bit signed exponent) is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflow occurred ($EA + src2 > +1023$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflow occurred ($EA + src2 < -1022$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
dst [11:0] <- ((src1 or dst) [11:0] + src2 [11:0]) & 0x0FFF
UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000101`. `W = 0` (always 1 cycle). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`), `HB_MUX = src2` (`EB` or
`IMM`).

#### Description

Performs 12-bit signed addition on the exponent registers using `alu_exp12`. Automatically checks IEEE exponent limits
($\pm 1023$ / $\pm 1022$), asserting `VF` on overflow and `UF` on underflow.

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
EXP_SUB dst, src2 / EXP_SUB EA, src2 — EXPONENT 12-BIT SUBTRACTION
EXP_SUB dst, src1, src2 — EXPONENT 12-BIT SUBTRACTION (REGISTER TO REGISTER/IMMEDIATE)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  X  |  X  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if 12-bit result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if bit 11 is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflow occurred ($EA - src2 > +1023$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflow occurred ($EA - src2 < -1022$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
dst [11:0] <- ((src1 or dst) [11:0] - src2 [11:0]) & 0x0FFF
UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000110`. `W = 0` (always 1 cycle). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`), `HB_MUX = src2` (`EB` or
`IMM`).

#### Description

Performs 12-bit signed subtraction on the exponent registers using `alu_exp12`. Asserts `VF` on overflow and `UF` on
underflow.

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

### Block 1 (0b001): Hardware Multiply / Divide / Math Block

```
===============================================================================
PACK dst, src1 — PACK IEEE-754 FLOATING-POINT NUMBER
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  X  |  X  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if packed float is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if sign bit of packed float is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflowed to $\pm\infty$ ($src1 \ge \text{MAX\_EXP}$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflowed ($src1 \le 0$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:  # Float32
    dst [31:0] <- { STATUS.S, src1 [7:0], dst [22:0] }
    UPC        <- UPC + 1
else:       # Float64
    {dst_H [31:0], dst_L [31:0]} <- { STATUS.S, src1 [10:0], dst_H [19:0], dst_L [31:0] }
    UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001000`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 2 cycles). `RES_SEL = dst`, `HA_MUX = src1` (exponent
register `EA` or `EB`), `HB_MUX = dst`.

#### Description

Assembles an IEEE-754 floating-point value from its components: sign bit from `STATUS.S`, biased exponent from `src1`
(`EA` or `EB`), and normalized mantissa from `dst` (`AL` or `AX`), stripping the implicit hidden bit. Asserts `VF` on
exponent overflow (saturating to infinity) or `UF` on exponent underflow (flushing to signed zero).

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
UNPACK dst, src1 — UNPACK IEEE-754 FLOATING-POINT NUMBER
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
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
    src1 [11:0] <- zero_extend(dst [30:23])
    dst [31:0]  <- { 8'b0, 1'b1, dst [22:0] }  # restore hidden bit
    STATUS.D    <- STATUS.S ^ dst [31]
    STATUS.S    <- dst [31]
    UPC         <- UPC + 1
else:       # Float64
    src1 [11:0]  <- zero_extend(dst_H [30:20])
    dst_H [31:0] <- { 11'b0, 1'b1, dst_H [19:0] }
    # dst_L remains unchanged
    STATUS.D     <- STATUS.S ^ dst_H [31]
    STATUS.S     <- dst_H [31]
    UPC          <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001001`. `W = 0` (Float32) or `W = 1` (Float64). `RES_SEL = dst`, `HA_MUX = src1` (exponent register `EA` or
`EB`), `HB_MUX = dst`.

#### Description

Splits an IEEE-754 floating-point number into its constituent fields: extracts biased exponent into `src1` (`EA` or
`EB`), inserts the hidden bit into `dst` mantissa, updates `STATUS.S` with operand sign, and calculates `DIFF_SIGN`
(`STATUS.D = sign_A ^ sign_B`) to steer downstream addition/subtraction.

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
MUL dst, src2 / MUL AX, src2 — SIGNED MULTIPLY (RADIX-4 BOOTH MULTIPLIER)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if entire product is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of product is 1; reset to 0 otherwise.
* **`C`**: Always cleared to 0.
* **`V`**: Set to 1 if product exceeds single-word capacity ($AH \neq 0$ for 32-bit, or when high half is not sign
  extension of low half); reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
# Hardware Booth Multiplier Core (W = 0, 16 cycles):
{AH [31:0], AL [31:0]} <- AL [31:0] * src2 [31:0]  (signed)
UPC                    <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001010`. `W = 0` (32-bit $\times$ 32-bit $\to$ 64-bit product, 16 cycles). `RES_SEL = dst` (must be `AL`),
`HA_MUX = dst`, `HB_MUX = src2`.

#### Description

Performs signed Radix-4 Booth multiplication using the shared multiplier core co-located with the arithmetic block. The
engine computes 2 bits per cycle over 16 clock cycles, placing the full 64-bit product into `{AH, AL}`.

- Cycle 15: Writes low word to `AL`.
- Cycle 16: Writes high word to `AH` and commits status flags `Z, S, C=0, V`.

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

```
================================================================================
DIV dst, src2 / DIV AX, src2 — SIGNED INTEGER DIVISION
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  X  |  -  |  X  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if quotient is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of quotient is 1; reset to 0 otherwise.
* **`C`, `U`, `D`**: Unaffected.
* **`V`**: Set to 1 on divide-by-zero or signed overflow (`0x80000000 / -1`); reset to 0 otherwise.
* **`ERR`**: Set to 1 on divide-by-zero ($src2 == 0$); reset to 0 otherwise.

#### Register Transfer & Datapath Flow

```text
if src2 == 0:
    STATUS.ERR <- 1
    STATUS.V   <- 1
    UPC        <- UPC + 1
elif W == 0:  # 32-bit divide (32 cycles)
    AL [31:0] <- AL [31:0] / src2 [31:0]  (signed quotient)
    DL [31:0] <- AL [31:0] % src2 [31:0]  (remainder)
    UPC       <- UPC + 1
else:         # 64-bit divide (64 cycles via microcode)
    AX [63:0] <- AX [63:0] / src2 [63:0]  (signed quotient)
    DX [63:0] <- AX [63:0] % src2 [63:0]  (remainder)
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001011`. `W = 0` (32-bit, 32 cycles) or `W = 1` (64-bit). `RES_SEL = dst` (must be `AL`), `HA_MUX = dst`,
`HB_MUX = src2`.

#### Description

Performs signed integer division of `dst` by `src2` using a multi-cycle non-restoring divider engine co-located in the
arithmetic block. Produces both signed quotient (written to `dst`, `AL`) and signed remainder (latched into `DL`). If
`src2 == 0`, the operation aborts without modifying `dst` or `DL`, asserting `ERR = 1` and `V = 1`.

- Cycle 31: Writes quotient to `AL`.
- Cycle 32: Writes remainder to `DL` and commits status flags.

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
MULU dst, src2 / MULU AX, src2 — UNSIGNED MULTIPLY (RADIX-4 BOOTH MULTIPLIER)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if entire 64-bit product is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of product (bit 63) is 1; reset to 0 otherwise.
* **`C`**: Always cleared to 0.
* **`V`**: Set to 1 if product exceeds single-word capacity ($AH \neq 0$); reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
# Hardware Booth Multiplier Core (W = 0, 16 cycles):
{AH [31:0], AL [31:0]} <- AL [31:0] * src2 [31:0]  (unsigned)
UPC                    <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001110`. `W = 0` (32-bit $\times$ 32-bit $\to$ 64-bit product, 16 cycles). `RES_SEL = dst` (must be `AL`),
`HA_MUX = dst`, `HB_MUX = src2`.

#### Description

Performs unsigned Radix-4 Booth multiplication using the shared multiplier core. Operates across 16 cycles, writing low
word product to `AL` in cycle 15, high word to `AH` in cycle 16, and committing status flags. `VF` is asserted if
`AH != 0`.

#### Concrete Numeric Example

```text
Suppose AL = 0x80000000, BL = 0x00000002, W = 0.
After execution of MULU AL, BL (16 cycles):
  Product = 0x80000000 * 2 = 0x00000001_00000000
  AH = 0x00000001, AL = 0x00000000
  Upper half AH != 0: sets OVERFLOW (V) to 1
  Full 64-bit product non-zero: sets ZERO (Z) to 0
  MSB (bit 63) = 0: sets SIGN (S) to 0
  Carry flag: cleared to 0
```

---

```
================================================================================
DIVU dst, src2 / DIVU AX, src2 — UNSIGNED INTEGER DIVISION
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  X  |  -  |  X  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if quotient is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of quotient is 1; reset to 0 otherwise.
* **`C`, `U`, `D`**: Unaffected.
* **`V`**: Set to 1 on divide-by-zero; reset to 0 otherwise.
* **`ERR`**: Set to 1 on divide-by-zero ($src2 == 0$); reset to 0 otherwise.

#### Register Transfer & Datapath Flow

```text
if src2 == 0:
    STATUS.ERR <- 1
    STATUS.V   <- 1
    UPC        <- UPC + 1
elif W == 0:  # 32-bit divide (32 cycles)
    AL [31:0] <- AL [31:0] / src2 [31:0]  (unsigned quotient)
    DL [31:0] <- AL [31:0] % src2 [31:0]  (unsigned remainder)
    UPC       <- UPC + 1
else:         # 64-bit divide (64 cycles via microcode)
    AX [63:0] <- AX [63:0] / src2 [63:0]  (unsigned quotient)
    DX [63:0] <- AX [63:0] % src2 [63:0]  (unsigned remainder)
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001111`. `W = 0` (32-bit, 32 cycles) or `W = 1` (64-bit). `RES_SEL = dst` (must be `AL`), `HA_MUX = dst`,
`HB_MUX = src2`.

#### Description

Performs unsigned integer division of `dst` by `src2` using the non-restoring divider engine. Produces unsigned quotient
in `dst` (`AL`) and unsigned remainder in `DL`. If `src2 == 0`, aborts without modifying `AL` or `DL`, setting `ERR = 1`
and `V = 1`.

- Cycle 31: Writes quotient to `AL`.
- Cycle 32: Writes remainder to `DL` and commits status flags.

#### Concrete Numeric Example

```text
Suppose AL = 0x00000017 (23), BL = 0x00000005 (5), W = 0.
After execution of DIVU AL, BL (32 cycles):
  Quotient: 23 / 5 = 4 -> AL = 0x00000004
  Remainder: 23 % 5 = 3 -> DL = 0x00000003
  Non-zero quotient: sets ZERO (Z) to 0
  Positive quotient: sets SIGN (S) to 0
  Valid division: sets OVERFLOW (V) to 0, ERR to 0
```

---

### Block 2 (0b010): Logic Block

```
================================================================================
AND dst, src2 / AND AX, src2 — BITWISE LOGICAL AND
AND dst, src1, src2  — BITWISE LOGICAL AND (dst <- src1 & src2)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  0  |  -  |  -  |  X  |
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
    dst [31:0] <- (src1 or dst) [31:0] & src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_L [31:0] <- (src1 or dst)_L [31:0] & src2_L [31:0]
    Cycle 2: dst_H [31:0] <- (src1 or dst)_H [31:0] & src2_H [31:0]
    UPC                   <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Performs bitwise logical AND between `(src1 or dst)` and `src2`. Always resets `C` and `V` to 0.

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
OR dst, src2 / OR AX, src2 — BITWISE LOGICAL OR
OR dst, src1, src2  — BITWISE LOGICAL OR (dst <- src1 | src2)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  0  |  -  |  -  |  X  |
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
    dst [31:0] <- (src1 or dst) [31:0] | src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_L [31:0] <- (src1 or dst)_L [31:0] | src2_L [31:0]
    Cycle 2: dst_H [31:0] <- (src1 or dst)_H [31:0] | src2_H [31:0]
    UPC                   <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Performs bitwise logical OR between `(src1 or dst)` and `src2`. Resets `C` and `V` to 0.

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
XOR dst, src2 / XOR AX, src2 — BITWISE LOGICAL EXCLUSIVE OR
XOR dst, src1, src2  — BITWISE LOGICAL XOR (dst <- src1 ^ src2)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  0  |  -  |  -  |  X  |
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
    dst [31:0] <- (src1 or dst) [31:0] ^ src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_L [31:0] <- (src1 or dst)_L [31:0] ^ src2_L [31:0]
    Cycle 2: dst_H [31:0] <- (src1 or dst)_H [31:0] ^ src2_H [31:0]
    UPC                   <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Performs bitwise logical XOR between `(src1 or dst)` and `src2`. Clearing a register (`XOR AL, AL`) produces zero and
asserts `ZF = 1`. Resets `C` and `V` to 0.

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
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  0  |  -  |  -  |  -  |  -  |  X  |
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

`OPCODE = 010011`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 1 cycle). `RES_SEL = dst`, `HA_MUX = n/a`,
`HB_MUX = dst`.

#### Description

Clears the sign bit (bit 31 of `AL` for 32-bit, or bit 31 of `AH` for 64-bit), producing the positive absolute value of
the floating-point operand. Always clears `STATUS.S` to 0.

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
  BSY    D     S     C     V     U    ERR    Z
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

`OPCODE = 010100`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 1 cycle). `RES_SEL = dst`, `HA_MUX = n/a`,
`HB_MUX = dst`.

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
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  -  |  -  |  -  |  X  |
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

`OPCODE = 010101`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = n/a`,
`HB_MUX = dst`.

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
LSL dst[, src1] / LSL AX[, src1] — LOGICAL SHIFT LEFT
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if shifted result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of shifted result is 1; reset to 0 otherwise.
* **`C`**: Set to the last bit shifted out (MSB of operand); reset to 0 if shift count is 0.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
count = src1[5:0] if src1 provided else C[5:0]
if W == 0:
    STATUS.C   <- (count > 0) ? AL [32 - count] : STATUS.C
    dst [31:0] <- dst [31:0] << count
    UPC        <- UPC + 1
else:
    STATUS.C  <- (count > 0) ? AH [64 - count - 32] : STATUS.C
    AX [63:0] <- AX [63:0] << count
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 110000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle barrel shifter). `RES_SEL = dst`,
`HA_MUX = src1` (or `C`), `HB_MUX = dst`.

#### Description

Performs logical shift left by the specified count using a single-cycle barrel shifter. Zeros are shifted into the least
significant bit positions. The carry flag captures the last bit shifted out.

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
LSR dst[, src1] / LSR AX[, src1] — LOGICAL SHIFT RIGHT
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  0  |  X  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if shifted result is zero; reset to 0 otherwise.
* **`S`**: Cleared to 0 (since zeros are shifted into the MSB).
* **`C`**: Set to the last bit shifted out (LSB of operand); reset to 0 if shift count is 0.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
count = src1[5:0] if src1 provided else C[5:0]
if W == 0:
    STATUS.C   <- (count > 0) ? AL [count - 1] : STATUS.C
    dst [31:0] <- dst [31:0] >> count  (zero-fill MSB)
    UPC        <- UPC + 1
else:
    STATUS.C  <- (count > 0) ? AX [count - 1] : STATUS.C
    AX [63:0] <- AX [63:0] >> count
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 110001`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst`, `HA_MUX = src1` (or `C`), `HB_MUX = dst`.

#### Description

Performs logical shift right by the specified count using the barrel shifter, inserting zeros into the most significant
bits. The carry flag captures the last bit shifted out.

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
LZC dst, src2 / LZC AX, src2 — LEADING ZERO COUNT
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if `src2 == 0` (all leading zeros: count is 32 or 64); reset to 0 otherwise.
* **`S`, `C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- count_leading_zeros(src2 [31:0])  # 0 to 32
    STATUS.Z   <- (src2 [31:0] == 0)
    UPC        <- UPC + 1
else:
    dst [63:0] <- count_leading_zeros(src2 [63:0])  # 0 to 64
    STATUS.Z   <- (src2 [63:0] == 0)
    UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 110110`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst` (typically `C` register), `HA_MUX = n/a`,
`HB_MUX = src2`.

#### Description

Counts the number of consecutive leading zero bits starting from the most significant bit of `src2` using dedicated LUT
tree logic. Typically written directly to counter `C` for floating-point normalization shifts.

#### Concrete Numeric Example

```text
Suppose AL = 0x00080000 (bit 19 set, bits 31..20 are zeros -> 12 leading zeros), W = 0.
After execution of LZC C, AL:
  C <- 12 (0x0C)
  Source is non-zero: sets ZERO (Z) to 0
```

---

### Block 4 (0b100): Memory Stack & Scratchpad Block

```
================================================================================
PUSH src2 / PUSH AX — PUSH REGISTER ONTO OPERAND STACK
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  X  |  -  |  X  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`V`**: Set to 1 if operand stack overflow occurred ($OSP > 28$ for 32-bit or $> 24$ for 64-bit); reset to 0
  otherwise.
* **`ERR`**: Set to 1 on stack overflow; reset to 0 otherwise.
* **`Z`, `S`, `C`, `U`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:  # 32-bit push (4 bytes)
    if OSP + 4 > 32:
        STATUS.V   <- 1
        STATUS.ERR <- 1
    else:
        STACK_RAM [OSP .. OSP+3] <- src2 [31:0]
        OSP                      <- OSP + 4
        TOS                      <- src2 [31:0]
    UPC <- UPC + 1
else:       # 64-bit push (8 bytes)
    if OSP + 8 > 32:
        STATUS.V   <- 1
        STATUS.ERR <- 1
    else:
        STACK_RAM [OSP .. OSP+7] <- { src2_H [31:0], src2_L [31:0] }
        OSP                      <- OSP + 8
        TOS                      <- src2_L [31:0]
    UPC <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = NONE (0b1111)`, `HA_MUX = NONE`,
`HB_MUX = src2`.

#### Description

Pushes register `src2` onto the 32-byte operand stack, updates internal `TOS` cache register, and advances `OSP[4:0]`.
No general-purpose register is written (`RES_SEL = NONE`). If pushing exceeds the 32-byte physical depth, `VF` and `ERR`
flags are raised.

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
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  X  |  X  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`U`**: Set to 1 if operand stack underflow occurred ($OSP < 4$ for 32-bit or $< 8$ for 64-bit); reset to 0
  otherwise.
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

`OPCODE = 100001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = NONE`,
`HB_MUX = TOS`.

#### Description

Pops the top value from the operand stack into `dst` and decrements `OSP`. If popping from an empty stack ($OSP < 4$),
`UF` and `ERR` flags are raised.

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
LDC dst, tbl, addr — LOAD FROM CONSTANT / LUT ROM
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
effective_offset <- (HA_MUX == IMM) ? INSTR[9:0] : HA_MUX_REG

case tbl of
    CONST (0b000):  # DATA_RAM base 0x100 (words 256..319)
        if W == 0:
            dst [31:0]   <- DATA_RAM [0x100 | (effective_offset & 0x03F)]
        else:
            dst_L [31:0] <- DATA_RAM [0x100 | (effective_offset & 0x03E)]
            dst_H [31:0] <- DATA_RAM [0x101 | (effective_offset & 0x03E)]
    TRIG  (0b001):  # DATA_RAM base 0x200 (words 512..639)
        dst [31:0]       <- DATA_RAM [0x200 | (effective_offset & 0x07F)]
    CHEB  (0b010):  # DATA_RAM base 0x280 (words 640..767)
        dst [31:0]       <- DATA_RAM [0x280 | (effective_offset & 0x07F)]
    RECIP (0b011):  # DATA_RAM base 0x300 (words 768..1023), low 16-bit slice
        dst [15:0]       <- DATA_RAM [0x300 | (effective_offset & 0x0FF)] [15:0]
        dst [31:16]      <- 0
    SQRT  (0b100):  # DATA_RAM base 0x300 (words 768..1023), high 16-bit slice
        dst [15:0]       <- DATA_RAM [0x300 | (effective_offset & 0x0FF)] [31:16]
        dst [31:16]      <- 0

UPC <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles).

- `RES_SEL = dst` (4 bits): Destination register (`AL`, `AH`, `BL`, etc.).
- `tbl`: Table selector translated by assembler (`CONST=0b000`, `TRIG=0b001`, `CHEB=0b010`, `RECIP=0b011`,
  `SQRT=0b100`).
- `HA_MUX = addr` (3 bits via `src1`): Selects address source:
    - `HA_MUX = IMM (4)`: Address supplied as immediate constant in `INSTR[9:0]`.
    - `HA_MUX = C (5)` or `AL (0)` / `BL (6)`: Address supplied dynamically from register at runtime.
- `HB_MUX = NONE`.

#### Description

Loads a constant or lookup table entry from the unified `DATA_RAM` ROM space (EBR 0–3, `0x100`–`0x3FF`) into destination register `dst`.

- **Zero-Cost Bitwise OR Addressing**: Table bases are power-of-two aligned (`0x100`, `0x200`, `0x280`, `0x300`), eliminating adders and carry chains on the memory address path.
- **Interleaved Seed Tables (`0x300`–`0x3FF`)**: Reciprocal and Square Root seeds share 256 words at base `0x300`:
  - `RECIP` (`tbl=3`): Slices low 16 bits `[15:0]` and zero-extends into `dst[31:0]`.
  - `SQRT` (`tbl=4`): Slices high 16 bits `[31:16]` and zero-extends into `dst[31:0]`.
- **Dynamic Register Addressing**: In addition to static immediate table offsets, `addr` can be routed from any `HA_MUX`
  register (such as counter `C`), enabling single-cycle dynamic seed table indexing during `SQRT` and `DIV` execution.

#### Concrete Numeric Examples

```text
Example 1: Loading static constant (pi)
LDC AL, CONST, PI_F32
  Machine encoding: OPCODE=LDC, DST=AL, SRC=CONST (0), SRC1=IMM, IMM=PI_F32 (0)
  Reads 32-bit IEEE-754 float (+3.1415927) from DATA_RAM base 0x100 | 0 into AL.
  AL <- 0x40490FDB
  Flags are unaffected.

Example 2: Loading dynamic SQRT seed using runtime index in C
LDC AH, SQRT, C
  Suppose C = 0x4A (mantissa fraction and exponent parity index).
  Machine encoding: OPCODE=LDC, DST=AH, SRC=SQRT (4), SRC1=C
  Reads 32-bit word from DATA_RAM at address 0x300 | 0x4A = 0x34A and slices [31:16] into AH.
  AH <- zero_extend(DATA_RAM[0x34A][31:16])
  Flags are unaffected.
```

---

```
================================================================================
LDI dst, imm — LOAD IMMEDIATE INTO REGISTER
LDI flag, val — LOAD IMMEDIATE BIT INTO STATUS FLAG
================================================================================
```

#### Status Flags Affected

When loading into a register (`dst != NONE`):

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected when `dst != NONE`.

When loading into a status flag (`dst == NONE`):

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  | mod | mod | mod | mod | mod | mod | mod |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: Exactly the flag selected by `FLAG_COND` is modified to `val & 1` (`0` or `1`). All other flags are
  unaffected.

#### Register Transfer & Datapath Flow

```text
if dst != NONE:
    dst [31:0]   <- zero_extend(INSTR[9:0])
    STATUS       <- unaffected
    UPC          <- UPC + 1
else:
    STATUS[flag] <- INSTR[0]
    UPC          <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100011`. `W = 0` (1 cycle).

- **Register Form**: `RES_SEL = dst`, `HA_MUX = NONE`, `HB_MUX = IMM`, `IMM = imm[9:0]`.
- **Flag Form**: `RES_SEL = NONE (0b1111)`, `HA_MUX = NONE`, `HB_MUX = IMM`, `FLAG_COND = flag[2:0]`,
  `IMM = val (0 or 1)`.

#### Description

1. **Register Load (`LDI dst, imm`)**: Loads a 10-bit unsigned immediate constant (`INSTR[9:0]`) into `dst` via
   `HB_MUX = IMM`. If `W=1` (64-bit), the immediate is loaded into the low-half register (`dst`) and zero is loaded into
   the high-half register (`dst | 1`).
2. **Flag Load (`LDI flag, val`)**: When `dst` is `NONE`, the instruction operates as a universal flag manipulation
   operation. It routes `status_wr_sel = 1 << flag` and `res_status = (val & 1) << flag` through the datapath writeback
   multiplexer, setting or clearing the chosen flag in a single cycle without altering any other register or status
   flag. Commonly used to assert or clear `ERR`, `ZERO`, `CARRY`, etc.

#### Concrete Numeric Examples

```text
Example 1: Loading register
LDI EA, 127
  EA <- 127
  Flags unaffected.

Example 2: Setting error flag
LDI ERR, 1
  Machine encoding: OPCODE=LDI, DST=NONE, HB_MUX=IMM, FLAG_COND=ERR (1), IMM=1
  STATUS[ERR] <- 1
  All other status flags unaffected.

Example 3: Clearing zero flag
LDI ZERO, 0
  Machine encoding: OPCODE=LDI, DST=NONE, HB_MUX=IMM, FLAG_COND=ZERO (6), IMM=0
  STATUS[ZERO] <- 0
  All other status flags unaffected.
```

---

```
================================================================================
LD dst, addr — LOAD FROM SCRATCHPAD MEMORY
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
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

`OPCODE = 100100`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = IMM`,
`HB_MUX = NONE`.

#### Description

Loads 32 or 64 bits from the internal scratchpad memory (mapped to `DATA_RAM` base `0x080`, words 128..191, `SCR[0..63]`) into `dst`. For
64-bit operations (`W = 1`), `addr` must be an even base address (`addr % 2 == 0`, bit 0 is 0); `dst_L` is loaded from
`addr` and `dst_H` from `addr | 1`.

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
STO addr, src2 — STORE TO SCRATCHPAD MEMORY
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    SCRATCHPAD [addr [5:0]] <- src2 [31:0]
    UPC                     <- UPC + 1
else:
    // 64-bit store requires an even base memory address (addr % 2 == 0)
    SCRATCHPAD [addr [5:0]]       <- src2_L [31:0]
    SCRATCHPAD [(addr [5:0]) | 1] <- src2_H [31:0]
    UPC                           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100101`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = NONE (0b1111)`, `HA_MUX = IMM`,
`HB_MUX = src2`.

#### Description

Stores 32 or 64 bits from register `src2` into internal scratchpad memory (mapped to `DATA_RAM` base `0x080`, words 128..191, `SCR[0..63]`) at `addr`. Does not write to any
general-purpose register (`RES_SEL = NONE`). For 64-bit operations (`W = 1`), `addr` must be an even base address
(`addr % 2 == 0`, bit 0 is 0); `src2_L` is stored into `addr` and `src2_H` into `addr | 1`.

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
MOV dst, src2 / MOV AX, src2 — REGISTER-TO-REGISTER MOVE
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- src2 [31:0]
    UPC        <- UPC + 1
else:
    dst [63:0] <- src2 [63:0]
    UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100110`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle via dual writeback). `RES_SEL = dst`,
`HA_MUX = NONE`, `HB_MUX = src2`.

#### Description

Transfers data directly from `src2` to `dst` across the internal data bus without changing any status flags.

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
SWAP dst, src2 / SWAP AX, src2 — REGISTER EXCHANGE
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
temp       <- dst
dst [31:0] <- src2 [31:0]
src2 [31:0] <- temp
UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100111`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle). `RES_SEL = dst`, `HA_MUX = dst`,
`HB_MUX = src2`.

#### Description

Exchanges the contents of registers `dst` and `src2` using the internal staging register in a single cycle.

#### Concrete Numeric Example

```text
Suppose AL = 0xAAAAAAAA, BL = 0x55555555.
After execution of SWAP AL, BL:
  AL <- 0x55555555
  BL <- 0xAAAAAAAA
  Flags are unaffected.
```

---

### Block 5 (0b101): Memory User Buffer & Status Shadow Block

```
================================================================================
LDU dst, addr — LOAD FROM HOST USER BUFFER
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
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

`OPCODE = 101000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = IMM`,
`HB_MUX = NONE`.

#### Description

Loads a word from the host-accessible user buffer (mapped to `DATA_RAM` base `0x0C0`, words 192..207, `USR[0..15]`) into `dst`.

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
STU addr, src2 — STORE TO HOST USER BUFFER
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    USER_BUFFER [addr [5:0]] <- src2 [31:0]
    UPC                      <- UPC + 1
else:
    { USER_BUFFER [addr+1], USER_BUFFER [addr] } <- { src2_H [31:0], src2_L [31:0] }
    UPC                      <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 101001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = NONE (0b1111)`, `HA_MUX = IMM`,
`HB_MUX = src2`.

#### Description

Stores `src2` into the host-accessible user buffer (mapped to `DATA_RAM` base `0x0C0`, words 192..207, `USR[0..15]`) at `addr`. Does not write to any general-purpose register
(`RES_SEL = NONE`).

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
SSAV — SAVE STATUS REGISTER TO SHADOW
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
STATUS_SHADOW [7:0] <- STATUS [7:0]
UPC                 <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 101110`. `W = 0` (1 cycle). `RES_SEL = NONE (0b1111)`, `HA_MUX = NONE`, `HB_MUX = NONE`.

#### Description

Saves the current 8-bit STATUS register into an internal shadow register (`status_shadow`). This allows microcode
subroutines to preserve status flags before executing helper operations and restore them later with `SRES`. Does not
alter any register or status flag (`RES_SEL = NONE`).

#### Concrete Numeric Example

```text
Suppose STATUS = 0x11 (ZERO=1, CARRY=1).
After execution of SSAV:
  STATUS_SHADOW <- 0x11
  STATUS remains 0x11 unchanged.
```

---

```
================================================================================
SRES — RESTORE STATUS REGISTER FROM SHADOW
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  | mod | mod | mod | mod | mod |  -  | mod |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`D, S, C, V, U, Z`**: Restored from `STATUS_SHADOW`.
* **`BSY` (bit 7), `ERR` (bit 1)**: Protected / Unaffected (mask `0x7D` prevents overwriting operational engine flags).

#### Register Transfer & Datapath Flow

```text
STATUS <- (STATUS & ~0x7D) | (STATUS_SHADOW & 0x7D)
UPC    <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 101111`. `W = 0` (1 cycle). `RES_SEL = NONE (0b1111)`, `HA_MUX = NONE`, `HB_MUX = NONE`.

#### Description

Restores status flags from the internal shadow register using write mask `0x7D` (`0b0111_1101`). Flags `DIFF_SIGN`,
`SIGN`, `CARRY`, `OVERFLOW`, `UNDERFLOW`, and `ZERO` are restored to their shadowed states. Host interface flags `BUSY`
(bit 7) and `ERR` (bit 1) are masked out to prevent corrupted engine state. No register is written (`RES_SEL = NONE`).

#### Concrete Numeric Example

```text
Suppose STATUS_SHADOW = 0x11 (ZERO=1, CARRY=1), current STATUS = 0x82 (BUSY=1, ERR=1).
After execution of SRES:
  Restored with mask 0x7D:
  STATUS <- (0x82 & ~0x7D) | (0x11 & 0x7D) = 0x82 | 0x11 = 0x93 (BUSY=1, ZERO=1, CARRY=1, ERR=1)
  BUSY and ERR remain unchanged.
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
  BSY    D     S     C     V     U    ERR    Z
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
JNZ [flag,] addr — JUMP IF FLAG NOT SET (DEFAULT: ZERO FLAG)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

The condition operand `flag` is always a status flag (`ZF`, `ERR`, `UF`, `VF`, `CF`, `SF`, `DF`, `BSY`). If omitted,
`ZF` is implied.

#### Register Transfer & Datapath Flow

```text
cond = flag if flag provided else STATUS.Z
if cond == 0:
    UPC [9:0] <- INSTR [9:0]  (addr)
else:
    UPC [9:0] <- UPC [9:0] + 1
```

#### Instruction Word Format

`OPCODE = 011001`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = NONE`, `FLAG_COND = flag`.

#### Description

Branches to `addr` if the selected status `flag` is 0. If `flag` is not specified, `STATUS.Z` is tested. If the flag is
1, execution falls through to `UPC + 1`.

#### Concrete Numeric Example

```text
Suppose STATUS.Z = 0, current UPC = 0x010, INSTR[9:0] = 0x030.
After execution of JNZ 0x030:
  Branch taken: UPC <- 0x030
  Flags are unaffected.
```

#### Examples:

```text
JNZ 0x32        ; tests STATUS.Z (default)
JNZ VF, 0x10    ; tests STATUS.V (OVERFLOW)
JNZ ERR, error  ; tests STATUS.ERR
```

---

```
================================================================================
JZ [flag,] addr — JUMP IF FLAG SET (DEFAULT: ZERO FLAG)
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

The condition operand `flag` is always a status flag (`ZF`, `ERR`, `UF`, `VF`, `CF`, `SF`, `DF`, `BSY`). If omitted,
`ZF` is implied.

#### Register Transfer & Datapath Flow

```text
cond = flag if flag provided else STATUS.Z
if cond == 1:
    UPC [9:0] <- INSTR [9:0]  (addr)
else:
    UPC [9:0] <- UPC [9:0] + 1
```

#### Instruction Word Format

`OPCODE = 011010`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = NONE`, `FLAG_COND = flag`.

#### Description

Branches to `addr` if the selected status `flag` is 1. If `flag` is not specified, `STATUS.Z` is tested. If the flag is
0, execution falls through to `UPC + 1`.

#### Concrete Numeric Example

```text
Suppose STATUS.Z = 1, current UPC = 0x010, INSTR[9:0] = 0x050.
After execution of JZ 0x050:
  Branch taken: UPC <- 0x050
  Flags are unaffected.
```

#### Examples:

```text
JZ 0x50         ; tests STATUS.Z (default)
JZ CF, carry_set ; tests STATUS.C (CARRY)
JZ SF, negative  ; tests STATUS.S (SIGN)
```

---

```
================================================================================
DJNZ addr — DECREMENT COUNTER C AND JUMP IF NOT ZERO
================================================================================
```

#### Status Flags Affected

```text
  BSY    D     S     C     V     U    ERR    Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  X  |
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

Decrements the loop counter register `C` by 1 and updates `STATUS.Z`. If `C` has not reached zero (`STATUS.Z == 0`),
branches to `addr`. When `C` reaches zero, branches are skipped and execution falls through to `UPC + 1`.

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
  BSY    D     S     C     V     U    ERR    Z
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

Saves the address of the next sequential instruction (`UPC + 1`) into the dedicated micro-return register and jumps to
subroutine `addr`.

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
  BSY    D     S     C     V     U    ERR    Z
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
  BSY    D     S     C     V     U    ERR    Z
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

Performs no operation. Used as a 1-cycle pipeline bubble / flush slot on branch mispredictions or when delaying for
multi-cycle memory alignment. Advances `UPC` without modifying any registers or flags.

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
  BSY    D     S     C     V     U    ERR    Z
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

Halts the microprogram normally by resetting `STATUS.BSY = 0`, pulses `EXEC_DONE` to notify host or dispatcher that
execution completed successfully, and vectors `UPC` back to the dispatch/idle state.

#### Concrete Numeric Example

```text
After execution of HALT:
  STATUS.BSY <- 0
  EXEC_DONE pulses for 1 cycle.
  UPC vectors to 0x000 (idle state).
```