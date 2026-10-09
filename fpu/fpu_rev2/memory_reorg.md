# Zx50 FPU Rev 2: SysMEM EBR Reorganization & Memory Architecture Specification

This document details the architectural redesign of the Lattice MachXO2 SysMEM Embedded Block RAM (EBR) subsystem for the Zx50 FPU Coprocessor.

---

## 1. Executive Summary & Symmetrical Memory Architecture

The 8 physical SysMEM EBR blocks (9 Kbits each) in the Lattice MachXO2 are partitioned into **two identical, symmetrical $1024 \times 32$-bit blocks**:

1. **`DATA_RAM` (EBR 0, 1, 2, 3):** Cascaded $1024 \text{ words} \times 32 \text{ bits}$ RAM (4,096 Bytes).
   - Segregated into a **1 KB RAM region** (`0x000`–`0x0FF`) and a **3 KB ROM region** (`0x100`–`0x3FF`).
   - Serviced exclusively by the micro-engine datapath for Stack, Scratchpad, User Storage, and all Mathematical Lookup Tables (`LDC`).
   - Single 10-bit address bus `MEM_ADDR[9:0]` (`0x000`–`0x3FF`).
   - Single 2-input NOR gate hardware write-protection for all ROM space: `data_ram_we = is_write & (mem_addr[9:8] == 2'b00)`.
2. **`CODE_ROM` (EBR 4, 5, 6, 7):** Cascaded $1024 \text{ words} \times 32 \text{ bits}$ ROM/RAM (4,096 Bytes).
   - Serviced exclusively by the micro-sequencer / dispatcher for micro-instruction prefetch.
   - Single 10-bit address bus `UPC[9:0]` (`0x000`–`0x3FF`).
   - Single 32-bit instruction word `INSTR[31:0]`.
3. **PFU Distributed LUT-RAM (0 EBR blocks consumed):**
   - Operation Stack (`OSP[4:0]`, 32 bytes circular buffer).

```
========================================================================================
                      TOTAL MACHXO2 EBR ALLOCATION (8 of 8 Blocks = 100%)
========================================================================================
+------------------+-----------------------+---------------------------------+---------+
| Physical EBR     | Diamond Configuration | Functional Allocation           | Size    |
+------------------+-----------------------+---------------------------------+---------+
| EBR 0, 1, 2, 3   | Cascaded Unified RAM  | DATA_RAM: Segregated RAM/ROM    | 4,096 B |
| (4 Blocks)       | (1024 x 32-bit)       | (1 KB RAM + 3 KB ROM Tables)    | (1024W) |
+------------------+-----------------------+---------------------------------+---------+
| EBR 4, 5, 6, 7   | Cascaded Unified ROM  | CODE_ROM: Microcode Execution   | 4,096 B |
| (4 Blocks)       | (1024 x 32-bit)       | Store (Unified UPC[9:0])        | (1024W) |
+------------------+-----------------------+---------------------------------+---------+
| Distributed RAM  | PFU Distributed RAM   | Operation Stack (OSP[4:0])      | 32 B    |
| (0 EBR Blocks)   | (32 x 8-bit)          | (Zero EBR consumed)             |         |
+------------------+-----------------------+---------------------------------+---------+
Total EBR Utilization: 8 of 8 blocks (100% utilized, perfectly balanced 4 + 4)
========================================================================================
```

---

## 2. Segregated Data RAM / ROM Subsystem (`DATA_RAM`, EBR 0–3)

### 2.1 Memory Map (10-bit Address Space: `0x000`–`0x3FF`)

The address space is cleanly segregated at word boundary `0x100` (256 words):
* **Lower 256 words (`0x000`–`0x0FF` / 1,024 Bytes):** **RAM Space** (`mem_addr[9:8] == 2'b00`)
* **Upper 768 words (`0x100`–`0x3FF` / 3,072 Bytes):** **ROM Space** (`mem_addr[9:8] != 2'b00`)

