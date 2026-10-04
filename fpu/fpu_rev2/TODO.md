# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)  
Architecture Specifications: [SystemDesignV2.md](SystemDesignV2.md) & [SystemReference.md](SystemReference.md)

---

## Active Tasks

### Task 1: Rewrite ALU & Memory Datapath for V2 Design
- [ ] **Strongly Modeled Bus Multiplexers & AND Walls**:
  - [ ] Implement `HA_MUX` with physical 3-bit selection across `{AL, AH, EA, EB, C, IMM}`.
  - [ ] Implement `HB_MUX` with 4-bit selection across `{AL, AH, BL, BH, DL, DH, FL, FH, C, EA, EB, IMM}`.
  - [ ] Implement `IMM` selection MUX: `{ INSTR[9:0], HOST_IN }`.
  - [ ] Implement AND Wall logic in front of each functional block (`OPCODE[5:3]`) to gate inputs and prevent toggling of unselected blocks.
- [ ] **Enforce Strict Write-back Handshake (`RES_MUX` & `EXEC_WB`)**:
  - [ ] Define bundle structure for each block: `BLK_BUS_i = { BLK_RES[31:0], BLK_RES_SEL[3:0], RES_STATUS[7:0], STATUS_WR_SEL[7:0], EXEC_WB, EXEC_DONE }`.
  - [ ] Implement top-level `RES_MUX` selecting the active `BLK_BUS_i`.
  - [ ] Enforce register updates exclusively through `RES_BUS` on `EXEC_WB` pulse matching `RES_SEL`. Prohibit ad-hoc asynchronous register mutations.
  - [ ] Latch `STATUS[7:0]` bits strictly according to `STATUS_WR_SEL[7:0]` bitmask driven by the active block.
- [ ] **Restructure Functional Blocks to Match V2 Architecture**:
  - [ ] **Block 0 (`0b000`) Arithmetic / Adder**:
    - Unify `ADD`, `ADC`, `SUB`, `SBB`, `CMP`, `EXP_ADD`, `EXP_SUB`.
    - Co-locate single 64-bit Radix-4 Booth multiplier (`MUL`), processing 32-bit (16 cycles) and 64-bit (32 cycles).
  - [ ] **Block 1 (`0b001`) Math / Float / Divider**:
    - Implement `PACK` and `UNPACK` IEEE-754 mantissa/exponent logic.
    - Co-locate integer non-restoring divider engine for `DIV` (quotient) and `MOD` (remainder) with divide-by-zero detection (`ERR=1, V=1`).
  - [ ] **Block 2 (`0b010`) Logic**:
    - Implement bitwise `AND`, `OR`, `XOR`, `NOT`, float `ABS` (clear sign), and float `CHS` (invert sign).
  - [ ] **Block 6 (`0b110`) Shifter & LZC**:
    - Single-cycle barrel shifter for `LSL`, `LSR`, `ASL`, `ASR`, `RRC`, `RLC`.
    - Leading Zero Count (`LZC`) tree logic.
  - [ ] **Block 4 & 5 (`0b100` / `0b101`) Memory & Storage**:
    - `PUSH` and `POP` operating on 32-byte circular `OSP[4:0]` with overflow/underflow detection.
    - Scratchpad access (`LD`, `ST`) and user buffer access (`LDU`, `STU`).
    - Immediate and constant loading (`LDI`, `LDC`).
    - Register moves (`MOV`) and exchanges (`SWAP`).
  - [ ] **Block 3 (`0b011`) Microcode Control**:
    - Micro-sequencer branching: `JMP`, `JNZ`, `JZ`, `DJNZ`, `CALL`, `RET`, `TRAP`, `NOP`.
- [ ] **Update Memory & Register File Models**:
  - [ ] Refactor `fpu_emu/hardware/registers.py` to support `HOST_IN`, `HOST_OUT`, `CMD_REG`, 5-bit `OSP`, and `RET`.
  - [ ] Refactor `fpu_emu/hardware/rom.py` to strictly use `fpu_const_map.py` for all constant lookups.
  - [ ] Remove all hardcoded constants from FP modules and move them into ROM via `tools/build_flash.py`.
