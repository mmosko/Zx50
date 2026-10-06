# Zx50 FPU Microcode Assembler Specification (`SystemAssembler.md`)

## 1. Overview and Architecture

The Zx50 FPU microcode assembler (`fasm`) compiles human-readable micro-assembly files (`.fasm`) into binary (`.bin`) and hex (`.hex`) images for the on-chip Embedded Block RAM (EBR) of the Lattice MachXO3 / MachXO2 FPGA.

The assembler's primary responsibilities are:
1. **Contiguous ROM Layout**: Assembles all user opcode implementations and shared routines into a single continuous 512-word (expandable to 1024-word) microcode address space.
2. **Label Resolution**: Converts symbolic labels (forward and backward references) into absolute 10-bit microcode word addresses.
3. **UserOpcode to Microcode Lookup Table**:
   - Detects special opcode entry labels of the form `User.<Name>` (e.g. `User.Abs`, `User.AddF32`).
   - Opcode numbers are decoupled from microcode and defined in an external opcode definition table (e.g. `user_opcodes.def`).
   - The assembler merges the opcode definitions and resolved label addresses to generate an opcode dispatch table (`0xZZ -> 0xYYY`) loaded into a dedicated EBR (e.g. EBR 7) or ROM block.
   - Exports all symbols into a `.sym` symbol file with a dedicated section for the opcode lookup table.
4. **Subroutine Reusability (`CALL` / `RET`)**: Resolves absolute call and return addresses so shared microcode sequences (e.g., exponent alignment, mantissa normalization, rounding, exception trapping) are shared across multiple high-level user opcodes.
5. **Hardware Simplification**: Strictly transforms high-level programmer syntax into fixed-format, deterministic machine words so that Verilog decode logic requires zero multiplexers, zero branch squashing logic, and zero runtime instruction rewriting.
6. **Maintainable Implementation**: Prioritizes code maintainability, clean architecture, and low cyclomatic complexity over raw assembly speed. Uses a structured Python parser/lexer (e.g., Lark or PLY) for the grammar.

---

## 2. Core Architectural Principles for Hardware Simplification

### 2.1 Always-Ternary Machine Word
In the physical FPGA implementation, `HA_MUX` is an 8-to-1 multiplexer that supplies the primary A-operand (`HA_BUS`) to the ALU, subtracter, comparator, and exponent units.

To minimize logic cell (LUT) count and keep decode-stage propagation delays strictly zero:
- **No hardware conditionality on `HA_MUX` select**: The 3 select lines of `HA_MUX` are hardwired directly to bits `[13:11]` of the instruction word (`SRC1`).
- **Assembler synthesizes ternary words**: Regardless of whether the assembly source uses unary, binary, or ternary syntax, the assembler always populates the `SRC1` field in the emitted machine word:
  - **Ternary syntax**:
    - `SUB DL, AL, BL` $\rightarrow$ `DST = DL (0b1000)`, `SRC1 = AL (0b000)`, `SRC2 = BL (0b0110)`
    - `EXP_SUB C, EA, EB` $\rightarrow$ `DST = C (0b0101)`, `SRC1 = EA (0b010)`, `SRC2 = EB (0b0011)`
  - **Binary syntax (Destination is accumulator/source 1)**:
    - `ADD AL, BL` $\rightarrow$ `DST = AL (0b0000)`, `SRC1 = AL (0b000)`, `SRC2 = BL (0b0110)`
    - `CMP EA, EB` $\rightarrow$ `DST = NONE (0b1111)`, `SRC1 = EA (0b010)`, `SRC2 = EB (0b0011)`
    - `EXP_ADD EA, IMM=1` $\rightarrow$ `DST = EA (0b0010)`, `SRC1 = EA (0b010)`, `SRC2 = IMM (0b0100)`
  - **Unary / Stack / Non-ALU syntax**:
    - `POP BL` $\rightarrow$ `DST = BL (0b0110)`, `SRC1 = AL (0b000)`, `SRC2 = NONE (0b1111)`
    - `NOP` / `HALT` $\rightarrow$ `DST = NONE (0b1111)`, `SRC1 = AL (0b000)`, `SRC2 = NONE (0b1111)`

