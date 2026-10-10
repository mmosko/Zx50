# Zx50 FPU Rev 2 Low-Level System Design

## Registers

all 32bit unless said othewise

- (AH, AL) = AX
- (BH, BL) = BX
- (CH, CL) = CX
- (DH, DL) = DX
- (FH, FL) = FX
- C (8 bit counter / opcode parameter register; automatically latched with UserOpcode[3:0] on dispatch)
- EA, EB (12-bit exponent registers)
- SP (8 bit) stack pointer
- OSP (5 bit) operation stack pointer for user BATCH mode (32-byte queue)
- UPC (10 bit), microcode program counter (addresses 1,024 words x 32-bit in CODE_ROM)
- STATUS (8 bit), status register [7: BSY, 6: D, 5: S, 4: C, 3: V, 2: U, 1: ERR, 0: Z]
- CALL_STACK (16 words x 10 bit), return address stack in distributed LUT RAM with 4-bit CSP pointer (supports up to 16
  nested CALL levels)
- HOST_IN (32-bit), host input staging register (accumulates 4 bytes from Port 0x70 writes)
- HOST_OUT (32-bit), host output staging register (stages 4 bytes for Port 0x70 reads)
- CMD_REG (8-bit), command latch for Port 0x71 user opcodes

## Functional Blocks

![Functional Blocks](fpu_alu.svg)

There are a small number of synthesized functional blocks that are then shared by the micro-opcodes (machine
instructions). We denote these as BLK_1, BLK_2, ..., BLK_k. We need to minimize the number of blocks.

There is an HA_BUS and HB_BUS (32-bit). Each is fed by a multiplexer.

```text
HA_BUS <= MUX {AL, AH, BL, BH, CL, CH, DL, DH, FL, FH, EA, EB, C, IMM}
HB_BUS <= MUX {AL, AH, BL, BH, CL, CH, DL, DH, FL, FH, EA, EB, C, IMM}
INSTR_BUS <= the 32-bit instruction from the dispatcher.
IMM <= MUX { INSTR[9:0], HOST_IN }
```

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
- SHIFTER: LSL, LSR, LZC
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
- UPC ADDER (UPC + 1), 10-bit modulo-1024 microcode counter, increments 4-byte instruction words in CODE_ROM
- HOST_IN Byte Packer: The Z80 writes to Port 0x70 one byte at a time. The byte packer accumulates 4 bytes into
  `HOST_IN`. When full (4 bytes), it signals the dispatcher, which routes `IMM <= HOST_IN` and executes `LDI FL, IMM`
  followed by `PUSH FL` to commit the word to the stack.
- HOST_OUT Byte Serializer: When the Z80 reads from Port 0x70, the dispatcher executes `POP FL` to stage a 32-bit word
  into `HOST_OUT`, which delivers bytes 0..3 sequentially across Port 0x70 reads.
- CMD_REG: Latches the 8-bit user opcode written to Port 0x71 to trigger microcode dispatch or enqueue into the batch
  queue. Upon dispatching an opcode to initiate microcode execution, the dispatcher automatically latches the lower
  nibble (`CMD_REG[3:0]`) into register `C` (`C[3:0] <= CMD_REG[3:0]`, `C[7:4] <= 0`), passing indexed parameters (such
  as scratchpad slot numbers 0..15, shift distances, or loop bounds) directly into microcode.
- DEC_C (C-1), decrement the counter
- CALL_STACK & CSP: 16-entry × 10-bit LUT RAM with 4-bit Call Stack Pointer (`CSP[3:0]`). On `CALL addr`, pushes
  `UPC + 1`
  to `CALL_STACK[CSP]`, increments `CSP`, and branches to `addr`. On `RET`, decrements `CSP` and restores `UPC` from
  `CALL_STACK[CSP]`.

### Hardware Call Stack & Subroutine Modularity

To enable composable mathematical algorithms (e.g., `POW_F32` synthesized as $2^{X \cdot \log_2 (Y)}$, `TAN_F32`
utilizing
`DIV_F32_CORE`, and floating-point addition/subtraction sharing `ADD_F32_CORE`), the control block incorporates a
hardware
return-address call stack:

* **Capacity & Implementation:** 16 words × 10 bits implemented in distributed LUT RAM (`RAM16X1S` / `RAM16X1D`
  primitives
  in MachXO2/MachXO3 PFU Slices). Consumes 10 LUT4s and 0 EBR blocks.
