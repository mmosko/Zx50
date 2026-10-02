## Registers

all 32bit unless said othewise

- (AH, AL) = AX
- (BH, BL) = BX
- (DH, DL) = DX
- (FH, FL) = FX
- C (8 bit counter)
- EA, EB (12-bit exponent registers)
- SP (8 bit) stack pointer
- OSP (8 bit) operation stack pointer for user BATCH mode
- UPC (10 bit), microcode program counter
- STATUS (8 bit), status register
- RET: (10-bit), return address from CALL -- no nested calls

## ALU Blocks

There are a small number of synthesized ALU blocks that are then shared by the micro-opcodes (machine
instructions). We denote these as BLK_1, BLK_2, ..., BLK_k. We need to minimize the number of blocks.

There is an HA_BUS and HB_BUS (32-bit). Each is fed by a multiplexer.

HA_BUS <- MUX {AL, AH, EA, EB, C, IMM}
HB_BUS <= MUX {AL, AH, BL, BH, DL, DH, FL, FH, C, EA, EB, IMM}
INSTR_BUS <= the 32-bit instruction from the dispatcher.
IMM <= The 32-bit immediate value

The dispatcher sets the IMM value to either the `INSTR[9:0]` or the 32-bit stack buffer if the user
has been pushing to 0x70.

There is a RES_BUS (32-bit) that is the output of the blocks:

RES_BUS = MUX {BLK_1_out, ..., BLK_k_out}

To reduce power consumption, we want an AND wall in front of each BLK, so only the needed block gets
changing signals.

HA_BUS -> MUX {WALL_1 -> BLK_1, WALL_2 -> BLK_2, ...}.

- The dispatcher sets the WALL selectors.
- The BLK sets the HA_BUS, HB_BUS selectors. A 64-bit instruction may need 2 cycles to read the LO and HI halves.
- This means that a BLK cannot directly call anything in a different BLK. That has to be orchestrated by the
  microcode via the dispatcher. Registers (except FX) and Scratch Memory are presistent through the dispatcher.

The RES_BUS selector will be set by the specific BLK (it may use AL then AH, e.g., in two write backs). The BLK will
also set the STATUS MUX. Likewise, specific register WRITE will be set by the BLK.

Some blocks may have result registers, e.g. the 64-bit multipler will have 128-bits of output, so it might have a its
own result register and mux to feed the RES_BUS mux. This is TBD. If we can do the 32x32->64 or 64x64->128 via microcode
and limit the hardware, that might be a win if we are short on space.

The STATUS register needs to have its own output mux for status writebacks

STATUS <- MUX {BLK_1_ST_OUT, BLK_2_ST_OUT, ...}

### Block Input and Output

INPUTS to each block:

- `HA_BUS[31:0]`
- `HB_BUS[31:0]`
- `STATUS[7:0]`
- `INSTR[31:16]`
- `EXEC_READY`

- OUTPUTS from each block:
-
- `RES_BUS[31:0]`
- `RES_SEL[3:0]`,
- `RES_STATUS[7:0]`,
- `STATUS_WR_SEL[7:1]` (which bits to write)
- `EXEC_DONE`

### Example Blocks

In general, each block will have gates for several related functions. They will examine the INSTR_BUS
to figure out exactly what to do.

- ADDER: various code for adder64 and the needed helpers to do 32 or 64-bit math
- BOOTH_MUL: booth multiplier
- LOGIC: and, or, xor, not, etc.
- SHIFTER: ASR, ASL, LSL, LSR, etc.
- FLOAT: (if needed)
- MEM: load, move, store, load constant
- CONV: format conversion
- CTRL: jump and call

We should try to keep the number of macro blocks to a small number, as each needs an adder wall.

### Special Blocks

These are not part of the HA_BUS/HB_BUS/RES_BUS structure, but are needed for the dispatcher and stack and counter.
TBD how these integrate with the other BLKs. They will likely need their own handshake bits to do an operation
in one FPU cycle.

- SP ADDER (SP+1, SP+2, SP-2, SP-1), always in 4-byte words
- UPC ADDER (UPC + 1), always in 4-byte words
- USER_OPCODE buffer (the user writes 0x70 stack 1-byte at a time, accumulate 4 then use LD FL, imm / PUSH FL)
- DEC_C (C-1), decrement the counter

## Timing

The dispatcher will set an EXE_READY flag for 1 FPU cycle when all the control lines are setup.

The ALU and MEM subsystems will then execute for 1 or more cycles. They will set the EXE_WB flag for 1 cycle when the
result is ready to be written out of the RES_MUX. They may do multiple write back cycles.

When the BLK is done, it will set the EXE_DONE flag for 1 FPU cycle, which will trigger the dispatcher to go to the
next instruction fetch, or loop until ready.

## Machine Instruction (INSTR)

