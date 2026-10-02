# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)

---

## Roadmap Phases

- [x] **Phase 1: High-Level Architecture (`FPU_REV2.md`)**
  - [x] Review current contents of `FPU_REV2.md` and identify obsolete CPLD remnants and gaps.
  - [x] Merge and harmonize architecture material from `fpga_arch.md` into `FPU_REV2.md` (features, operating theory, memory hierarchy, dual-port EBR, clocking, flash shadowing, and operating modes).
  - [x] Remove `fpga_arch.md`.
  - [x] Finalize high-level feature set, data types (`i32`, `f32`, `i64`, `f64`), stack model, and host interfaces (Port I/O & optional MMIO).

- [x] **Phase 2: Low-Level System Design (`SystemDesign.md`)**
  - [x] Detail hardware ALU primitive blocks (32-bit adder/subtractor, Radix-4 Booth multiplier, barrel shifter, normalizer/LZC, exponent ALU).
  - [x] Define physical register set (`AX`, `BX`, `DX`, `EA`, `EB`, `C`, `STATUS`, `SP`, `OSP`, `UPC`, `BLOCKING`, `IMMEDIATE`), register pairing, and EBR coupling.
  - [x] Define microcode instruction set architecture ($\mu$-ops) including arithmetic, shifts, logic, data moves, stack pops/pushes, and control flow (`DJNZ`, `JNZ`, `JZ`, `SET`, `CLR`).
  - [x] Specify dispatcher FSM logic, Port 0x70/0x71 arbitration, and wait-state handshake circuit (`BWAIT_N` / `Q4`).
  - [x] Specify microcode programs for all 60 ALU opcodes, 10 stack ops, constants, and management routines.
  - [x] Establish preliminary gate/LUT/EBR resource usage estimates for MachXO2 (`LCMXO2-2000HC`).

- [x] **Phase 3: Z80 Programmer's Guide (`ProgrammersGuide.md`)**
  - [x] Define single source of truth for Status Register (`STATUS[7:0]`) and Z80 polling conventions.
  - [x] Define single source of truth for complete User OpCode Set (Port 0x71 Language).
  - [x] Document assembly programming models (Port 0x70/0x71 protocol, blocking, non-blocking, and batch execution).
  - [x] Define stack conventions, operand layout (Little-Endian), and error handling.
  - [x] Provide complete, runnable Z80 assembly examples for four canonical benchmark problems (Manhattan distance, 3D vector norm, sphere volume, quadratic polynomial evaluation) comparing Immediate Blocking, Non-blocking, and Batch modes.

- [x] **Phase 4: Python Machine Model (Specification in `FPU_EMULATOR.md`)**
  - [x] Create architectural specification and emulation guidelines in `FPU_EMULATOR.md`.
  - [x] Implement bit-accurate hardware building blocks (registers, 32-bit ALU, barrel shifter, booth multiplier, LZC, micro-sequencer) in Python.
  - [x] Single-source flash image builder (`tools/build_flash.py`) generating `fpu_flash.bin` with automated SHA256 drift-prevention unit test.
  - [x] Implement execution strictly using byte arrays, microcode steps, and hardware ALU primitives:
    - Dedicated register file (`AX, BX, DX, FX, EA, EB, C, STATUS, SP, OSP`).
    - Fixed-point & floating-point datapaths (`adder`, `shifter`, `booth_mul`, `lzc`, `logic`, `ieee754_exp`, `fp_sqrt`, `fp_mul_div`, `fp_ln`, `fp_exp`, `fp_pow`).
    - Microcode engine & dual-mode dispatcher (`~BWAIT`, immediate blocking, non-blocking, and batch queues).
  - [x] Validate complete microcode routines against IEEE-754 test vectors, integer arithmetic, and stack edge cases (519 unit tests passing with 99% test coverage).
  - [x] Implement the 4 canonical benchmark programs in `tests/example_test.py` verifying full end-to-end execution.
  - [x] Perform detailed second-pass FPGA resource estimation in `SystemDesign.md` (~787 LUT4s, 494 FFs, 7 EBR blocks, ~62.7% free logic).
  - [x] Implement transcendental ALU modules: natural logarithm (`fp_ln.py`), exponential (`fp_exp.py`), and power (`fp_pow.py`).
  - [ ] Implement combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
  - [ ] Implement autonomous SPI Flash bootloader copy simulation.