* **Call Stack Pointer (CSP):** A 4-bit synchronous up/down pointer register (`CSP[3:0]`, range 0..15).
* **Nesting Depth:** Supports up to 16 levels of subroutine calls, easily accommodating nested execution hierarchies
  (e.g., `USER_POW_F32` $\to$ `LOG2_CORE` $\to$ `NORMALIZE_F32`).
* **Reusable Mathematical Cores:**
    - `ADD_F32_CORE` / `SUB_F32_CORE`: Takes float operands in `AL` and `BL`, returns sum/difference in `AL`.
    - `MUL_F32_CORE`: Multiplies `AL` and `BL`, returns float product in `AL`.
    - `DIV_F32_CORE`: Divides `AL` by `BL`, returns float quotient in `AL`.
    - `SQRT_F32_CORE`: Evaluates reciprocal square root polynomial/NR and returns $\sqrt{\text{AL}}$ in `AL`.
    - `LOG2_CORE`: Computes $\log_2 (\text{AL})$, returns float result in `AL`.
    - `EXP2_CORE`: Computes $2^{\text{AL}}$, returns float result in `AL`.
    - `NORMALIZE_F32`: Normalizes mantissa in `AL` with exponent in `EA` and sign in `AH[31]`, returning packed IEEE-754
      float in `AL`.

## Timing

The dispatcher will set an EXEC_READY flag for 1 FPU cycle when all the control lines are setup.

The ALU and MEM subsystems will then execute for 1 or more cycles. They will set the EXEC_WB flag for 1 cycle when the
result is ready to be written out of the RES_MUX. They may do multiple write back cycles.

When the BLK is done, it will set the EXEC_DONE flag for 1 FPU cycle, which will trigger the dispatcher to go to the
next instruction fetch, or loop until ready.

## Machine Instruction (INSTR)

```text
 31        26  25        21       17           14        10                        0
+------------+---+---------+--------+------------+---------+-+-----------------------+
|   OPCODE   | W |   DST   | SRC2   | FLAG_COND  |  SRC1   |     IMMEDIATE / ADDR    |
|   [5:0]    |   |  [3:0]  | [3:0]  |   [2:0]    |  [3:0]  |           [9:0]         |
+------------+---+---------+--------+------------+---------+-+-----------------------+
```

The immediate, address, offset values can be up to 10 bits, which is enough to address
up to 1K PC locations (in 4-byte words) or immediate values 0 - 1023.

If SRC1 is None (`0b1111`), then binary operands like "AND AL, BL" mean `AL <- AL & BL`.
If SRC1 is a valid `HA_MUX` register, then binary operands have a distinct
output register, e.g. "SUB DL, AL, BL" means `DL <- AL - BL`.

Opcodes are a 3 bit block ID plus a 3 bit operation ID. This means we can group
BLK by the first three bits for the purpose of activating the AND walls. The `Math`
and `Memory` blocks span two block codes -- they have a single AND wall that is activated
by both blocks.

| Block    | Prefix | Notes                                                   |
|----------|--------|---------------------------------------------------------|
| Math     | 0b000  | Shared AND wall with 0b001 (co-located fast math block) |
|          | 0b001  | Pack/Unpack, Hardware Multiply/Divide, co-located 0b000 |
| Logic    | 0b010  | AND, OR, XOR, FABS, FCHS, NOT                           |
| Ctrl     | 0b011  | Branch, Call, Return, Trap, Halt                        |
| Memory   | 0b100  | Stack PUSH/POP, Internal RAM load/store                 |
|          | 0b101  | User storage load/store                                 |
| Shifter  | 0b110  | LSL, LSR, ASL, ASR, LZC                                 |
| Reserved | 0b111  | Reserved for expansion                                  |

A unified 4-bit register encoding is used across `INSTR[24:21]` (`dst`), `INSTR[20:17]` (`src2`), `INSTR[13:10]`
(`src1`),
`HA_BUS` MUX, `HB_BUS` MUX, and `BLK_RES_SEL` write-back routing.

Both `HA_BUS` and `HB_BUS` multiplexers are fully symmetric 16-input multiplexers decoding the full 4-bit register code
(`[3:0]`).
This eliminates register shuffling constraints and allows any general-purpose register to serve as `src1`, `src2`, or
`dst`.

Note that `src1` in the machine word uses `0b1111` (`NONE`) when an operation uses the default destination as `src1` or
has no left operand.