By delegating operand replication to the assembler, the Verilog data path executes:
```verilog
assign ha_mux_sel = instr_reg[13:11]; // Pure wire, 0 LUTs, 0 gate delays
```

### 2.2 Branch Delay Slots and Assembler NOP Insertion
The micro-sequencer runs a 2-stage pipelined fetch/execute cycle:
- **T0 (Fetch)**: The instruction at `UPC` is fetched from EBR, while `UpcAdder` calculates `UPC + 1` in parallel.
- **T1 (Execute)**: The fetched instruction executes in `instr_reg`.

When a branch instruction (`JMP`, `JZ`, `JNZ`, `DJNZ`, `CALL`, `RET`) is taken, the target address is written into `UPC` on the writeback clock edge, but the instruction at `UPC + 1` has already been fetched into the pipeline.

To avoid adding pipeline flush multiplexers or synchronous clear logic into the Verilog fast-path:
- **Hardware is pure feed-forward**: The FPGA does not squash instructions or stall the pipeline. The instruction slot immediately following any taken jump always executes.
- **Assembler-Managed Delay Slots**:
  1. **Default Mode (Automatic NOP Insertion)**: The assembler automatically inserts a single `NOP` cycle immediately following any control-flow instruction (`JMP`, `JZ`, `JNZ`, `DJNZ`, `CALL`, `RET`) and adjusts all branch targets and labels accordingly.
  2. **Optimized Mode (Delay-Slot Scheduling)**: When possible, the assembler moves a preceding independent micro-instruction into the slot following the branch, eliminating the 1-cycle branch penalty entirely.
  3. **Explicit Mode**: Advanced microcode may explicitly specify an instruction in the delay slot using a `.delay` attribute or annotation.

---

## 3. Machine Instruction Word Format (32 Bits)

The assembler produces 32-bit machine words divided between the 21-bit control/instruction register (`reg_file.instr`) and the 10-bit immediate register (`reg_file.imm`), with 1 reserved bit.

```text
 31        26 25  24     21 20    17 16        14 13     11 10 9                      0
+------------+---+---------+--------+------------+---------+-+-----------------------+
|   OPCODE   | W |   DST   |  SRC2  | FLAG_COND  |  SRC1   |R|   IMMEDIATE / ADDR    |
|   [5:0]    |   |  [3:0]  | [3:0]  |   [2:0]    |  [2:0]  | |         [9:0]         |
+------------+---+---------+--------+------------+---------+-+-----------------------+
|<----------------- INSTR [20:0] (21 bits) --------------->| |<- IMM [9:0] (10 bits)->|
```

### 3.1 Field Definitions

| Field | Bits | Width | Description |
|:---|:---|:---|:---|
| **OPCODE** | `[31:26]` | 6 | Micro-operation opcode (Block ID `[2:0]` + Operation ID `[2:0]`). |
| **W** | `[25]` | 1 | Word width select: `0 = 32-bit (W32)`, `1 = 64-bit (W64)`. |
| **DST** | `[24:21]` | 4 | Destination writeback register (`0b0000` to `0b1111`). |
| **SRC2** | `[20:17]` | 4 | Secondary source register selecting from `HB_MUX` (12 inputs). |
| **FLAG_COND**| `[16:14]` | 3 | Status flag condition code for `JZ` / `JNZ` branches. |
| **SRC1** | `[13:11]` | 3 | Primary source register selecting from `HA_MUX` (8 inputs). |
| **RESERVED** | `[10]` | 1 | Reserved (set to `0`). |
| **IMM** | `[9:0]` | 10 | Unsigned immediate constant or 10-bit jump/call address (0–1023). |

### 3.2 Register Field Mapping

#### `SRC1` Select (`HA_MUX` — 3 bits `[13:11]`)
```text
000: AL       010: EA       100: IMM      110: BL
001: AH       011: EB       101: C        111: BH
```

#### `SRC2` Select (`HB_MUX` — 4 bits `[20:17]`)
```text
0000: AL      0011: EB      0110: BL      1001: DH
0001: AH      0100: IMM     0111: BH      1010: FL
0010: EA      0101: C       1000: DL      1011: FH
1111: NONE (No HB operand read)
```