```text
 31        26 25  24     22 21    19 18        16          9                      0
+------------+---+---------+--------+------------+----------------------------------+
|   OPCODE   | W |   DST   |  SRC   | FLAG_COND  | RESERVED |   IMMEDIATE / ADDR    |
|   [5:0]    |   |  [3:0]  | [3:0]  |   [2:0]    |   [3:0]  |         [9:0]         |
+------------+---+---------+--------+------------+----------------------------------+
```

The immediate, address, offset values can be up to 10 bits, which is enough to address
up to 1K PC locations (in 4-byte words) or immediate values 0 - 1023.

Opcodes are a 3 bit block ID plus a 3 bit operation ID. This means we can group
BLK by the first three bits for the purpose of activating the AND walls.

| Block   | Prefix |
|---------|--------|
| Adder   | 0b000  |
| Adder   | 0b001  |
| Logic   | 0b010  |
| Ctrl    | 0b011  |
| Mem     | 0b100  |
| Mem     | 0b101  |
| Shifter | 0b110  |
| Shifter | 0b111  |

These are the 6-bit `OPCODE` values that go in a machine instruction

| Block   | Opcode  | Value     | Operation                                              |
|---------|---------|-----------|--------------------------------------------------------|
| Adder   | ADD     | 0b000_000 | Add                                                    |
| Adder   | ADC     | 0b000_001 | Add with carry                                         |
| Adder   | SUB     | 0b000_010 | Subtract                                               |
| Adder   | SBB     | 0b000_011 | Subtract with carry                                    |
| Adder   | CMP     | 0b000_100 | Compare                                                |
| Adder   | EXP_ADD | 0b000_101 | EA <- EA + EB (12-bit adder), or EA <- EA + src        |
| Adder   | EXP_SUB | 0b000_110 | EA <- EA - EB (12-bit adder), or EQ <- EA - src        |
| Adder   | EXP_CMP | 0b000_111 | ea < eb                                                |
| Adder   | PACK    | 0b001_000 | Combine reg, exp, sign into one reg                    |
| Adder   | UNPACK  | 0b001_001 | Extract one reg into reg, exponent, and sign           |
| ------  | ------- | -------   | -----------                                            |
| Logic   | AND     | 0b010_000 | logical and                                            |
| Logic   | OR      | 0b010_001 | logical or                                             |
| Logic   | XOR     | 0b010_010 | logical xor                                            |
| Logic   | ABS     | 0b010_011 | Absolute value                                         |
| Logic   | CHS     | 0b010_100 | Change sign (XOR + 1, if use 0-x put in adder)         |
| Logic   | NOT     | 0b010_101 | logical not                                            |
| ------  | ------- | -------   | -----------                                            |
| Shifter | LSL     | 0b110_000 | logical shift left (no carry) by C bits, zero fill     |
| Shifter | LSR     | 0b110_001 | logical shift right (no carry) by C bits, zero fill    |
| Shifter | ASL     | 0b110_010 | arithmetic shift left (no carry) by C bits, zero fill  |
| Shifter | ASR     | 0b110_011 | arithmetic shift right (no carry) by C bits, sign fill |
| Shifter | RRC     | 0b110_100 | rotate right with carry by 1 bit                       |
| Shifter | RLC     | 0b110_101 | rotate left with carry by 1 bit                        |
| Shifter | LZC     | 0b110_110 | count leading zeros                                    |
| ------  | ------- | -------   | -----------                                            |
| Mem     | PUSH    | 0b100_000 | push reg to TOS                                        |
| Mem     | POP     | 0b100_001 | pop reg from TOS                                       |
| Mem     | LDC     | 0b100_010 | Load reg from math constant from `[addr]`              |
| Mem     | LDI     | 0b100_011 | Load reg from immediate                                |
| Mem     | LD      | 0b100_100 | Load reg from scratch memory                           |
| Mem     | ST      | 0b100_101 | store reg to scratch memory                            |
| Mem     | MOV     | 0b100_110 | register (HB_BUS) to register move                     |
| Mem     | SWAP    | 0b100_111 | register (HB_BUS) to register swap (uses F register)   |
| Mem     | LDU     | 0b101_000 | Load reg from user memory                              |
| Mem     | STU     | 0b101_001 | store reg to user memory                               |
| ------  | ------- | -------   | -----------                                            |
| Ctrl    | JMP     | 0b011_000 | Unconditional call to `[addr]` in u_op memory          |
| Ctrl    | JNZ     | 0b011_001 | jump not zero                                          |
| Ctrl    | JZ      | 0b011_010 | jump zero                                              |
| Ctrl    | DJNZ    | 0b011_011 | decrement C, jump not zero                             |
| Ctrl    | CALL    | 0b011_100 | RET <- UPC, UPC <- `[addr]` (post UPC inc?)            |
| Ctrl    | RET     | 0b011_101 | set UPC to `RET` (post UPC inc?)                       |
| Ctrl    | TRAP    | 0b011_110 | error trap                                             |
| Ctrl    | NOP     | 0b011_111 | NOP                                                    |

