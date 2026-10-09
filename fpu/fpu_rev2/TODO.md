# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)  
Architecture Specifications: [SystemDesignV2.md](SystemDesignV2.md) & [SystemReference.md](SystemReference.md)  
Programmer's Guide: [ProgrammersGuide.md](ProgrammersGuide.md)

---

## Current Status & Capacity

- **Test Suite Status:** 100% pass rate (**904 / 904 tests passing**).
- **Microcode Capacity:** **861 / 1,024 words used** (163 instruction words of headroom remaining).
- **Hardware Call Stack:** 16-deep $\times$ 10-bit return-address stack in distributed LUT RAM (`RAM16X1S`) with 4-bit `CSP` pointer fully implemented and verified.
- **Completed 32-Bit Math Operations:**
  - Standard arithmetic: `ADD_I32`, `SUB_I32`, `MUL_I32`, `DIV_I32`, `ADD_F32`, `SUB_F32`, `MUL_F32`, `DIV_F32`.
  - Math utilities: `ABS_I32`, `ABS_F32`, `CHS_I32`, `CHS_F32`, `DUP4`.
  - Transcendentals: `SQRT_F32`, `EXP2_F32`, `LOG2_F32`, `POW_F32`.
  - CORDIC Trigonometrics: `SIN_F32`, `COS_F32`, `TAN_F32` (with Cody-Waite range reduction and asymptote detection).
- **Completed 64-Bit Math Operations:**
  - Basic integer/float operations: `ADD_I64`, `SUB_I64`, `MUL_I64`, `ABS_I64`, `CHS_I64`, `ABS_F64`, `CHS_F64`, `DUP8`.

---

## Next Steps: Architecture Improvements to Reduce Microcode Size

To reclaim microcode capacity for 64-bit routines (`DIV_I64`, `MUL_F64`, `DIV_F64`, `SQRT_F64`, and 64-bit CORDIC), the following architectural and microcode improvements are prioritized:

### 1. Expose `ASR` in `MicroOp` & Add Range Constants to `CONST` ROM (Zero FPGA Logic Cost)
- [ ] **Assign `MicroOp.ASR` (`0b110_010`) in Block 6 (Shifter)**:
  - The shifter hardware already implements arithmetic right shifting (`ShiftOp.ASR`), but lacked a microcode opcode.
  - In `trig_f32.asm`, arithmetic shifting of $Y$ in CORDIC is currently emulated using 11 instructions of manual bitwise sign extension and branching.
  - Replacing the emulation with `ASR FH, BL, C` saves **10 instructions** in 32-bit CORDIC and will save an additional **15 instructions** when writing 64-bit CORDIC.
- [ ] **Populate Range Reduction Constants in `CONST` ROM**:
  - Add $C_1 = 102943$ and $C_2 = 11601$ into unused slots of `CONST` ROM.
  - Eliminates multi-instruction synthesis loops (`LDI`, `LSL`, `LDI`, `ADD`), saving **8 instructions**.

### 2. Algorithmic Trigonometric Deduplication (~50 Words Saved)
- [ ] **Unify Cosine and Sine Reconstruction**:
  - In `trig_f32.asm`, `RECONSTRUCT_COS` duplicates ~60 instructions of quadrant checking and sign reconstruction from `RECONSTRUCT_SIN`.
  - Because $\cos(\theta) = \sin(\theta + \pi/2)$, mapping quadrant $q_{cos} = (q + 1) \pmod 4$ before reconstruction allows cosine to share 100% of the sine reconstruction logic.
  - Saves **~50 instructions** with zero hardware changes.

### 3. Indirect Addressing & Dispatcher Nibble Parameter (~95 Words Saved)
- [ ] **Add Indirect Memory Addressing (`LD dst, [reg]`, `STO [reg], src`)**:
  - Add multiplexing in the Memory block so `MEM_ADDR` can be driven by `HB_MUX[5:0]` (masked to RAM space `0x000..0x0FF`) in addition to instruction immediates.
  - Estimated FPGA cost: ~12–16 LUT4s.
- [ ] **Latch Opcode Low Nibble (`opcode & 0x0F`) into Register `C` during Dispatch**:
  - Currently, `cp_mem.asm` maintains 16 separate `CP_MEMx_TOS` handlers (48 instructions), 16 separate `CP_TOS_MEMx` handlers (48 instructions), and an unrolled `ZERO_MEM` routine (16 instructions) because slot numbers are hardcoded immediates.
  - With indirect addressing and dispatcher parameter latching, all 32 routines collapse into two 3-instruction subroutines and a 4-instruction loop:
    ```asm
    CP_MEM_TOS: CALL POP_ONE_32; STO [C], AL; HALT
    CP_TOS_MEM: LD AL, [C]; PUSH AL; HALT
    ZERO_MEM:   LDI C, 16; XOR AL, AL; ZERO_LOOP: STO [C-1], AL; DJNZ ZERO_LOOP; HALT
    ```
  - Saves **~95 instructions** in `cp_mem.asm`, freeing major ROM headroom.

### 4. Widen `HA_MUX` to Full 4-Bit Symmetry (~20–30 Words Saved)
- [ ] **Expand `HA_MUX` from 3 Bits to 4 Bits**:
  - Currently `HA_MUX` is restricted to `{AL, AH, BL, BH, EA, EB, C, IMM}`. Registers `DL, DH, FL, FH` cannot be used as `src1` (the left operand of `ADD`, `SUB`, `CMP`, `AND`, `OR`, `XOR`).
  - Expanding `HA_MUX` to 16 inputs makes `HA_BUS` fully symmetric with `HB_BUS` and eliminates redundant register shuffling (`MOV AL, FL; ADD AL, BL; MOV FL, AL`).
  - Estimated FPGA cost: ~32 LUT4s.

---

## Remaining Functional Roadmap

### 1. 64-Bit Arithmetic & Transcendental Routines
- [ ] Implement `DIV_I64` (64-bit non-restoring integer division).
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
