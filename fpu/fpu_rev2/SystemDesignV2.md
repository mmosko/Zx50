# Zx50 FPU Rev 2 Low-Level System Design

## Registers

all 32bit unless said othewise

- (AH, AL) = AX
- (BH, BL) = BX
- (DH, DL) = DX
- (FH, FL) = FX
- C (8 bit counter)
- EA, EB (12-bit exponent registers)
- SP (8 bit) stack pointer
- OSP (5 bit) operation stack pointer for user BATCH mode (32-byte queue)
- UPC (10 bit), microcode program counter
- STATUS (8 bit), status register [7: BSY, 6: Z, 5: S, 4: C, 3: V, 2: U, 1: ERR, 0: D (DIFF_SIGN)]
- RET: (10-bit), return address from CALL -- no nested calls
- HOST_IN (32-bit), host input staging register (accumulates 4 bytes from Port 0x70 writes)
- HOST_OUT (32-bit), host output staging register (stages 4 bytes for Port 0x70 reads)
- CMD_REG (8-bit), command latch for Port 0x71 user opcodes

## Functional Blocks

![Functional Blocks](fpu_alu.svg)

There are a small number of synthesized functional blocks that are then shared by the micro-opcodes (machine
instructions). We denote these as BLK_1, BLK_2, ..., BLK_k. We need to minimize the number of blocks.

There is an HA_BUS and HB_BUS (32-bit). Each is fed by a multiplexer.

HA_BUS <- MUX {AL, AH, EA, EB, C, IMM, BL, BH}
HB_BUS <= MUX {AL, AH, EA, EB, C, IMM, BL, BH, DL, DH, FL, FH}
INSTR_BUS <= the 32-bit instruction from the dispatcher.
IMM <= MUX { INSTR[9:0], HOST_IN }

The dispatcher selects the source for `IMM`:

- `INSTR[9:0]` (zero-extended to 32 bits) during normal microcode execution with immediate operands.
- `HOST_IN` (32-bit) when executing a user stack push from Port 0x70.

There is a multi-signal output bus multiplexer (`RES_MUX`) that selects the output bundle from the active block:

```text
BLK_BUS_i [53:0] = { BLK_RES[31:0], BLK_RES_SEL[3:0], RES_STATUS[7:0], STATUS_WR_SEL[7:0], EXEC_WB, EXEC_DONE }

{RES_BUS, RES_SEL, RES_STATUS, STATUS_WR_SEL, EXEC_WB, EXEC_DONE} = MUX { BLK_BUS_1, ..., BLK_BUS_k }
```

*(Note: In the MachXO2 architecture, each PFU block provides 53 inputs and 25 outputs across its 4 slices / 8 LUT4s. A
54-bit wide multiplexer across $k$ functional blocks naturally bit-slices across multiple PFUs using general
interconnect and dedicated MUXF7/MUXF8 multiplexer resources.)*

To reduce power consumption, we want an AND wall in front of each BLK, so only the needed block gets
changing signals.

HA_BUS, HB_BUS -> AND_WALL_k -> BLK_k

- The dispatcher sets the WALL selectors from `OPCODE[5:3]`.
- The instruction decoder sets the HA_BUS and HB_BUS selectors. A 64-bit instruction may need 2 cycles to read the LO
  and HI halves.
- This means that a BLK cannot directly call anything in a different BLK. That has to be orchestrated by the
  microcode via the dispatcher. Registers (except FX) and Scratch Memory are persistent through the dispatcher.
- The active BLK drives `BLK_RES_SEL` to designate the target register for write-back (it may use AL then AH, e.g., in
  two write-backs for a 64-bit operation). Likewise, specific register write enables and `STATUS` bits are latched on
  `EXEC_WB`.
- Some blocks may have result registers, e.g. the 64-bit multiplier will have 128-bits of output, so it might have its
  own result register and mux to feed the RES_BUS mux. This is TBD. If we can do the 32x32->64 or 64x64->128 via
  microcode and limit the hardware, that might be a win if we are short on space.