| Word Range (Hex) | Word Range (Dec) | Size (Words / Bytes) | Region Type | Content / Allocation | Addressing Mechanism |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `0x000`–`0x07F` | 0..127 | 128 words / 512 B | **RAM** | **Math RAM Stack** | `0x000 \| SP[6:0]` |
| `0x080`–`0x0BF` | 128..191 | 64 words / 256 B | **RAM** | **Scratchpad RAM `SCR[0..63]`** | `0x080 \| imm[5:0]` |
| `0x0C0`–`0x0CF` | 192..207 | 16 words / 64 B | **RAM** | **User Word Storage `USR[0..15]`** | `0x0C0 \| imm[3:0]` |
| `0x0D0`–`0x0FF` | 208..255 | 48 words / 192 B | **RAM** | **Extra RAM Headroom** (Working storage) | Dynamic allocation |
| `0x100`–`0x13F` | 256..319 | 64 words / 256 B | **ROM** | **IEEE-754 Constants** ($\pi, e, \ln 2$, etc.) | `0x100 \| slot[5:0]` |
| `0x140`–`0x1FF` | 320..511 | 192 words / 768 B | **ROM** | **Extra ROM Headroom** (Float64 / FIR / Poly) | Reserved |
| `0x200`–`0x27F` | 512..639 | 128 words / 512 B | **ROM** | **Trigonometric & CORDIC Angles** | `0x200 \| slot[6:0]` |
| `0x280`–`0x2FF` | 640..767 | 128 words / 512 B | **ROM** | **Chebyshev Coefficients** | `0x280 \| slot[6:0]` |
| `0x300`–`0x3FF` | 768..1023 | 256 words / 1,024 B | **ROM** | **Interleaved RECIP / SQRT Seed LUTs**<br>• High 16b `[31:16]`: SQRT Seeds<br>• Low 16b `[15:0]`: RECIP Seeds | `0x300 \| slot[7:0]` |

### 2.2 Clean Hardware Write Protection
Because the RAM/ROM split falls on the clean power-of-two boundary `0x100` (bit 8 or 9 set), write protection is implemented with a single 2-input gate:
```verilog
// Write enable is asserted ONLY when writing within RAM region 0x000..0x0FF (mem_addr[9:8] == 2'b00)
assign data_ram_we = is_write & (mem_addr[9:8] == 2'b00);
```
Any accidental microcode write to addresses $\ge \text{0x100}$ has write-enable suppressed by hardware.

### 2.3 Datapath & `LDC` Table Lookup Logic
All table lookups execute via `LDC dst, TABLE, slot`. Because each table base is aligned to a power-of-two offset (`0x100`, `0x200`, `0x280`, `0x300`), table address calculation is a zero-cost bitwise OR:

```python
if tbl == FpuTable.CONST:
    addr = 0x100 | (offset & 0x3F)
    val = data_ram[addr]                   # 32-bit constant
elif tbl == FpuTable.TRIG:
    addr = 0x200 | (offset & 0x7F)
    val = data_ram[addr]                   # 32-bit angle
elif tbl == FpuTable.CHEB:
    addr = 0x280 | (offset & 0x7F)
    val = data_ram[addr]                   # 32-bit polynomial coefficient
elif tbl == FpuTable.RECIP:
    addr = 0x300 | (offset & 0xFF)
    val = data_ram[addr] & 0xFFFF          # Low 16-bit slice zero-extended
elif tbl == FpuTable.SQRT:
    addr = 0x300 | (offset & 0xFF)
    val = (data_ram[addr] >> 16) & 0xFFFF  # High 16-bit slice zero-extended
```

---

## 3. Unified Microcode Store (`CODE_ROM`, EBR 4–7)

1. **Configuration in Lattice Diamond:**
   - Cascaded 4-block module ($1024 \text{ words} \times 32 \text{ bits}$, 2 deep $\times$ 2 wide).
   - Generates a single unified ROM/RAM macro.
   - The micro-sequencer presents a single 10-bit address `UPC[9:0]` directly to the macro.
   - Returns a single 32-bit instruction word `INSTR[31:0]` in 1 clock cycle with **zero external multiplexers**.
2. **Microcode Budget & Capacity:**
   - Capacity: **1,024 words**.
   - Current microcode utilization: 548 words ($\approx 53.5\%$).
   - Headroom: 476 words available for 32-bit CORDIC trigonometrics and prioritized 64-bit routines.