- [ ] **Unit Tests**:
  - [ ] Update and expand unit tests in `fpu_emu/tests/` to verify MUX routing, AND wall gating, and write-back enforcement.

---

### Task 2: Transcendental & Trigonometric Functions as Pure Microcode
- [ ] **Decommission Monolithic Hardware Modules**:
  - [ ] Retire monolithic implementations in `fp_exp.py`, `fp_ln.py`, `fp_pow.py`, and `fp_sqrt.py`.
- [ ] **Pure Microcode Transcendental Implementations (`fpu_emu/micro_code.py`)**:
  - [ ] Implement `SQRT` using digit-by-digit or Newton-Raphson iteration using standard adder, Booth multiplier, and shifter primitives.
  - [ ] Implement `EXP` and `LN` using polynomial/rational minimax approximations or Taylor series with Constants ROM table lookups and scratchpad temporaries.
  - [ ] Implement `POW` as $x^y = \exp(y \cdot \ln(x))$ synthesized from microcode routines with edge case handling ($x \le 0$, integer powers, $y = 0$).
- [ ] **Pure Microcode CORDIC Trigonometric Implementations**:
  - [ ] Implement Cody-Waite range reduction ($\text{mod } \pi/2$) with quadrant tracking.
  - [ ] Implement circular CORDIC vector rotation ($z \to 0$ mode) for `SIN`, `COS`, and `TAN` across 24 stages (F32) and 53 stages (F64).
  - [ ] Quadrant reconstruction and IEEE-754 float normalization using `LZC`, `LSL`, `EXP_NORM`, and `PACK`.
  - [ ] Handle tangent asymptotes at $\pm \pi/2$ asserting `VF=1, ERR=1`.
- [ ] **Unit Testing & Accuracy**:
  - [ ] Verify transcendentals and trigonometric functions against IEEE-754 test vectors and special values (zeros, infinities, subnormals, quadrant boundaries).

---

### Task 3: User Opcode Set & Dispatcher Completeness
- [ ] **Port 0x70 / 0x71 Hardware Protocol & Dispatcher**:
  - [ ] Wire `HOST_IN` (32-bit assembly of 4 bytes from Port 0x70) into `IMM` MUX for user `PUSH`.
  - [ ] Wire `HOST_OUT` to stage results for 4-byte host reads from Port 0x70.
  - [ ] Wire `CMD_REG` to capture Port 0x71 opcode writes.
  - [ ] Verify Immediate Blocking (`~BWAIT`), Non-blocking polling (`STATUS.BSY`), and Batch execution modes.
- [ ] **Complete Missing User Opcodes**:
  - [ ] Trigonometrics: `SIN_F32/F64`, `COS_F32/F64`, `TAN_F32/F64`.
  - [ ] Integer division: `DIV_I32`, `DIV_I64`.
  - [ ] Floor / Ceiling: `FLOOR_F32/F64`, `CEIL_F32/F64`.
  - [ ] Conversions: `CONV_I32_F32`, `CONV_F32_I32`, `CONV_I64_F64`, `CONV_F64_I64`, `CONV_F32_F64`, `CONV_F64_F32`.

---

### Task 4: Hardware Support, Simulation & Verilog Implementation
- [ ] **Host Interface Simulation**:
  - [ ] Implement combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
  - [ ] Implement autonomous SPI Flash bootloader copy simulation.
- [ ] **Verilog Implementation**:
  - [ ] Implement modular Verilog RTL corresponding to V2 functional blocks, MUXes, AND walls, and write-back registers.
  - [ ] Write Verilog testbenches with `$fatal` assertions on errors.
  - [ ] Synthesize for Lattice MachXO2 (`LCMXO2-2000HC`) and verify timing closure.