### Block Input and Output

INPUTS to each block:

- `HA_BUS[31:0]`
- `HB_BUS[31:0]`
- `STATUS[7:0]`
- `INSTR[31:16]`
- `EXEC_READY`

OUTPUTS from each block:

- `BLK_RES[31:0]`
- `BLK_RES_SEL[3:0]`,
- `RES_STATUS[7:0]`,
- `STATUS_WR_SEL[7:0]` (which bits to write)
- `EXEC_WB` (asserted for 1 cycle when RES_BUS has valid write-back data)
- `EXEC_DONE` (asserted for 1 cycle when block execution is complete)

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
- HOST_IN Byte Packer: The Z80 writes to Port 0x70 one byte at a time. The byte packer accumulates 4 bytes into
  `HOST_IN`. When full (4 bytes), it signals the dispatcher, which routes `IMM <= HOST_IN` and executes `LDI FL, IMM`
  followed by `PUSH FL` to commit the word to the stack.
- HOST_OUT Byte Serializer: When the Z80 reads from Port 0x70, the dispatcher executes `POP FL` to stage a 32-bit word
  into `HOST_OUT`, which delivers bytes 0..3 sequentially across Port 0x70 reads.
- CMD_REG: Latches the 8-bit user opcode written to Port 0x71 to trigger microcode dispatch or enqueue into the batch
  queue.
- DEC_C (C-1), decrement the counter

## Timing

The dispatcher will set an EXEC_READY flag for 1 FPU cycle when all the control lines are setup.

The ALU and MEM subsystems will then execute for 1 or more cycles. They will set the EXEC_WB flag for 1 cycle when the
result is ready to be written out of the RES_MUX. They may do multiple write back cycles.

When the BLK is done, it will set the EXEC_DONE flag for 1 FPU cycle, which will trigger the dispatcher to go to the
next instruction fetch, or loop until ready.

## Machine Instruction (INSTR)

```text
 31        26 25  24     21 20    17 16        14 13     11 10 9                      0
+------------+---+---------+--------+------------+---------+-+-----------------------+
|   OPCODE   | W |   DST   | SRC2   | FLAG_COND  |  SRC1   | |   IMMEDIATE / ADDR    |
|   [5:0]    |   |  [3:0]  | [3:0]  |   [2:0]    |  [2:0]  | |         [9:0]         |
+------------+---+---------+--------+------------+---------+-+-----------------------+
```

The immediate, address, offset values can be up to 10 bits, which is enough to address
up to 1K PC locations (in 4-byte words) or immediate values 0 - 1023.

If SRC1 is None (1111), then binary operands like "AND AL, BL" mean `AL <- AL & BL`.
If SRC1 is a valid `HA_MUX` register, then binary operands have a distinct
output register, e.g. "SUB DL, AL, BL" means `DL <- AL - BL`.

Opcodes are a 3 bit block ID plus a 3 bit operation ID. This means we can group
BLK by the first three bits for the purpose of activating the AND walls.

| Block              | Prefix | Notes                                                   |
|--------------------|--------|---------------------------------------------------------|
| Arithmetic / Adder | 0b000  | Shared AND wall with 0b001 (co-located fast math block) |
| Math / Float / Div | 0b001  | Pack/Unpack, Hardware Divide/Mod, co-located with 0b000 |
| Logic              | 0b010  | AND, OR, XOR, ABS, CHS, NOT                             |
| Ctrl               | 0b011  | Branch, Call, Return, Trap, Halt                        |
| Mem                | 0b100  | Stack PUSH/POP, Internal RAM load/store                 |
| Mem (User)         | 0b101  | User storage load/store                                 |
| Shifter            | 0b110  | LSL, LSR, ASL, ASR, RRC, RLC, LZC                       |
| Reserved           | 0b111  | Reserved for expansion                                  |

