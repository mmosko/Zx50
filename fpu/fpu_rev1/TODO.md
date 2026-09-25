# CPLD Firmware TODO

## Priority 1: Hardware Pinout, Memory & Power Architecture

* [x] **Update Top-Level Netlist Pinout & Control Bus Architecture**
* [x] Expand private address bus from 14-bit (`CA[13:0]`) to 15-bit (`CA[14:0]`) to utilize the full 32 KB active window
  (`CA14` mapped to CPLD Pin 60).
* [x] Replace separate memory strobes (`f_oe_n`, `f_we_n`, `m_oe_n`, `m_we_n`) with consolidated shared strobes:
* `c_oe_n` (Pin 45) — Shared Output Enable
* `c_we_n` (Pin 46) — Shared Write Enable


* [x] Maintain dedicated active-LOW Chip Enables:
* `m_ce_n` (Pin 44) — Private SRAM Chip Enable
* `f_ce_n` (Pin 68) — Private Flash Chip Enable


* [x] **Update Wrapper & Arbiter Modules**
* [x] Update `src/zx50_fpu_mem.v` to decode `CA[14:0]` and drive consolidated `c_oe_n` / `c_we_n` strobes.
* [x] Embed detailed Architectural Integration Contract & Timing Guard documentation in `src/zx50_fpu_mem.v`.
* [x] Update `src/zx50_fpu_block.v` cluster wrapper to reflect new top-level I/O ports.
* [x] Update `src/zx50_fpu.v` top-level instantiation.


* [ ] **Electrical & Decoupling Verification**
* [ ] Verify decoupling capacitor sizing ($0.1\mu\text{F}$ ceramics / bulk caps) for the private memory bus, accounting
  for higher dynamic peak current draw when `m_ce_n` is asserted on the fast $12\text{ ns}$ IS61C256AL SRAM vs slower
  memory chips.

---

## Priority 2: RTL Timing, State Machine & CDC Revisions

* [x] **Dynamic Memory Controller & Timing FSM (`src/zx50_fpu_mem.v`)**
* [x] Implement 1-cycle synchronous SRAM reads and 2-phase write strobe generator (`sram_we_strobe` -> `sram_we_hold`).
* [x] Implement address latching (`latched_addr`) during write cycles to eliminate delta-cycle address glitches across
  the `c_we_n` rising edge.
* [x] Implement dynamic wait-state counter (`flash_cnt`) driven by `clk_spd`:
* 3 cycles at 40 MHz MCLK ($75\text{ ns} > 55\text{ ns } t_{\text{ACC}}$)
* 2 cycles at 20 MHz MCLK ($100\text{ ns} > 55\text{ ns } t_{\text{ACC}}$)


* [x] Implement explicit 1-cycle `mem_ready` completion pulse for master handshake.


* [x] **Handshaked Serial ALU FSM (`src/zx50_fpu_alu.v`)**
* [x] Wire `mem_ready` handshake into fetch (`ST_READ_A`, `ST_READ_B`) and store (`ST_WRITE`) states.
* [x] Validate multi-byte integer addition (`OP_ADD`), subtraction (`OP_SUB`), and two's complement negation (`OP_CHS`).
* [x] Implement status flag registers (`ZERO`, `SIGN`, `CARRY`) across multi-byte serial iterations.

---

## Priority 3: Simulator & Algorithm Expansion (Python Models)

* [ ] **Python Datapath Simulator Enhancements (`tools/fpu_sim.py`)**
* [ ] Model `i16` (16-bit signed integer) and `i64` (64-bit signed integer) byte-serial execution loops.
* [ ] Model custom `F16` (16-bit floating-point) and `F32` (32-bit floating-point) formats using microcode serial
  shifting (`ALU_SHL` / `ALU_SHR`).
* [ ] Model `CFLOAT` (32-bit complex float $a + bi$) via chained microcode execution steps.
* [ ] Model `SIN`, `COS`, and `TAN` functions along with their respective Flash ROM lookup table generators
  (`tools/build_flash.py`).


