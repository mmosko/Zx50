# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)

---

## Roadmap Phases

- [x] **Phase 1: High-Level Architecture (`FPU_REV2.md`)**
  - [x] Review current contents of `FPU_REV2.md` and identify obsolete CPLD remnants and gaps.
  - [x] Merge and harmonize architecture material from `fpga_arch.md` into `FPU_REV2.md` (features, operating theory, memory hierarchy, dual-port EBR, clocking, flash shadowing, and operating modes).
  - [x] Remove `fpga_arch.md`.
  - [x] Finalize high-level feature set, data types (`i32`, `f32`, `i64`, `f64`), stack model, and host interfaces (Port I/O & optional MMIO).

- [ ] **Phase 2: Low-Level System Design (`SystemDesign.md`)**
  - [x] Detail hardware ALU primitive blocks (32-bit adder/subtractor, Radix-4 Booth multiplier, barrel shifter, normalizer/LZC, exponent ALU).
  - [x] Define physical register set (`AX`, `BX`, `DX`, `EA`, `EB`, `C`, `STATUS`, `SP`, `UPC`), register pairing, and EBR coupling.
  - [x] Establish preliminary gate/LUT/EBR resource usage estimates for MachXO2 (`LCMXO2-2000HC`).
  - [ ] Define micro-sequencer / microcode execution engine (uPC, micro-instruction word format, dispatch table).
  - [ ] Specify detailed execution flow and cycle breakdown for every Port 0x70/0x71 operation and opcode.

- [ ] **Phase 3: Z80 Programmer's Guide (`ProgrammersGuide.md`)**
  - [ ] Document assembly programming models (Port 0x70/0x71 protocol, blocking vs. non-blocking wait modes).
  - [ ] Define stack conventions, operand layout (endianness), and error handling (`STATUS` register).
  - [ ] Provide end-to-end Z80 assembly examples for real math routines (evaluating polynomials, vector operations, transcendental calls).
  - [ ] Verify semantic consistency to eliminate edge cases and subtle math bugs.

- [ ] **Phase 4: Python Machine Model**
  - [ ] Implement bit-accurate hardware building blocks (registers, 32-bit ALU, shifter, micro-sequencer) in Python.
  - [ ] **Constraint:** Implement execution strictly using microcode steps and basic hardware ALU primitives—NO Python native math/float libraries for computation.
  - [ ] Validate complete microcode routines against IEEE-754 test vectors and integer arithmetic edge cases.

- [ ] **Phase 5: Verilog Implementation & Unit/Integration Testing**
  - [ ] Build modular Verilog components (top-level bus interface, CDC dispatcher, micro-engine, ALU blocks, SysMEM EBR wrappers, QSPI shadow loader).
  - [ ] Write unit testbenches for all submodules with `$fatal` assertions on failure.
  - [ ] Implement top-level system simulation testbenches (`sim/`) against Z80 bus functional models.
  - [ ] Synthesize and verify timing closure in Lattice Diamond for target speed grade.