| SRC | HA Value | HB Value |
|-----|----------|----------|
| AL  | 0b0000   | 0b0000   |
| AH  | 0b0001   | 0b0001   |
| EA  | 0b0010   | 0b0010   |
| EB  | 0b0011   | 0b0011   |
| IMM | 0b0100   | 0b0100   |
| C   | 0b0101   | 0b0101   |
| BL  |          | 0b0110   |
| BH  |          | 0b0111   |
| DL  |          | 0b1000   |
| DH  |          | 0b1001   |
| FL  |          | 0b1010   |
| FH  |          | 0b1011   |

- For BINARY functions, we use HA and HB as sources
- For UNIARY functions, we use the single HB_BUS as the source]()
- All functions use the RES_BUS as their output, though some MEM functions may write directly to memory and not
  use the RES_BUS output (i.e. they will not set a register WE pulse).

All Arithmetic operations are to AL or AX (depending on W). So they do not really need
the "AL" or "AX" in the mnemonic, but we include it for clarity.

The exception are the EXP_ADD and EXP_SUB which use the EA and EB. But they still use the HA_BUS and HB_BUS mux.

### Adder Machine Instructions

Need to add columns for STATUS register effects too.

A `DST`, `HA`, or `HB` specified as a specific register is fixed to only that register. It is encoded in the instruction
as normal, but cannot vary. A value of `src` or `dst` can be any valid value (i.e. `HA` can only select a limited number
of sources).

The W flag is impled by the assembly mnemonics, e.g. `ADD AX, BX` is implied 64-bit.

The EA registers are left-filled with 0 to use a 32-bit ALU block, or they may be a dedicated, simpler adder.