- [ ] **Phase 4.5: Trigonometric (CORDIC) Engine & ISA Completeness**
  - [x] **Trigonometric Architecture & Design Specification (`fpu_emu/alu/fp_trig.md`)**:
    - [x] Detail circular CORDIC vector rotation algorithm in $z \to 0$ mode.
    - [x] Specify precision: 24 rotation stages for `f32` (24-bit mantissa), 53 rotation stages for `f64` (53-bit mantissa).
    - [x] Document range reduction strategy: modulo $\pi/2$ with quadrant tracking ($\sin, \cos, \tan$ sign and axis mapping).
    - [x] Define tangent asymptote overflow detection ($\tan(\pm \pi/2) \to \pm \infty$, $V=1$, $ERR=1$).
    - [x] Specify register allocation contract (`AX`: $X$, `BX`: $Y$, `DX`: $Z$ residual angle, `C`: loop counter).
  - [ ] **Lookup Table & Flash Constants (`tools/build_flash.py`, `rom.py`)**:
    - [x] Precompute high-precision CORDIC arctangent angle table ($\theta_i = \text{atan}(2^{-i})$) in Q2.30 / Q2.62 fixed-point format for EBR 2 & 3 constants ROM.
    - [x] Add scaling factor constants ($1/K \approx 0.607252935...$) and range-reduction factors ($2/\pi$, $\pi/2$, $\pi/4$) in both fixed-point and IEEE-754 formats.
    - [x] Update `tools/build_flash.py` serializer, Verilog headers (`src/fpu_rom_map.vh`), and emulator binary image (`fpu_emu/rom/fpu_flash.bin`).
    - [ ] Rewrite `fpu_emu/memory/rom.py` to use the new `fpu_const_map.py`.
    - [ ] Move all constants from FP modules (e.g. `fp_exp.py`, `fp_ln.py`, `fp_pow.py`, `fp_sqrt.py`) into ROM via `tools/build_flash.py` and `fpu_const_map.py`.
  - [ ] **Datapath & Bus MUX Architecture Review (`HA_BUS` & `HB_BUS`)**:
    - [ ] Audit all ALU operations, microcode, and register moves accessing `EA`, `EB`, and `C` to identify required bus connections.
    - [ ] Design hierarchical MUX (or Stage 2 bank expansion) to incorporate `EA[11:0]`, `EB[11:0]`, and `C[5:0]` into `HA_BUS` and/or `HB_BUS`.
    - [ ] Update `SystemDesign.md` (datapath interconnect architecture, Mermaid diagrams, PFU input packing, and slice budget).
    - [ ] Update emulator register model (`fpu_emu/memory/registers.py`) for HA/HB MUX control and collision detection.
    - [ ] Add unit tests verifying MUX selection and timing for `EA`, `EB`, and `C`.
  - [ ] **Multiplier Consolidation (Unified 64-Bit Radix-4 Booth Multiplier)**:
    - [ ] Remove separate 32-bit multiplier; use single 64-bit Booth multiplier for both 32-bit and 64-bit operations.
    - [ ] Define 32-bit execution mode on 64-bit core (16 cycles / early termination or operand positioning/extension).
    - [ ] Update `SystemDesign.md` Section 3.6 and recalculate FPGA resource utilization (eliminating redundant 32-bit multiplier logic).
    - [ ] Refactor `fpu_emu/alu/booth_mul.py` to route all multiplies through the single 64-bit core with unified `@fpga_resource` tracking.
    - [ ] Update unit tests in `fpu_emu/tests/alu/booth_mul_test.py` and `fpu_emu/tests/fpga_budget_test.py`.
  - [ ] **Transcendental Microcode Architectural Review (`POW`, `EXP`, `LN`, `SQRT`)**:
    - [ ] Audit `POW`, `EXP`, `LN`, and `SQRT` modules (`fp_pow.py`, `fp_exp.py`, `fp_ln.py`, `fp_sqrt.py`) to eliminate monolithic hardware blocks.
    - [ ] Re-implement algorithms as pure microcode assembly programs using standard ALU primitives (adder, Booth multiplier, barrel shifter, normalizer/LZC), Constants ROM (`LOAD_CONST`), and scratchpad (`SCR[0..63]`).
    - [ ] Update `SystemDesign.md` FPGA resource estimates to reflect logic savings from moving dedicated transcendental execution blocks into microcode.
  - [ ] **Trigonometric Microcode Implementation (`fpu_emu/micro_code.py`)**:
    - [ ] Implement pure microcode assembly program for `SIN_F32` and `SIN_F64` without monolithic hardware blocks:
      - Cody-Waite range reduction using standard `MUL_F32` / `SUB_F32` and barrel shifter.
      - 24-stage (F32) and 53-stage (F64) CORDIC circular rotation using existing adder, shifter, and EBR ROM table reads via `LOAD_CONST`.
      - Quadrant reconstruction and IEEE-754 float normalization using `LZC`, `LSL`, `EXP_NORM`, and `PACK_F32`.
    - [ ] Implement `COS` and `TAN` microcode routines for F32 and F64.
    - [ ] Unit testing: verify against IEEE-754 reference vectors, special angles ($0, \pi/6, \pi/4, \pi/3, \pi/2, \pi, 3\pi/2, 2\pi$), negative angles, and domain limits.
  - [ ] **ISA & Opcode Completeness Audit**:
    - [ ] Add missing User Opcodes to `fpu_emu/user_opcodes.py`:
      - Trigonometrics:
        - [ ] `SIN_F32` (`0x71`), `SIN_F64` (`0x73`).
        - [ ] `COS_F32` (`0x79`), `COS_F64` (`0x7B`), `TAN_F32` (`0x81`), `TAN_F64` (`0x83`).
      - [x] Sign negation: `CHS_I32` (`0x50`), `CHS_F32` (`0x51`), `CHS_I64` (`0x52`), `CHS_F64` (`0x53`).
      - Floor / Ceil: `FLOOR_F32` (`0x61`), `FLOOR_F64` (`0x63`), `CEIL_F32` (`0x69`), `CEIL_F64` (`0x6B`).
    - [ ] Implement missing microcode sequences in `fpu_emu/micro_code.py` (`_ucode` dictionary):
      - [ ] `SIN_F32` and `SIN_F64` microcode assembly programs using reusable hardware blocks.
      - [ ] `COS`, `TAN` routines for F32 and F64.
      - [x] `CHS` routines for I32, F32, I64, F64.
      - [x] `ABS` routines for F32, F64.
      - `FLOOR` and `CEIL` routines for F32 and F64.
      - Fill existing gaps: integer division (`DIV_I32`, `DIV_I64`) and type conversions (`CONV_*`).
    - [x] Wire functor dispatch table `_FUNCTORS` in `fpu_emu/dispatcher.py` for trig and CORDIC micro-ops.
  - [ ] **Integration & End-to-End Validation**:
    - [x] Extend `fpu_emu/tests/dispatcher_test.py` to cover `SIN_F32` and `SIN_F64` across special angles and error cases.
    - [ ] Extend `fpu_emu/tests/dispatcher_test.py` to cover remaining user opcodes across blocking, non-blocking, and batch modes.
    - [x] Verify 100% test pass rate (668 passing), `ruff check --no-cache`, and `pyright`.

- [ ] **Phase 5: Verilog Implementation & Unit/Integration Testing**
  - [ ] Build modular Verilog components (top-level bus interface, CDC dispatcher, micro-engine, ALU blocks, SysMEM EBR wrappers, QSPI shadow loader, combinatorial SRAM decoder).
  - [ ] Write unit testbenches for all submodules with `$fatal` assertions on failure.
  - [ ] Implement top-level system simulation testbenches (`sim/`) against Z80 bus functional models.
  - [ ] Synthesize and verify timing closure in Lattice Diamond for target speed grade.
