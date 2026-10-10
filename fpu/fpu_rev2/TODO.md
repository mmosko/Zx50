# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)  
Architecture Specifications: [SystemDesignV2.md](SystemDesignV2.md) & [SystemReference.md](SystemReference.md)  
Programmer's Guide: [ProgrammersGuide.md](ProgrammersGuide.md)

---

## Current Status & Capacity

- **Test Suite Status:** 100% pass rate (**923 / 923 tests passing**).
- **Microcode Capacity:** **736 / 1,024 words used** (288 instruction words of headroom remaining).
- **Hardware Call Stack:** 16-deep $\times$ 10-bit return-address stack in distributed LUT RAM (`RAM16X1S`) with 4-bit `CSP` pointer fully implemented and verified.
- **Completed 32-Bit Math Operations:**
  - Standard arithmetic: `ADD_I32`, `SUB_I32`, `MUL_I32`, `DIV_I32`, `ADD_F32`, `SUB_F32`, `MUL_F32`, `DIV_F32`.
  - Math utilities: `ABS_I32`, `ABS_F32`, `CHS_I32`, `CHS_F32`, `DUP4`.
  - Transcendentals: `SQRT_F32`, `EXP2_F32`, `LOG2_F32`, `POW_F32`.
  - CORDIC Trigonometrics: `SIN_F32`, `COS_F32`, `TAN_F32` (with Cody-Waite range reduction and asymptote detection).
  - Memory Storage: `CP_MEMx_TOS` (slots 0..15), `CP_TOS_MEMx` (slots 0..15), `ZERO_MEM` (using indirect addressing and latched opcode nibble dispatch).
- **Completed 64-Bit Math Operations:**
  - Basic integer/float operations: `ADD_I64`, `SUB_I64`, `MUL_I64`, `ABS_I64`, `CHS_I64`, `ABS_F64`, `CHS_F64`, `DUP8`.

---

## Next Steps: Architecture Improvements to Reduce Microcode Size

To reclaim microcode capacity for 64-bit routines (`DIV_I64`, `MUL_F64`, `DIV_F64`, `SQRT_F64`, and 64-bit CORDIC), the following architectural and microcode improvements are prioritized:

### 1. Populate Range Reduction Constants in `CONST` ROM (~8 Words Saved)
- [ ] **Add Cody-Waite Constants to `CONST` ROM**:
  - Add $C_1 = 102943$ and $C_2 = 11601$ into unused slots of `CONST` ROM.
  - Eliminates multi-instruction synthesis loops (`LDI`, `LSL`, `LDI`, `ADD`), saving **8 instructions**.

### 2. Widen `HA_MUX` to Full 4-Bit Symmetry (~20–30 Words Saved)
- [ ] **Expand `HA_MUX` from 3 Bits to 4 Bits**:
  - Currently `HA_MUX` is restricted to `{AL, AH, BL, BH, EA, EB, C, IMM}`. Registers `DL, DH, FL, FH` cannot be used as `src1` (the left operand of `ADD`, `SUB`, `CMP`, `AND`, `OR`, `XOR`).
  - Expanding `HA_MUX` to 16 inputs makes `HA_BUS` fully symmetric with `HB_BUS` and eliminates redundant register shuffling (`MOV AL, FL; ADD AL, BL; MOV FL, AL`).
  - Estimated FPGA cost: ~32 LUT4s.

---

## Remaining Functional Roadmap

### 1. 64-Bit Arithmetic & Transcendental Routines
- [x] Implement `DIV_I64` (64-bit integer division with overflow and zero check).
- [ ] Implement `MUL_F64` (64-bit IEEE-754 double-precision multiplication using cascaded Booth multiplier).
- [ ] Implement `DIV_F64` (64-bit IEEE-754 double-precision division).
- [ ] Implement `SQRT_F64` (64-bit IEEE-754 double-precision square root).
- [ ] Implement 64-bit CORDIC trigonometrics (`SIN_F64`, `COS_F64`, `TAN_F64`).

### 2. Conversions & Floor/Ceiling Opcodes
- [ ] Implement `FLOOR_F32`, `FLOOR_F64`, `CEIL_F32`, `CEIL_F64`.
- [ ] Implement format conversions:
  - `CONV_I32_F32`, `CONV_F32_I32`
  - `CONV_I64_F64`, `CONV_F64_I64`
  - `CONV_F32_F64`, `CONV_F64_F32`

### 3. Hardware Simulation & Verilog RTL
- [ ] **Host Interface Simulation**:
  - Combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
  - Autonomous SPI Flash bootloader copy simulation.
- [ ] **Verilog Implementation**:
  - Modular Verilog RTL corresponding to V2 functional blocks, MUXes, AND walls, and write-back registers.
  - Self-checking Verilog testbenches with `$fatal` assertions on errors.
  - Synthesis for Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) and timing verification at 80 MHz.