* [ ] **High-Fidelity Verilog Simulation Models (`sim/`)**
* [x] Build 12ns SRAM simulation model (`src/is61c256al_12.v`)
  with $t_{\text{AA}} = 12\text{ ns}$, $t_{\text{PWE}} = 9\text{ ns}$, and tri-state driver release checks.
* [x] Refine Flash ROM simulation model (`src/sst39sf040.v`)
  enforcing $t_{\text{AA}} = 55\text{ ns}$, $t_{\text{OE}} = 35\text{ ns}$.
* [ ] Update testbench suite:
* [x] `sim/fpu_mem_tb.v`: Verify 20 MHz vs 40 MHz Flash reads, SRAM access, and dual-client priority.
* [x] `sim/fpu_alu_tb.v`: Verify multi-byte carry/borrow, status flags, and `mem_ready` handshaking.
* [ ] `sim/init_tb.v`: Verify chip select isolation (`m_ce_n`, `f_ce_n`) and shared strobe default states.
* [ ] `sim/fpu_stack_tb.v`: Verify 32-bit frame PUSH/POP operations against `CA[14:0]` and SRAM access.
* [ ] `sim/fpu_cmd_tb.v`: Re-validate 4-phase Level CDC handshaking (`exec_req` / `done_ack`) across `ZCLK` and `MCLK`
  domains.

---

## Priority 4: RTL Implementation & CPLD Fitting Iterations

* [ ] **Core Format Verilog Implementation**
* [ ] Generate Quarter-Square lookup table (`qs_table.hex`) for $f (n) = \lfloor n^2 / 4 \rfloor$ ($n \in [0, 510]$).
* [ ] Implement `i16`, `i32`, `i64`, `16.16` (fixed-point), and `F32` (custom float) in Verilog microcode.
* [ ] Build multiplication unit testbench (`sim/fpu_mul_tb.v`).


* [ ] **Synthesis & Fitting Verification Pass 1**
* [ ] Synthesize `i16`, `i32`, `i64`, `16.16`, and `F32` implementations in Yosys / ProChip.
* [ ] Verify macrocell count and fitting allocation on the ATF1508AS target (target $< 80\%$ macrocell ceiling).


* [ ] **Extended Format Implementation Pass 2**
* [ ] If macrocell budget permits after Pass 1, implement `F16` and `CFLOAT` in Verilog RTL and re-check fitting.

---

## Priority 5: Z80 Software Stack & Host Libraries

* [ ] **Z80 Assembly Header (`zx50_fpu.inc`)**
* [ ] Write standard Z80 assembly header defining port constants (`SPORT = 0x70`, `CPORT = 0x71`), format fields
  (`FMT_*`), operation mnemonics (`OP_*`), and management opcodes (`MGMT_*`).


* [ ] **String Conversion & I/O Library (`libfpu_str.asm`)**
* [ ] Develop Z80 assembly routines for String-to-Number conversion (ASCII string $\rightarrow$ `i32`, `fx1616`, `F32`).
* [ ] Develop Z80 assembly routines for Number-to-String formatting (Number $\rightarrow$ formatted ASCII string for
  user I/O).

---

## Priority 6: User & System Documentation Updates

* [ ] **`PROGRAMMERS_GUIDE.md` Updates**
* [ ] Document new formats (`i16`, `i64`, `CFLOAT`, `F16`, `F32`).
* [ ] Explicitly note that IEEE-754 64-bit Double Precision (`F64`) is unsupported in hardware due to CPLD macrocell
  constraints.
* [ ] Add usage documentation for the `zx50_fpu.inc` assembly header and ASCII string conversion library.


* [ ] **`SYSTEM_DESIGN_GUIDE.md` Updates**
* [ ] Add a dedicated section analyzing host Z80 cycle counts ($T$-states) and expected polling/wait durations per FPU
  operation (accounting for CDC handshaking and MCLK/ZCLK ratios).