#### `DST` Select (Writeback Register — 4 bits `[24:21]`)
```text
0000: AL      0100: IMM     1000: DL      1100: (reserved)
0001: AH      0101: C       1001: DH      1101: (reserved)
0010: EA      0110: BL      1010: FL      1110: UPC
0011: EB      0111: BH      1011: FH      1111: NONE (No writeback)
```

#### `FLAG_COND` Condition Select (3 bits `[16:14]`)
```text
000: ZERO         (ZF == 1 for JZ, ZF == 0 for JNZ)
001: SIGN         (SF == 1)
010: CARRY        (CF == 1)
011: OVERFLOW     (VF == 1)
100: UNDERFLOW    (UF == 1)
101: ERR          (EF == 1)
110: DIFF_SIGN    (DF == 1)
111: BUSY         (BF == 1)
```

---

## 4. Continuous ROM Layout & Dispatch Model

### 4.1 Address Space Structure (512–1024 Words)

The microcode address space is packed contiguously with user opcode handlers and shared subroutines:

```text
+-----------------------+ 0x000
|  USER OPCODE ROUTINES |
|  - Integer routines   | Packed sequential handler routines.
|  - Conversion routines| Each routine begins with a label
|  - FP arithmetic      | of the form: User.<Name>
+-----------------------+
|  SHARED SUBROUTINES   | Common reusable blocks
|  - _align_f32         | Invoked via CALL, returns via RET
|  - _normalize_f32     |
|  - _trap_underflow    |
+-----------------------+ 0x1FF (Word 511 / 1023)
```

### 4.2 UserOpcode to Microcode Lookup Table (`EBR 7`)

Instead of hardcoding numeric opcode values into the assembler or microcode source files, the numerical mapping is decoupled and configured via an external table:

- **EBR 7 Dispatch Memory**: 256 entries $\times$ 10 bits.
- **Dispatch Flow**:
  1. The host CPU or bus controller writes a `UserOpcode` (e.g. `0x10` for `ADD_F32`) to the FPU command port.
  2. The opcode directly indexes **EBR 7**: `addr = UserOpcode`.
  3. EBR 7 outputs the 10-bit target microcode address: `target_upc = EBR7[UserOpcode]`.
  4. Hardware loads `UPC <= target_upc` in a single clock cycle, starting microcode execution immediately.

#### Symbolic Label Convention: `User.<Name>`
Microcode labels entry points using purely symbolic names:
```fasm
User.AddF32:
    POP     BL
    ...
```
- `User.`: Prefix identifying the label as a user opcode entry point.
- `<Name>`: Human-readable symbolic name (e.g. `AddF32`, `SubF32`, `Abs`).

#### Opcode Definition Table (`user_opcodes.def`)
Numerical opcode assignments are defined in an external mapping table passed to the assembler:
```ini
; user_opcodes.def
; Symbolic Name     Opcode
User.Abs          = 0x01
User.Chs          = 0x02
User.AddF32       = 0x10
User.SubF32       = 0x11
```
- **Clean Separation of Concerns**: Opcode numbers can be renumbered or reorganized without modifying a single line of microcode assembly.
- **Validation**:
  - The assembler checks that every entry in `user_opcodes.def` maps to an existing `User.<Name>` label in microcode.
  - Any unused table entries in EBR 7 are initialized to point to a common `User.Trap` routine.
  - Unmapped `User.<Name>` labels in microcode trigger an assembler warning or error.

### 4.3 Subroutine Mechanism (`CALL` / `RET`)
- **Hardware Support**: ControlBlock includes a 1-deep microcode return register (`reg_file.ret`) and a validity latch (`reg_file.ret_set`).
- **Nesting**: 1 level of subroutine call is supported (no nested calls inside a subroutine).
- **Execution Cost**:
  - `CALL target` (1 cycle) + `NOP` / delay slot (1 cycle)
  - `RET` (1 cycle) + `NOP` / delay slot (1 cycle)
  - Net call overhead: 4 cycles total, saving dozens of duplicate EBR words across floating-point arithmetic opcodes.