A unified 4-bit register encoding is used across `INSTR[24:21]` (`dst`), `INSTR[20:17]` (`src`), `HB_BUS` MUX, and
`BLK_RES_SEL` write-back routing.

To save FPGA logic and routing resources, the `HA_BUS` multiplexer physically supports only the first 6 sources
(`0b0000`–`0b0101`), so its physical multiplexer only inspects the lower 3 bits (`[2:0]`). `HB_BUS` and `BLK_RES_SEL`
write-back routing decode the full 4 bits.

| 4-Bit Code | Register / Source | HA_BUS (Physical 3-Bit) | HB_BUS (Full 4-Bit) | RES_SEL Target (on EXEC_WB) |
|:----------:|:-----------------:|:-----------------------:|:-------------------:|:---------------------------:|
|  `0b0000`  |        AL         |      Yes (`0b000`)      |   Yes (`0b0000`)    |      AL (or AX if W=1)      |
|  `0b0001`  |        AH         |      Yes (`0b001`)      |   Yes (`0b0001`)    |             AH              |
|  `0b0010`  |        EA         |      Yes (`0b010`)      |   Yes (`0b0010`)    |         EA (12-bit)         |
|  `0b0011`  |        EB         |      Yes (`0b011`)      |   Yes (`0b0011`)    |         EB (12-bit)         |
|  `0b0100`  |        IMM        |      Yes (`0b100`)      |   Yes (`0b0100`)    |     — (No write / CMP)      |
|  `0b0101`  |         C         |      Yes (`0b101`)      |   Yes (`0b0101`)    |          C (8-bit)          |
|  `0b0110`  |        BL         |      Yes (`0b110`)      |   Yes (`0b0110`)    |      BL (or BX if W=1)      |
|  `0b0111`  |        BH         |      Yes (`0b111`)      |   Yes (`0b0111`)    |             BH              |
|  `0b1000`  |        DL         |            —            |   Yes (`0b1000`)    |      DL (or DX if W=1)      |
|  `0b1001`  |        DH         |            —            |   Yes (`0b1001`)    |             DH              |
|  `0b1010`  |        FL         |            —            |   Yes (`0b1010`)    |      FL (or FX if W=1)      |
|  `0b1011`  |        FH         |            —            |   Yes (`0b1011`)    |             FH              |
|  `0b1100`  |        TOS        |            —            |          —          |     Hardware Stack Push     |
|  `0b1101`  |        UPC        |            —            |          —          |     UPC (Branch/Return)     |
|  `0b1110`  |     HOST_OUT      |            —            |          —          |    Port 0x70 Staging Reg    |
|  `0b1111`  |       NONE        |            —            |          —          | Discard result (CMP, TEST)  |

- For BINARY functions, the instruction decoder routes operands to `HA_MUX` and `HB_MUX`.
- For UNARY functions, a single bus is used as the source; it may vary by instruction.
- All functions return their result bundle via `BLK_BUS_i` to `RES_MUX`. Some MEM functions write directly to RAM
  without asserting `EXEC_WB`. Control functions may update `SP` or `UPC` directly.

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

