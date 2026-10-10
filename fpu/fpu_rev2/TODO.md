# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)  
Architecture Specifications: [SystemDesignV2.md](SystemDesignV2.md) & [SystemReference.md](SystemReference.md)  
Programmer's Guide: [ProgrammersGuide.md](ProgrammersGuide.md)

---

## Current Status & Capacity

- **Test Suite Status:** 100% pass rate (**952 / 952 tests passing**).
- **Microcode Capacity:** **785 / 1,024 words used** (239 instruction words of headroom remaining).
- **Hardware Call Stack:** 16-deep $\times$ 10-bit return-address stack in distributed LUT RAM (`RAM16X1S`) with 4-bit `CSP` pointer fully implemented and verified.
- **Completed 32-Bit Math Operations:**
  - Standard integer arithmetic: `ADD_I32`, `SUB_I32`, `MUL_I32`, `DIV_I32` (100% complete).
  - Floating-point arithmetic: `ADD_F32`, `SUB_F32`, `MUL_F32`, `DIV_F32`.
  - Math utilities: `ABS_I32`, `ABS_F32`, `CHS_I32`, `CHS_F32`, `DUP4`.
  - Transcendentals: `SQRT_F32`, `EXP2_F32`, `LOG2_F32`, `POW_F32`.
  - CORDIC Trigonometrics: `SIN_F32`, `COS_F32`, `TAN_F32` (with Cody-Waite range reduction and asymptote detection).
  - Memory Storage: `CP_MEMx_TOS` (slots 0..15), `CP_TOS_MEMx` (slots 0..15), `ZERO_MEM` (using indirect addressing and latched opcode nibble dispatch).
  - Math Constants: `PUSH_PI_32`, `PUSH_E_32`, `PUSH_LN2_32`, `PUSH_LOG2E_32`, `PUSH_LOG2_10_32`, `PUSH_LOG10_2_32`, `PUSH_SQRT2_32`, `PUSH_INV_SQRT2_32`.
- **Completed 64-Bit Math Operations:**
  - Standard integer arithmetic: `ADD_I64`, `SUB_I64`, `MUL_I64`, `DIV_I64` (100% complete).
  - Utilities: `ABS_I64`, `CHS_I64`, `ABS_F64`, `CHS_F64`, `DUP8`.
  - Math Constants: `PUSH_PI_64`, `PUSH_E_64`, `PUSH_LN2_64`, `PUSH_LOG2E_64`, `PUSH_LOG2_10_64`, `PUSH_LOG10_2_64`, `PUSH_SQRT2_64`, `PUSH_INV_SQRT2_64`.

---

## Next Steps: Architecture Improvements to Reduce Microcode Size

To reclaim microcode capacity for remaining 64-bit routines (`MUL_F64`, `DIV_F64`, `SQRT_F64`, and 64-bit CORDIC), the following architectural and microcode improvements are prioritized:

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

### 1. Pure Integer Conversions (Final Remaining Pure-Integer Operations)
- [ ] Implement `CONV_I32_I64` (`0xC8`): Sign-extend signed 32-bit int to 64-bit int (net $+4$ bytes on stack).
- [ ] Implement `CONV_I64_I32` (`0xCA`): Narrow signed 64-bit int to 32-bit int with truncation overflow check ($V=1$) (net $-4$ bytes on stack).
- [ ] Implement `CONV_U32_U64` (`0xC2`): Zero-extend unsigned 32-bit uint to 64-bit uint (net $+4$ bytes on stack).
- [ ] Implement `CONV_U64_U32` (`0xC3`): Narrow unsigned 64-bit uint to 32-bit uint with truncation overflow check ($V=1$) (net $-4$ bytes on stack).

### 2. Hybrid Integer $\leftrightarrow$ Floating-Point Conversions
- [ ] Implement `CONV_I32_F32` (`0xCC`): Signed 32-bit int to IEEE-754 single float (net $0$ bytes on stack).
- [ ] Implement `CONV_F32_I32` (`0xCD`): IEEE-754 single float to signed 32-bit int (truncate toward zero, $V=1$ on range overflow).
- [ ] Implement `CONV_I64_F64` (`0xCE`): Signed 64-bit int to IEEE-754 double float (net $0$ bytes on stack).
- [ ] Implement `CONV_F64_I64` (`0xCF`): IEEE-754 double float to signed 64-bit int (truncate toward zero, $V=1$ on range overflow).

### 3. Floating-Point Conversions & Utilities
- [ ] Implement `CONV_F32_F64` (`0xC9`): Expand IEEE single float to double float (net $+4$ bytes on stack).
- [ ] Implement `CONV_F64_F32` (`0xCB`): Narrow IEEE double float to single float (net $-4$ bytes on stack, $V=1$ on exponent overflow, $U=1$ on underflow).
- [ ] Implement `FLOOR_F32`, `FLOOR_F64`: Mathematical floor toward $-\infty$.
- [ ] Implement `CEIL_F32`, `CEIL_F64`: Mathematical ceiling toward $+\infty$.

### 4. 64-Bit Floating-Point Arithmetic & Transcendentals
- [ ] Implement `ADD_F64` (`0x03`): 64-bit IEEE-754 double-precision addition.
- [ ] Implement `SUB_F64` (`0x0B`): 64-bit IEEE-754 double-precision subtraction.
- [ ] Implement `MUL_F64` (`0x13`): 64-bit IEEE-754 double-precision multiplication using cascaded Booth multiplier.
- [ ] Implement `DIV_F64` (`0x1B`): 64-bit IEEE-754 double-precision division.
- [ ] Implement `SQRT_F64` (`0x23`): 64-bit IEEE-754 double-precision square root.
- [ ] Implement `POW_F64` (`0x2B`): 64-bit IEEE-754 double-precision power ($x^y$).
- [ ] Implement `LOG2_F64` (`0x33`): 64-bit base-2 logarithm.
- [ ] Implement `EXP2_F64` (`0x3B`): 64-bit base-2 exponential ($2^x$).
- [ ] Implement 64-bit CORDIC trigonometrics: `SIN_F64` (`0x73`), `COS_F64` (`0x7B`), `TAN_F64` (`0x83`).

### 5. Hardware Simulation & Verilog RTL
- [ ] **Host Interface Simulation**:
  - Combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
  - Autonomous SPI Flash bootloader copy simulation.
- [ ] **Verilog Implementation**:
  - Modular Verilog RTL corresponding to V2 functional blocks, MUXes, AND walls, and write-back registers.
  - Self-checking Verilog testbenches with `$fatal` assertions on errors.
  - Synthesis for Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) and timing verification at 80 MHz.