---

## 5. Assembly Language Syntax (`fasm`)

### 5.1 General Rules
- **Case-Insensitive**: Opcodes and registers are case-insensitive (`add al, bl` == `ADD AL, BL`).
- **Comments**: Start with `;` or `#` and continue to end of line.
- **Labels**: Defined with a trailing colon (e.g. `L_ALIGN:` or `.normalize:`).

### 5.2 Directives

| Directive | Description |
|:---|:---|
| `.entry <UserOpcode>` | Binds the following block or routine to a specific UserOpcode in the dispatch table. |
| `.subroutine <name>` | Declares a callable shared subroutine. Validates that no nested `CALL` occurs within it. |
| `.org <address>` | Sets the current microcode assembly address counter. |
| `.align <n>` | Pads microcode with `NOP`s until the address is a multiple of `n`. |
| `.global <label>` | Exports a label across multiple source modules. |

### 5.3 Instruction Forms

```fasm
; --- 3-Operand Form (Explicit Destination and Sources) ---
SUB         DL, AL, BL          ; DL <- AL - BL
EXP_SUB     C, EA, EB           ; C  <- EA - EB

; --- 2-Operand Form (Destination acts as Source 1) ---
ADD         AL, BL              ; AL <- AL + BL (Emitted as: DST=AL, SRC1=AL, SRC2=BL)
EXP_ADD     EA, #1              ; EA <- EA + 1  (Emitted as: DST=EA, SRC1=EA, SRC2=IMM=1)
CMP         EA, EB              ; Compare EA - EB (Emitted as: DST=NONE, SRC1=EA, SRC2=EB)

; --- 64-Bit Form (W bit set) ---
ADD.64      AL, BL              ; AX <- AX + BX (W=1, 2 cycles)
MOV.64      DL, AL              ; DX <- AX      (W=1, 2 cycles)

; --- Branches and Calls ---
JMP         L_TARGET            ; Unconditional jump (Assembler emits following NOP)
JZ          ZERO, L_TARGET      ; Jump if ZF == 1
JNZ         CARRY, L_TARGET     ; Jump if CF == 1
JNZ         DIFF_SIGN, L_TARGET ; Jump if sign bit difference is set
DJNZ        L_LOOP              ; Decrement C and jump if C != 0
CALL        .fn_normalize_f32   ; Call shared subroutine
RET                             ; Return from subroutine

; --- Stack and Memory ---
POP         BL                  ; Pop 32-bit stack TOS into BL
PUSH        AL                  ; Push 32-bit AL onto math stack
SWAP        AL, BL              ; Exchange AL and BL (3 cycles)
```

---

---

## 6. Example: Opcode Handlers and Shared Subroutine Pattern

```fasm
; ======================================================================
; USER OPCODE ENTRY POINTS
; ======================================================================

User.AddF32:
    POP     BL
    JNZ     UNDERFLOW, .trap_underflow
    MOV     DL, BL              ; Stash packed B
    POP     AL
    JNZ     UNDERFLOW, .trap_underflow
    MOV     AH, AL              ; Stash packed A for sign
    UNPACK  BL, EB
    JZ      ZERO, .ret_a
    UNPACK  AL, EA
    JZ      ZERO, .ret_b

    ; Call shared alignment subroutine (C <- shift, larger into AL/EA)
    CALL    .sub_align_f32

    ; Perform mantissa arithmetic
    JNZ     DIFF_SIGN, .do_sub
    ADD     AL, BL
    JMP     .do_norm

.do_sub:
    SUB     AL, BL

.do_norm:
    ; Call shared normalization subroutine
    CALL    .sub_normalize_f32

    PACK    AL, EA
    PUSH    AL
    HALT

.ret_a:
    PUSH    AL
    HALT

.ret_b:
    PUSH    DL
    HALT

.trap_underflow:
    HALT

; ======================================================================
; SHARED SUBROUTINES
; ======================================================================

.subroutine .sub_align_f32
    CMP     EA, EB
    JNZ     CARRY, .swap_ops
    JNZ     ZERO, .diff_exp
    CMP     AL, BL
    JNZ     CARRY, .swap_ops
    JMP     .diff_exp

.swap_ops:
    SWAP    AL, BL
    SWAP    EA, EB
    MOV     AH, DL              ; Preserve sign of larger operand

.diff_exp:
    EXP_SUB C, EA, EB           ; C <- EA - EB (1 cycle, 3-operand!)
    CMP     C, #32
    JNZ     CARRY, .shift_bl
    MOV     BL, #0              ; Underflow shift
    RET

.shift_bl:
    LSR     BL, C               ; Align smaller mantissa
    RET
```