3. **Hardware Registers:**
   - `Reg.UPC` and `Reg.IMM` in [`registers.py`](file:///Users/marc/Documents/z80/Zx50/fpu/fpu_rev2/fpu_emu/hardware/registers.py) are already 10 bits (`size_in_bits=10`).
   - Branch instructions (`JMP`, `JZ`, `JNZ`, `CALL`) already pass 10-bit target addresses directly into `UPC`.

---

## 4. Flash Image & Serialization Directives (`tools/build_flash.py`)

### 4.1 Single 8 KB Image ($2048 \times 32$-bit Words)
`tools/build_flash.py` generates a single **8 KB binary/hex image** representing exactly **2,048 words $\times$ 32 bits**:

* **Words 0..1023 (0x0000..0x0FFF, First 4 KB): `DATA_RAM` Image**
  * Words 0..255 (`0x000`–`0x0FF`): Zero-filled (RAM space: Stack, Scratchpad, User Storage, RAM Headroom)
  * Words 256..319 (`0x100`–`0x13F`): IEEE-754 Constants (64 words $\times$ 32-bit)
  * Words 320..511 (`0x140`–`0x1FF`): Zero-filled (ROM Headroom: 192 words)
  * Words 512..639 (`0x200`–`0x27F`): Trigonometric & CORDIC Angles (128 words $\times$ 32-bit)
  * Words 640..767 (`0x280`–`0x2FF`): Chebyshev Polynomial Coefficients (128 words $\times$ 32-bit)
  * Words 768..1023 (`0x300`–`0x3FF`): Combined 16-bit Seed Tables (256 words $\times$ 32-bit)
* **Words 1024..2047 (0x1000..0x1FFF, Second 4 KB): `CODE_ROM` Image**
  * Words 1024..2047 (`0x000`–`0x3FF` in UPC space): 1,024 words of microcode instructions padded with NOPs.

### 4.2 Big-Endian Serialization Requirement
Because Lattice Diamond 32-bit EBR modules and simulation hex files expect 32-bit words in **big-endian order**, `tools/build_flash.py` must output words MSB first (`byte3, byte2, byte1, byte0`).

### 4.3 Mixed 16-Bit Stream Combining
For words 768..1023 (`0x300..0x3FF`), `tools/build_flash.py` combines the two 16-bit seed tables into single 32-bit words:
```python
for k in range(256):
    word32 = ((sqrt_seed[k] & 0xFFFF) << 16) | (recip_seed[k] & 0xFFFF)
```
In big-endian byte order:
* `Byte 0: (sqrt_seed[k] >> 8) & 0xFF`  (SQRT MSB)
* `Byte 1: sqrt_seed[k] & 0xFF`         (SQRT LSB)
* `Byte 2: (recip_seed[k] >> 8) & 0xFF` (RECIP MSB)
* `Byte 3: recip_seed[k] & 0xFF`        (RECIP LSB)

### 4.4 Autonomous Boot Loader Execution
The autonomous QSPI hardware state machine performs two sequential block transfers on power-up:
1. **Loop 1 (Words 0..1023):** Reads 1,024 words from Flash offset 0 $\to$ writes `DATA_RAM[0..1023]`.
2. **Loop 2 (Words 1024..2047):** Reads 1,024 words from Flash offset 0x1000 $\to$ writes `CODE_ROM[0..1023]`.

Both transfers use simple incrementing counters without complex banking or address jumping logic.

---

## 5. Implementation Guide & Concrete Checklist for New Thread

### A. Table Map & Encodings: `fpu_emu/rom/fpu_const_map.py`
* Update `FpuTable` table identifier enum for `MicroOp.LDC`:
  ```python
  class FpuTable(IntEnum):
      """Table Identifier for LDC instruction (MicroOp.LDC).
      Mapped to base offsets in unified DATA_RAM (1024x32):
        - CONST: Base 0x100 (words 256..319, 32-bit)
        - TRIG:  Base 0x200 (words 512..639, 32-bit)
        - CHEB:  Base 0x280 (words 640..767, 32-bit)
        - RECIP: Base 0x300 (words 768..1023, low 16-bit slice)
        - SQRT:  Base 0x300 (words 768..1023, high 16-bit slice)
      """
      CONST = 0
      TRIG  = 1
      CHEB  = 2
      RECIP = 3
      SQRT  = 4
  ```

### B. Flash ROM Image Generator: `tools/build_flash.py`
* Update generator to construct the 8 KB ($2048 \times 32$-bit) unified flash image.
* Place IEEE-754 constants at words 256..319 (`0x100..0x13F`).
* Pack words 768..1023 (`0x300..0x3FF`) with `(sqrt << 16) | recip`.
* Serialize in 32-bit big-endian format.
* Update generated outputs: `bin/fpu_flash.bin`, `fpu_emu/rom/fpu_flash.bin`, `sim/fpu_rom.hex`, and `fpu_emu/rom/fpu_const_map.py`.

### C. ROM Buffer Loader: `fpu_emu/rom/ebr_loader.py`
* Update `load_ebr_rom_buffers()`:
  * Reads the 8 KB flash image.
  * Populates `DATA_RAM` (EBR 0–3) initial buffer (1,024 words).
  * Returns `[data_ram, code_rom]` or mapped 8-EBR buffer list where EBR 0–3 share the data buffer.

### D. Memory Block Controller: `fpu_emu/blocks/memory/memory_block.py`
* Define address bases in unified `DATA_RAM`:
  ```python
  MTH_BASE     = 0x000  # Stack: words 0..127 (512 bytes)
  SCR_BASE     = 0x080  # Scratchpad: words 128..191 (256 bytes)
  USR_BASE     = 0x0C0  # User storage: words 192..207 (64 bytes)
  RAM_HEADROOM = 0x0D0  # Free RAM headroom: words 208..255 (192 bytes)
  CNS_BASE     = 0x100  # IEEE-754 Constants: words 256..319 (256 bytes)
  ROM_HEADROOM = 0x140  # Free ROM headroom: words 320..511 (768 bytes)
  TRIG_BASE    = 0x200  # Trig/CORDIC: words 512..639 (512 bytes)
  CHEB_BASE    = 0x280  # Chebyshev: words 640..767 (512 bytes)
  SEEDS_BASE   = 0x300  # Combined Seeds: words 768..1023 (1024 bytes)
  ```
* Update `_ldc_core(dst, tbl_val, offset)` to read from unified `DATA_RAM` and slice data bits `[15:0]` for `RECIP` and `[31:16]` for `SQRT`.
* Update user storage `STO` / `RCL` to access `USR_BASE = 0x0C0`.

### E. Microcode Store & Assembler: `fpu_emu/micro_code.py` & `fpu_asm/`
* In `fpu_emu/micro_code.py`:
  * Update `@fpga_resource` annotation to reflect cascaded EBR 4–7 (4 EBR blocks, $1024 \times 32$).
  * Set `SOFT_MAX_MICRO_INSTRUCTIONS = 1024` and `HARD_MAX_MICRO_INSTRUCTIONS = 1024`.
* In `fpu_asm/emitter.py` and `fpu_asm/__main__.py`:
  * Update default padding from 512 to 1024 words (`total_words: Optional[int] = 1024`).
* In `fpu_asm/tests/test_cli_and_emitter.py`:
  * Update tests asserting 512 words to assert 1024.

### F. Hardware Model: `fpu_emu/hardware/memory.py`
* Update `@fpga_resource`: `ebr=8` (all 8 blocks allocated: 4 for `DATA_RAM`, 4 for `CODE_ROM`).

### G. Specification Document: `FPU_REV2.md`
* Update Section "Internal Memory Subsystem (SysMEM EBR)" with the segregated RAM/ROM layout table and unified addressing description.

---

## 6. Critical Rules & Guardrails for the Incoming Agent
1. **Never edit `fpu_emu/ucode.py` or `fpu_emu/ucode.sym` manually.** They are compiled automatically by running:
   ```bash
   python -m fpu_asm
   ```
2. **Preserve Registers in Microcode:**
   * Registers `A`, `B`, `D` (`AL`, `AH`, `BL`, `BH`, `DL`, `DH`) are preserved across macro-instructions.
   * Scratch registers within an instruction routine are `FL`, `FH`, `FX`.
3. **Run Full Test Suite:**
   * Run `.venv/bin/pytest -q --no-cov` to verify that all 776 tests continue to pass.
