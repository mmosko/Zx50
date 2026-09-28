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

- [ ] **Phase 4: Python Machine Model (Specification in `FPU_EMULATOR.md`)**
  - [x] Create architectural specification and emulation guidelines in `FPU_EMULATOR.md`.
  - [ ] Implement bit-accurate hardware building blocks (registers, 32-bit ALU, shifter, micro-sequencer) in Python.
  - [ ] **Constraint:** Implement execution strictly using byte arrays, microcode steps, and basic hardware ALU primitives—NO Python native math/float libraries for computation.
  - [ ] Validate complete microcode routines against IEEE-754 test vectors and integer arithmetic edge cases.

- [ ] **Phase 5: Verilog Implementation & Unit/Integration Testing**
  - [ ] Build modular Verilog components (top-level bus interface, CDC dispatcher, micro-engine, ALU blocks, SysMEM EBR wrappers, QSPI shadow loader).
  - [ ] Write unit testbenches for all submodules with `$fatal` assertions on failure.
  - [ ] Implement top-level system simulation testbenches (`sim/`) against Z80 bus functional models.
  - [ ] Synthesize and verify timing closure in Lattice Diamond for target speed grade.