*Note: The assembler automatically inserts the required `NOP` delay slots following `JMP`, `JZ`, `JNZ`, `CALL`, and `RET` instructions.*

---

## 7. Assembler Parser and Lexer Architecture

To keep cyclomatic complexity low and the codebase highly maintainable, the assembler avoids ad-hoc regular expression string splitting. Instead, it uses a structured Python lexer/parser architecture (e.g. using `lark` or `ply`):

### 7.1 Multi-Pass Pipeline

```text
Source (.fasm) + Opcode Table (.def)
      │
      ▼
[ Tokenizer / Lexer ]  --> Tokens (Mnemonic, Register, Immediate, LabelDef, Flag)
      │
      ▼
[ Parser / AST ]       --> Instruction Nodes, Directive Nodes, Label Nodes
      │
      ▼
[ Pass 1: Expansion ]  --> Synthesizes ternary operands (SRC1 <= DST if omitted)
                       --> Inserts delay-slot NOPs (or schedules instructions)
      │
      ▼
[ Pass 2: Layout ]     --> Resolves label word addresses (0x000 - 0x3FF)
                       --> Matches User.<Name> against user_opcodes.def to build EBR 7 table
      │
      ▼
[ Pass 3: Emission ]   --> Generates 32-bit machine binary words
      │
      ├──> .hex (Verilog $readmemh)
      ├──> .bin (Raw binary image)
      ├──> .sym (Symbol table + Opcode table)
      └──> .map (Utilization report)
```

---

## 8. Assembler CLI, Outputs, and Symbol File Format

### 8.1 CLI Invocation
```bash
python -m fpu_asm microcode.fasm --opcodes user_opcodes.def -o fpu_rom.hex --bin fpu_rom.bin --sym fpu_rom.sym --map fpu_rom.map
```

### 8.2 Generated Artifacts
1. **`fpu_rom.hex`**: Verilog `$readmemh` ASCII hexadecimal file containing 512 (or 1024) 32-bit hex words for ModelSim, Icarus Verilog, and Lattice Diamond/Radiant EBR initialization.
2. **`fpu_rom.bin`**: Raw binary file (4 bytes per word, little-endian).
3. **`fpu_rom.sym`**: Combined symbol file containing all labels and the specialized opcode dispatch table.
4. **`fpu_rom.map`**: Human-readable symbol map detailing:
   - Base address and instruction count per `UserOpcode`.
   - Shared subroutine entry points and sizes.
   - Total EBR utilization percentage (e.g. `248 / 512 words (48.4%)`).
5. **`fpu_rom.py`**: Python module exporting `MICROCODE_ROM = [0x..., ...]` for direct execution in `fpu_emu`.

### 8.3 Symbol File (`.sym`) Format
The `.sym` file contains a dedicated `[USER_OPCODES]` section specifically designed to initialize the EBR 7 dispatch memory, followed by all local and global labels:

```ini
[USER_OPCODES]
; Opcode  Address  Name
0x01      0x0010   User.Abs
0x02      0x0014   User.Chs
0x10      0x0040   User.AddF32
0x11      0x008A   User.SubF32

[SYMBOLS]
; Address  Scope   Name
0x0040     global  User.AddF32
0x0052     local   .do_sub
0x0054     local   .do_norm
0x0060     local   .ret_a
0x0064     local   .ret_b
0x0070     global  .sub_align_f32
0x0078     local   .swap_ops
0x007E     local   .diff_exp
0x0084     local   .shift_bl
```