| 4-Bit Code | Register / Source | HA_BUS (Full 4-Bit) | HB_BUS (Full 4-Bit) | RES_SEL Target (on EXEC_WB) | Description / Role                      |
|:----------:|:-----------------:|:-------------------:|:-------------------:|:---------------------------:|:----------------------------------------|
|  `0b0000`  |        AL         |   Yes (`0b0000`)    |   Yes (`0b0000`)    |      AL (or AX if W=1)      | General / Accumulator Low               |
|  `0b0001`  |        AH         |   Yes (`0b0001`)    |   Yes (`0b0001`)    |             AH              | General / Accumulator High              |
|  `0b0010`  |        BL         |   Yes (`0b0010`)    |   Yes (`0b0010`)    |      BL (or BX if W=1)      | General Operand B Low                   |
|  `0b0011`  |        BH         |   Yes (`0b0011`)    |   Yes (`0b0011`)    |             BH              | General Operand B High                  |
|  `0b0100`  |        CL         |   Yes (`0b0100`)    |   Yes (`0b0100`)    |      CL (or CX if W=1)      | General Register C Low                  |
|  `0b0101`  |        CH         |   Yes (`0b0101`)    |   Yes (`0b0101`)    |             CH              | General Register C High                 |
|  `0b0110`  |        DL         |   Yes (`0b0110`)    |   Yes (`0b0110`)    |      DL (or DX if W=1)      | General Scratch D Low                   |
|  `0b0111`  |        DH         |   Yes (`0b0111`)    |   Yes (`0b0111`)    |             DH              | General Scratch D High                  |
|  `0b1000`  |        FL         |   Yes (`0b1000`)    |   Yes (`0b1000`)    |      FL (or FX if W=1)      | General Scratch F Low                   |
|  `0b1001`  |        FH         |   Yes (`0b1001`)    |   Yes (`0b1001`)    |             FH              | General Scratch F High                  |
|  `0b1010`  |        EA         |   Yes (`0b1010`)    |   Yes (`0b1010`)    |         EA (12-bit)         | Exponent Register A (Float unpack/pack) |
|  `0b1011`  |        EB         |   Yes (`0b1011`)    |   Yes (`0b1011`)    |         EB (12-bit)         | Exponent Register B (Float unpack/pack) |
|  `0b1100`  |         C         |   Yes (`0b1100`)    |   Yes (`0b1100`)    |          C (8-bit)          | Dedicated Loop / Shift Counter (`DJNZ`) |
|  `0b1101`  |        IMM        |   Yes (`0b1101`)    |   Yes (`0b1101`)    |     — (No write / CMP)      | Instruction Immediate Constant          |
|  `0b1110`  |        UPC        |          —          |          —          |     UPC (Branch/Return)     | Microprogram Counter Writeback Target   |
|  `0b1111`  |       NONE        |          —          |          —          | Discard result (CMP, TEST)  | No register read / No writeback         |

- For BINARY functions, the instruction decoder routes operands to `HA_MUX` and `HB_MUX`.
- For UNARY functions, a single bus is used as the source; it may vary by instruction.
- All functions return their result bundle via `BLK_BUS_i` to `RES_MUX`. Some MEM functions write directly to RAM
  without asserting `EXEC_WB`. Control functions may update `SP` or `UPC` directly.

All Arithmetic operations are to AL or AX (depending on W). So they do not really need
the "AL" or "AX" in the mnemonic, but we include it for clarity.

The exception are the EXP_ADD and EXP_SUB which use the EA and EB. But they still use the HA_BUS and HB_BUS mux.

### Opcode Allocation & Block Prefixes

Micro-opcodes (`OPCODE[5:0]`) are divided into a 3-bit block prefix (`OPCODE[5:3]`) and a 3-bit operation identifier
(`OPCODE[2:0]`). The 3-bit block prefix enables the dispatcher to selectively activate only the relevant functional
block and its input AND walls:

- **`0b000` & `0b001` (Math Block):** Shared hardware resources for addition/subtraction, 12-bit exponent math, Booth
  multiplication, restoring division, and IEEE-754 pack/unpack. Blocks `0b000` and `0b001` share the same AND wall and
  internal functional units.
- **`0b010` (Logic Block):** Bitwise operations (`AND`, `OR`, `XOR`, `NOT`) and floating-point sign manipulation
  (`FABS`, `FCHS`).
- **`0b011` (Control Block):** Branching (`JMP`, `JZ`, `JNZ`), loop control (`DJNZ`), call stack management (`CALL`,
  `RET`), pipeline control (`NOP`), and sequencer completion (`HALT`).