| mnemonic          | OPCODE    | W     | RES_SEL | HA_MUX | HB_MUX | Details                            | Status Registers                      |
|-------------------|-----------|-------|---------|--------|--------|------------------------------------|---------------------------------------|
| ADD dst, src      | 0b000_000 | 0/1   | dst     | dst    | src    | `dst <- dst + src`                 | sets ZF, SF, CF, VF                   |
| ADC dst, src      | 0b000_001 | 0/1   | dst     | dst    | src    | `dst <- dst + src + CF`            | sets ZF, SF, CF, VF                   |
| SUB dst, src      | 0b000_010 | 0/1   | dst     | dst    | src    | `dst <- dst - src`                 | sets ZF, SF, CF, VF                   |
| SBB dst, src      | 0b000_011 | 0/1   | dst     | dst    | src    | `dst <- dst - src - CF`            | sets ZF, SF, CF, VF                   |
| CMP dst, src      | 0b000_100 | 0/1   | NONE    | dst    | src    | `dst - src` (updates flags)        | sets ZF, SF, CF, VF                   |
| EXP_ADD EA, src   | 0b000_101 | 0     | EA      | EA     | src    | `EA <- EA + EB` or immediate       | sets ZF, SF, VF (>1023), UF (<-1022)  |
| EXP_SUB EA, src   | 0b000_110 | 0     | EA      | EA     | src    | `EA <- EA - EB` or immediate       | sets ZF, SF, VF (>1023), UF (<-1022)  |
| MOD dst, src      | 0b000_111 | 0/1   | dst     | dst    | src    | `dst <- dst % src` (remainder)     | sets ZF, SF, VF, ERR (on div-by-zero) |
| PACK dst, exp     | 0b001_000 | 0/1   | dst     | exp    | dst    | `dst <- dst & exp & sign`          | sets ZF, SF, VF, UF                   |
| UNPACK dst, exp   | 0b001_001 | 0/1   | dst     | exp    | dst    | exp <- dst.exp, dst <- mantissa    | sets ZF, SF, DF (sign_A ^ sign_B)     |
| MUL dst, src      | 0b001_010 | 0/1   | dst     | dst    | src    | `dst <- dst * src` (Booth mul)     | sets ZF, SF, VF                       |
| DIV dst, src      | 0b001_011 | 0/1   | dst     | dst    | src    | `dst <- dst / src`, DL/DX <- rem   | sets ZF, SF, VF, ERR (on div-by-zero) |
| -----             | -----     | ----- | -----   | -----  | -----  | -----                              | -----                                 |
| AND dst, src      | 0b010_000 | 0/1   | dst     | dst    | src    | `dst <- dst & src`                 | sets ZF, SF, clears CF <- 0, VF <- 0  |
| OR dst, src       | 0b010_001 | 0/1   | dst     | dst    | src    | `dst <- dst \| src`                | sets ZF, SF, clears CF <- 0, VF <- 0  |
| XOR dst, src      | 0b010_010 | 0/1   | dst     | dst    | src    | `dst <- dst  ^ src`                | sets ZF, SF, clears CF <- 0, VF <- 0  |
| ABS dst           | 0b010_011 | 0/1   | dst     | n/a    | dst    | absolute value                     | sets ZF, clears SF <- 0               |
| CHS dst           | 0b010_100 | 0/1   | dst     | n/a    | dst    | change sign                        | sets SF <- ~SF                        |
| NOT dst           | 0b010_101 | 0/1   | dst     | n/a    | dst    | bitwise complement                 | sets ZF, SF                           |
| -----             | -----     | ----- | -----   | -----  | -----  | -----                              | -----                                 |
| LSL dst\[, src\]  | 0b110_000 | 0/1   | dst     | src    | dst    | `dst <- dst << src` (C implied)    | sets ZF, SF, CF                       |
| LSR dst\[, src\]  | 0b110_001 | 0/1   | dst     | src    | dst    | `dst <- dst >> src` (C implied)    | sets ZF, clears SF <- 0, sets CF      |
| ASL dst\[, src\]  | 0b110_010 | 0/1   | dst     | src    | dst    | `dst <- dst << src` (C implied)    | sets ZF, SF, CF, VF                   |
| ASR dst\[, src\]  | 0b110_011 | 0/1   | dst     | src    | dst    | `dst <- dst >> src` (C implied)    | sets ZF, SF, CF                       |
| RRC dst           | 0b110_100 | 0/1   | dst     | n/a    | dst    | circular rotate right              | sets ZF, SF, CF                       |
| RLC dst           | 0b110_101 | 0/1   | dst     | n/a    | dst    | circular rotate left               | sets ZF, SF, CF                       |
| LZC dst, src      | 0b110_110 | 0/1   | dst     | n/a    | src    | `dst <- leading zero count of src` | sets ZF (if src == 0)                 |
| -----             | -----     | ----- | -----   | -----  | -----  | -----                              | -----                                 |
| PUSH src          | 0b100_000 | 0/1   | TOS     | n/a    | src    | `TOS <- src`, sp <- sp + W + 1     | sets VF, ERR (on stack overflow)      |
| POP dst           | 0b100_001 | 0/1   | dst     | n/a    | TOS    | `dst <- TOS`, sp <- sp - (W+1)     | sets UF, ERR (on stack underflow)     |
| LDC dst, addr     | 0b100_010 | 0/1   | dst     | IMM    | n/a    | `dst <- CONST_ADDR + [addr]`       | none (flags unaffected)               |
| LDI dst, imm      | 0b100_011 | 0/1   | dst     | IMM    | n/a    | `dst <- imm`                       | none (flags unaffected)               |
| LDI flag, val     | 0b100_011 | 0     | NONE    | IMM    | n/a    | `status[flag] <- imm & 1`          | sets/clears selected flag (0 or 1)    |
| LD  dst, addr     | 0b100_100 | 0/1   | dst     | IMM    | n/a    | `dst <- SCR_ADDR + [addr]`         | none (flags unaffected)               |
| STO  addr, src    | 0b100_101 | 0/1   | IMM     | n/a    | src    | `SCR_ADDR + [addr] <- src`         | none (flags unaffected)               |
| MOV dst, src      | 0b100_110 | 0/1   | dst     | n/a    | src    | `dst <- src`                       | none (flags unaffected)               |
| SWAP dst, src     | 0b100_111 | 0/1   | dst     | n/a    | src    | `F_ <- src, src <- dst, dst <- F_` | none (flags unaffected)               |
| LDU dst, addr     | 0b101_000 | 0/1   | dst     | IMM    | n/a    | `dst <- USER_ADDR + [addr]`        | none (flags unaffected)               |
| STU addr, src     | 0b101_001 | 0/1   | dst     | IMM    | n/a    | `USER_ADDR + [addr] <- src`        | none (flags unaffected)               |
| SSAV              | 0b101_110 | 0     | n/a     | n/a    | n/a    | STATUS save                        | Stashes STATUS reg to shadow          |
| SRES              | 0b101_111 | 0     | n/a     | n/a    | n/a    | STATUS restore                     | Unstash STATUS from shadow            |
| -----             | -----     | ----- | -----   | -----  | -----  | -----                              | -----                                 |
| JMP addr          | 0b011_000 | 0     | UPC     | IMM    | n/a    | `upc <- addr`                      | none                                  |
| JNZ \[src,\] addr | 0b011_001 | 0     | UPC     | IMM    | n/a    | `upc <- addr` if !ZF or `src != 0` | none                                  |
| JZ \[src,\] addr  | 0b011_010 | 0     | UPC     | IMM    | n/a    | `upc <- addr` if ZF  or `src == 0` | none                                  |
| DJNZ addr         | 0b011_011 | 0     | UPC     | IMM    | n/a    | `dec C, upc <- addr` if !ZF        | sets ZF (from dec C)                  |
| CALL addr         | 0b011_100 | 0     | UPC     | IMM    | n/a    | `ret <- upc, upc <- addr`          | none                                  |
| RET               | 0b011_101 | 0     | UPC     | n/a    | n/a    | `upc <- ret`                       | none                                  |
| NOP               | 0b011_110 | 0     | NONE    | n/a    | n/a    | No operation (pipeline bubble)     | none (flags unaffected)               |
| HALT              | 0b011_111 | 0     | UPC     | n/a    | n/a    | end execution normally, pulse EXEC_DONE | clears BSY <- 0                   |

---

For detailed documentation, status flags, register transfers, bit patterns, and concrete examples for every instruction,
see the [Microcode Instruction Reference Manual](SystemReference.md).