| mnemonic         | OPCODE    | W     | DST   | HA    | HB    | Details                            | Status Registers                      |
|------------------|-----------|-------|-------|-------|-------|------------------------------------|---------------------------------------|
| ADD dst, src     | 0b000_000 | 0/1   | dst   | dst   | src   |                                    |                                       |
| ADC dst, src     | 0b000_001 | 0/1   | dst   | dst   | src   |                                    |                                       |
| SUB dst, src     | 0b000_010 | 0/1   | dst   | dst   | src   |                                    |                                       |
| SBB dst, src     | 0b000_011 | 0/1   | dst   | dst   | src   |                                    |                                       |
| CMP dst, src     | 0b000_100 | 0/1   | dst   | dst   | src   |                                    |                                       |
| EXP_ADD EA, src  | 0b000_101 | 0     | EA    | EA    | src   | `EA <- EA + EB` or immediate       | Just use ADD plus a mask?             |
| EXP_SUB EA, src  | 0b000_110 | 0     | EA    | EA    | src   | EB or immediate                    | Just use SUB plus a mask?             |
| EXP_CMP EA, EB   | 0b000_111 | 0     |       |       |       |                                    | not needed, just use CMP?             |
| PACK dst, exp    | 0b001_000 | 0/1   | dst   | exp   | dst   | `dst <- dst & exp & sign`          |                                       |
| UNPACK dst, exp  | 0b001_001 | 0/1   | dst   | exp   | dst   |                                    |                                       |
| -----            | -----     | ----- | ----- | ----- | ----- | -----                              | -----                                 |
| AND dst, src     | 0b010_000 | 0/1   | dst   | dst   | src   | `dst <- dst & src`                 | sets ZF, SF, clears CF <- 0, OVF <- 0 |
| OR dst, src      | 0b010_001 | 0/1   | dst   | dst   | src   | `dst <- dst \| src`                | sets ZF, SF, clears CF <- 0, OVF <- 0 |
| XOR dst, src     | 0b010_010 | 0/1   | dst   | dst   | src   | `dst <- dst  ^ src`                | sets ZF, SF, clears CF <- 0, OVF <- 0 |
| ABS dst          | 0b010_011 | 0/1   | dst   | n/a   | dst   |                                    | sets SF                               |
| CHS dst          | 0b010_100 | 0/1   | dst   | n/a   | dst   |                                    | sets SF                               |
| NOT dst          | 0b010_101 | 0/1   | dst   | n/a   | dst   |                                    | sets flags                            |
| -----            | -----     | ----- | ----- | ----- | ----- | -----                              | -----                                 |
| LSL dst\[, src\] | 0b110_000 | 0/1   | dst   | src   | dst   | `dst <- dst << src` (C implied)    | sets flags                            |                               |
| LSR dst\[, src\] | 0b110_001 | 0/1   | dst   | src   | dst   | `dst <- dst >> src` (C implied)    | sets flags                            |                              |
| ASL dst\[, src\] | 0b110_010 | 0/1   | dst   | src   | dst   | `dst <- dst << src` (C implied)    | sets flags                            |                               |
| ASR dst\[, src\] | 0b110_011 | 0/1   | dst   | src   | dst   | `dst <- dst >> src` (C implied)    | sets flags                            |                              |
| RRC dst          | 0b110_100 | 0/1   | dst   | n/a   | dst   | circular rotate                    | sets flags                            |                               |
| RLC dst          | 0b110_101 | 0/1   | dst   | n/a   | dst   | circular rorate                    | sets flags                            |                              |
| LZC dst, src     | 0b110_110 | 0/1   | dst   | n/a   | src   | `dst <- leading zero count of src` |                                       |                              |
| -----            | -----     | ----- | ----- | ----- | ----- | -----                              | -----                                 |
| PUSH src         | 0b100_000 | 0/1   | TOS   | n/a   | src   | `TOS <- src, sp <- sp + W + 1      | sets OVF                              |                               |
| POP dst          | 0b100_001 | 0/1   | dst   | n/a   | TOS   | `dst <- TOS`, sp <- sp - (W+1)     | sets OVF                              |                               |
| LDC dst, addr    | 0b100_010 | 0/1   | dst   | IMM   | n/a   | `dst <- CONST_ADDR + \[addr\]`     | sets flags                            |                               |
| LDI dst, imm     | 0b100_011 | 0/1   | dst   | IMM   | n/a   | `dst <- imm`                       | sets flags                            |                               |
| LD  dst, addr    | 0b100_100 | 0/1   | dst   | IMM   | n/a   | `dst <- SCR_ADDR + \[addr\]`       | sets flags                            |                               |
| ST  addr, src    | 0b100_101 | 0/1   | IMM   | n/a   | src   | `SCR_ADDR + \[addr\] <- src`       |                                       |                               |
| LDU dst, addr    | 0b101_000 | 0/1   | dst   | IMM   | n/a   | `dst <- USER_ADDR + \[addr\]`      | sets flags                            |                               |
| STU addr, src    | 0b101_001 | 0/1   | dst   | IMM   | n/a   | `USER_ADDR + \[addr\] <- src`      |                                       |                               |
| MOV dst, src     | 0b100_110 | 0/1   | dst   | n/a   | src   | `dst <- src`                       |                                       |                               |
| SWAP dst, src    | 0b100_111 | 0/1   | dst   | n/a   | src   | `F_ <- src, src <- dst, dst <-F_`  |                                       |                               |
| -----            | -----     | ----- | ----- | ----- | ----- | -----                              | -----                                 |
| JMP addr         | 0b011_000 | 0     | UPC   | IMM   | n/a   | `upc <- addr`                      |                                       |                               |
| JNZ addr         | 0b011_000 | 0     | UPC   | IMM   | n/a   | `upc <- addr` if !ZF               |                                       |                               |
| JZ addr          | 0b011_010 | 0     | UPC   | IMM   | n/a   | `upc <- addr` if ZF                |                                       |                               |
| DJNZ addr        | 0b011_011 | 0     | UPC   | IMM   | n/a   | `dec C, upc <- addr` if !ZF        |                                       |                               |
| CALL addr        | 0b011_100 | 0     | UPC   | IMM   | n/a   | `ret <- upc, upc <- addr`          |                                       |                               |
| RET              | 0b011_101 | 0     | UPC   | n/a   | n/a   | `upc <- ret`                       |                                       |                               |
| TRAP             | 0b011_110 | 0     | UPC   | n/a   | n/a   | ??                                 |                                       |                               |
| NOP              | 0b011_111 | 0     | n/a   | n/a   | n/a   | 1 tick do nothing                  |                                       |                               |

## Microcode Instruction Reference Manual

Document all instructions similar to this template like the Z80 Reference Manual

```
================================================================================
SUB AL, src / SUB AX, src — SUBTRACT REGISTER FROM ACCUMULATOR
================================================================================
```

#### Status Flags Affected
```text
  BSY    Z     S     C     V     U    ERR
+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  X  |  X  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+
```
* **`Z`**: Set to 1 if result is zero ($AL == src$); reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred ($AL < src$ unsigned); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.

#### Register Transfer & Datapath Flow
```text
AL [31:0] <- AL [31:0] - src [31:0]
UPC       <- UPC + 1
```

#### Instruction Word Format
`OPCODE = 000011`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles).

#### Description
Subtracts the source register from `AL` or `AX`. Evaluated as $AL + \overline{src} + 1$ using `alu_adder32` with subtract control asserted. In 64-bit mode (`W = 1`), subtraction proceeds across 2 cycles ($AL - src_L$, then $AH - src_H - \text{Borrow}$).

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