- **`0b100` & `0b101` (Memory Block):** Math stack operations (`PUSH`, `POP`), scratchpad RAM access (`LD`, `STO`,
  `LDU`, `STU`), constant/LUT table lookup (`LDC`), immediate loads (`LDI`), register transfers (`MOV`, `SWAP`), and
  status shadowing (`SSAV`, `SRES`). Blocks `0b100` and `0b101` share the same memory controller and AND wall.
- **`0b110` (Shifter Block):** Barrel shifter for logical (`LSL`, `LSR`), arithmetic (`ASL`, `ASR`), and count leading
  zeros (`LZC`).
- **`0b111` (Reserved):** Unallocated, reserved for future coprocessor expansion.

For the full instruction set summary detailing operand encodings, execution cycles, status flags matrix, and RTL
semantics, see [SystemReference.md](SystemReference.md#1-summary-of-the-microcode-instruction-set).


## Memory Architecture & SysMEM EBR Subsystem

The MachXO2-2000 provides 8 physical 9-Kbit SysMEM EBR blocks. In Rev 2, these are organized symmetrically into two
4-block clusters ($1024 \times 32$-bit each):

1. **`DATA_RAM` (EBR 0, 1, 2, 3):** Cascaded $1024 \text{ words} \times 32 \text{ bits}$ RAM (4,096 Bytes).
    - Single 10-bit address bus `MEM_ADDR[9:0]` (`0x000`–`0x3FF`).
    - Cleanly segregated at word boundary `0x100` into **1 KB RAM Space** (`0x000`–`0x0FF`) and **3 KB ROM Space**
      (`0x100`–`0x3FF`).
2. **`CODE_ROM` (EBR 4, 5, 6, 7):** Cascaded $1024 \text{ words} \times 32 \text{ bits}$ ROM/RAM (4,096 Bytes).
    - Sequenced directly by 10-bit `UPC[9:0]` (`0x000`–`0x3FF`) to fetch 32-bit micro-instructions (`INSTR[31:0]`).
3. **PFU Distributed LUT-RAM (0 EBR blocks consumed):**
    - 32-byte circular Operation Stack (`OSP[4:0]`) for user batch opcode queueing.

### `DATA_RAM` Memory Map (`MEM_ADDR[9:0]`)

| Word Range (Hex) | Word Range (Dec) | Size            | Region  | Allocation                                                                         | Addressing Mechanism                                 |
|:-----------------|:-----------------|:----------------|:--------|:-----------------------------------------------------------------------------------|:-----------------------------------------------------|
| `0x000`–`0x07F`  | 0..127           | 128 W (512 B)   | **RAM** | Hardware Math Stack                                                                | `10'h000 \| SP[6:0]`                                 |
| `0x080`–`0x0BF`  | 128..191         | 64 W (256 B)    | **RAM** | Scratchpad RAM `SCR[0..63]`                                                        | `10'h080 \| HA_MUX[5:0]` (`imm[5:0]` or `src1[5:0]`) |
| `0x0C0`–`0x0CF`  | 192..207         | 16 W (64 B)     | **RAM** | User Word Storage `USR[0..15]`                                                     | `10'h0C0 \| imm[3:0]`                                |
| `0x0D0`–`0x0FF`  | 208..255         | 48 W (192 B)    | **RAM** | Extra RAM Headroom                                                                 | Working scratch storage                              |
| `0x100`–`0x13F`  | 256..319         | 64 W (256 B)    | **ROM** | IEEE-754 Math Constants ($\pi, e, \ln 2$)                                          | `10'h100 \| slot[5:0]`                               |
| `0x140`–`0x1FF`  | 320..511         | 192 W (768 B)   | **ROM** | Extra ROM Headroom                                                                 | Float64 / FIR / Poly headroom                        |
| `0x200`–`0x27F`  | 512..639         | 128 W (512 B)   | **ROM** | Trig & CORDIC Angles                                                               | `10'h200 \| slot[6:0]`                               |
| `0x280`–`0x2FF`  | 640..767         | 128 W (512 B)   | **ROM** | Chebyshev Polynomial Coeffs                                                        | `10'h280 \| slot[6:0]`                               |
| `0x300`–`0x3FF`  | 768..1023        | 256 W (1,024 B) | **ROM** | Interleaved RECIP / SQRT Seeds<br>• `[31:16]`: SQRT Seed<br>• `[15:0]`: RECIP Seed | `10'h300 \| slot[7:0]`                               |

### Hardware Write-Protection

Because all RAM space resides strictly within the first 256 words (`0x000`–`0x0FF`, where `MEM_ADDR[9:8] == 2'b00`),
write protection for all ROM tables is implemented with a single 2-input gate:

```verilog
// Write enable is asserted ONLY when writing within RAM space (mem_addr[9:8] == 2'b00)
assign data_ram_we = is_write & (mem_addr[9:8] == 2'b00);
```

Any unintended write to addresses $\ge \text{0x100}$ is automatically suppressed by hardware, eliminating any risk of
microcode overwriting math constants or seed lookup tables.

### LD and STO addresses

`LD` and `STO` can use direct addressing (the `IMM`) or indirect addressing (e.g. `[BL]`).  If the source is anything
except `IMM`, it is indirect addressing by the contents of that register.

Examples:

```text
LD AX, [BL]  ; Indirect addressing, uses the bottom 5 bits of BL
LD AX, 12    ; Direct addressing
STO [C], AH  ; Indirect, users count register bottom 5 bits
STO 63, AH   ; Direct
```

### LDC Address Generator & Constant ROM Interface

To eliminate arithmetic adders and avoid carry-chain delays on the critical address path, table lookups
(`LDC dst, tbl, addr`) utilize power-of-two base alignment in `DATA_RAM`.

The 3-bit table selector `tbl` (`SRC[2:0]`) specifies the mathematical table:

| Table ID (`tbl`) | Constant Table | Base Address in `DATA_RAM` | Offset Mask |           Output Datapath Width           |
|:----------------:|:---------------|:--------------------------:|:-----------:|:-----------------------------------------:|
|  `0` (`0b000`)   | `CONST`        |    `10'h100` (Word 256)    |   `6'h3F`   |           32-bit IEEE-754 Word            |
|  `1` (`0b001`)   | `TRIG`         |    `10'h200` (Word 512)    |   `7'h7F`   |          32-bit Angle / Constant          |
|  `2` (`0b010`)   | `CHEB`         |    `10'h280` (Word 640)    |   `7'h7F`   |          32-bit Polynomial Coeff          |
|  `3` (`0b011`)   | `RECIP`        |    `10'h300` (Word 768)    |   `8'hFF`   |  Low 16-bit slice `[15:0]` zero-extended  |
|  `4` (`0b100`)   | `SQRT`         |    `10'h300` (Word 768)    |   `8'hFF`   | High 16-bit slice `[31:16]` zero-extended |

#### 10-Bit Address Generation Logic (`MEM_ADDR[9:0]`):

Because every table base is aligned to a power-of-two offset (`0x100`, `0x200`, `0x280`, `0x300`), table address
calculation is a pure bitwise OR:

```verilog
always_comb begin
    case (tbl_sel)
        3'd0:    ldc_addr = 10'h100 | {4'b0000, offset[5:0]}; // CONST: 64 words
        3'd1:    ldc_addr = 10'h200 | {3'b000,  offset[6:0]}; // TRIG:  128 words
        3'd2:    ldc_addr = 10'h280 | {3'b000,  offset[6:0]}; // CHEB:  128 words
        3'd3:    ldc_addr = 10'h300 | {2'b00,   offset[7:0]}; // RECIP: 256 words
        3'd4:    ldc_addr = 10'h300 | {2'b00,   offset[7:0]}; // SQRT:  256 words
        default: ldc_addr = 10'h100 | {4'b0000, offset[5:0]};
    endcase
end
```

#### Datapath Slicing Multiplexer:

The cascaded `DATA_RAM` outputs a single 32-bit word `data_ram_dout[31:0]` in 1 clock cycle. A lightweight multiplexer
selects between full 32-bit words and zero-extended 16-bit seed slices:

```verilog
always_comb begin
    case (tbl_sel)
        3'd3:    ldc_result = {16'h0000, data_ram_dout[15:0]};   // RECIP: low 16-bit slice
        3'd4:    ldc_result = {16'h0000, data_ram_dout[31:16]};  // SQRT:  high 16-bit slice
        default: ldc_result = data_ram_dout[31:0];                // CONST, TRIG, CHEB: 32-bit
    endcase
end
```

Total FPGA hardware cost: **0 adders, 0 carry chains**, 0 wait states, and single-cycle deterministic execution for all
mathematical tables.

---

For detailed documentation, status flags, register transfers, bit patterns, and concrete examples for every instruction,
see the [Microcode Instruction Reference Manual](SystemReference.md).
