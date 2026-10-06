# ZX50 Project Status & Architecture Checkpoint

*Last Updated: October 5, 2026*

---

## 1. Executive Summary

The Zx50 project is a custom, multi-node Z80 distributed computing cluster featuring custom KiCad hardware cards, CPLD/FPGA memory controllers, a microcoded floating-point coprocessor, and a self-hosting modular operating system.

Since the March 2026 checkpoint, major milestones have been achieved across hardware, firmware, and emulation:
- **Physical Silicon Bring-Up**: The physical backplane (`RevD`), CPU (`RevB1`), clock mezzanine (`RevC`), memory card (`RevA1`), serial card (`RevB`), front panel (`RevB`), and bus probe (`RevB`) are operational in the chassis.
- **Operating System Kernel**: The Z80 monitor has evolved into a self-hosting OS with interrupt-driven ring buffers, an XMODEM binary loader, Process Control Block (PCB) memory auditing, and a formal Page 0 syscall SDK.
- **Microcoded FPU Architecture (`fpu_rev2`)**: Designed and fully verified a custom 32/64-bit IEEE-754 floating-point coprocessor emulator in Python with **486 unit/integration tests** and **98% code coverage**, complete with 3-operand instruction execution and an assembler specification (`SystemAssembler.md`).

---

## 2. Live System Configuration & Physical Slot Map

The active hardware test chassis is populated as follows:

| Slot | Card / Module | Status / Notes |
|:---:|:---|:---|
| **Backplane** | `Zx50_Backplane_RevD` | Operational; updated resistive termination. |
| **Display** | `Zx50_FrontPanelDisplay` | Blue LCD + rotary/switches driven by Front Panel Card. |
| **Slot 1** | `Zx50_Cpu_RevB1` + `Zx50_Clock_Mezzanine_RevC` | Z80 CPU running at 5.0 MHz / 10.0 MHz (divided from 20MHz/40MHz oscillator). |
| **Slot 2** | `Zx50_Serial_RevB` | Dual Z80 SIO channels: Port A (Console 0x84/0x86) and Port B (Debug 0x85/0x87). |
| **Slot 3** | `Zx50_MemoryCard_RevA1` | 512KB SST39SF040 Flash + SRAM; ATF1508 CPLD with boot bypass & write protection. |
| **Slot 4** | *(Reserved)* | Reserved for secondary memory card / NUMA node. |
| **Slot 5** | *(Reserved)* | Target slot for FPGA FPU Coprocessor card. |
| **Slot 6** | `Zx50_FrontPanelCard_RevB` | RP2040-driven front panel bus interface (Port 0x50). |
| **Slot 7** | `Zx50_BusProbe_RevB` | RP2040 Pico + PIC18F4620 dual-core real-time bus snooper and injector. |
| **Slot 8** | *(Empty / Probing)* | Oscilloscope probes attached to `ZCLK`, `MCLK`, and bus analyzer. |

---

## 3. Subsystem Achievements & Current Status

### 3.1 Zx50 Operating System & Monitor Kernel (`zx50_monitor`)
- **Self-Hosting OS Kernel**: Transitions seamlessly from SST39SF040 boot ROM to SRAM via a 16KB copy window and a hardware "Phantom Jump" that trips the MMU ROM kill-switch.
- **Interrupt-Driven Asynchronous I/O**:
  - IM 2 vector table with SIO Channel A/B and CTC channels.
  - Single-Producer / Single-Consumer (SPSC) lock-free ring buffers (`ring_buffer.z80`) for low-overhead serial RX and TX.
  - Dynamically enabled SIO TX interrupts (`SIO_WR1_TX_INT_EN`) and formal TX buffer reset (`SIO_CMD_RST_TX_INT`).
- **File Transfer & Application Loading**:
  - Native XMODEM receiver (`apps/xmodem.z80`) with hardware polling and timeout protection.
  - Kernel memory protection preventing loads below `0x2000`.
- **Process Control Block (PCB) & Auditing**:
  - Process table in Page 0 tracking binary names, execution entry points, page mappings, and 16-bit cumulative checksums.
  - CLI `verify <name>` command (`pcb_verify.z80`) validates in-memory integrity against bit rot before execution.
- **Developer SDK**:
  - Formal jump table (`syscall.z80`) providing OS services (`Sys_PrintString`, `Sys_ReadChar`, `Sys_PrintChar`, `Sys_Yield`, etc.).
  - Standalone app development documentation (`DEVGUIDE.md`) with example binaries (`hello.z80`).

### 3.2 FPU Math Coprocessor Subsystem (`fpu/fpu_rev2`)
- **Architecture**: Custom microcoded 32-bit / 64-bit coprocessor modeled for Lattice MachXO3 / MachXO2 FPGA implementation.
- **Python Hardware Emulator (`fpu_emu`)**:
  - **486 passed tests** with **98% overall line coverage**.
  - Cycle-accurate models for all hardware blocks:
    - **ALU Block (`adder_block.py`)**: 32-bit adder/subtractor, signed/unsigned comparisons, Booth 32x32 multiplier (`booth_mul.py`), non-restoring divider (`div_core.py`), and exponent add/subtract (`EXP_ADD`, `EXP_SUB`).
    - **Shifter Block (`shifter_block.py`)**: 64-bit barrel shifter (`LSL`, `LSR`, `ASR`), leading zero counter / priority encoder (`LZC`), float `PACK` and `UNPACK`.
    - **Logic Block (`logic_block.py`)**: 32-bit AND, OR, XOR, NOT, ABS, and CHS.
    - **Memory/Stack Block (`memory_block.py`)**: 32-bit hardware stack (`PUSH`, `POP`, `SWAP`), scratch SRAM transfer (`_LD`, `_STO`, `CP_MEM`).
    - **Control Block (`control_block.py`)**: Sequencer, `UPC`, flag branching (`JZ`, `JNZ`, `DJNZ`), and 1-level hardware `CALL` / `RET` subroutine mechanism.
- **Instruction Set Enhancements**:
  - Widened `ha_mux` to 8 inputs (including `BL` and `BH`).
  - Widened `reg_file.instr` to 21 bits (`inst_21[20:0]`), supporting canonical 3-address operations (e.g. `EXP_SUB C, EA, EB` executing $C \leftarrow EA - EB$ in 1 cycle without register destruction).
  - Floating-point microcode routines for IEEE-754 single-precision operations (`ADD_F32`, `SUB_F32`, `MUL_F32`, `DIV_F32`).
- **Assembler Specification (`SystemAssembler.md`)**:
  - Detailed design for the microcode assembler (`fasm`).
  - Always-ternary machine word synthesis (`assign ha_mux_sel = instr_reg[13:11]` in pure FPGA wires).
  - Automatic branch delay-slot `NOP` insertion and instruction scheduling.
  - Decoupled `User.<Name>` labels with an external `user_opcodes.def` mapping to initialize the EBR 7 dispatch lookup table.
  - Outputs: `.hex` (Verilog `$readmemh`), `.bin`, `.sym` (symbol & opcode dispatch tables), and `.map`.

### 3.3 Memory Subsystem Generations
- **RevA1 (Current Physical Hardware)**:
  - ATF1508AS CPLD fitted at 96% macrocell utilization (124/128).
  - Bodge fix applied to LED pull-up drops, dropping standby current from 500mA to a healthy 114mA.
  - Linear 32KB boot ROM bypass and hardware EEPROM write protection verified.
- **RevB (Lattice MachXO2 Design)**:
  - Transition to 3.3V FPGA in TQFP-100/144 package using 74LVC245 level translators.
  - Eliminates external ISSI SRAM by placing the MMU page table directly into FPGA Block RAM (BRAM).
  - Supported by open-source Yosys + NextPNR (Project Trellis) toolchain.
- **RevC (Lattice MachXO3 NUMA/PGAS Architecture)**:
  - Fast-path data plane: Zero-contention cycle-stealing DMA over 12ns SRAM, ~WAIT generation, custom 8b/10b physical packet framing over LVDS.
  - Control plane: Embedded RISC-V softcore SmartNIC managing dynamic PGAS routing, mailbox interrupts, and lock arbitration.

### 3.4 Bus Probe & Diagnostics (`Zx50_BusProbe_RevB`)
- **Hardware**: RP2040 Pico paired with PIC18F4620 interface chip snooping backplane buses via high-speed multiplexers.
- **Firmware**:
  - Modular Pico firmware (`bus.py`, `pic18_link.py`, `pins.py`) with non-blocking interactive command REPL.
  - 1 Mbps binary RPC UART link to the PIC18F4620 supporting single-step, bus sniffing, and memory snapshot commands.
  - Direct memory access (`machine.mem32[0xd0000004]`) for single-cycle 8-bit bus acquisition.
- **Host Software & RF Analysis**:
  - SCPI control driver (`scope_control.py`) over LAN for Tektronix MDO3034 oscilloscope.
  - Automated sweep orchestrator (`test_runner.py`) logging voltage and phase sweeps across TX/RX lines.
  - Jupyter workflow (`backplane_analysis.ipynb`) analyzing signal integrity and crosstalk against TTL thresholds.

---

## 4. Hardware Rework & Board Tasks

### 4.1 Zx50_Serial_RevB
- [ ] **DCDA (Pin 19):** Pull down to GND (or add 10k resistor) on `IC2` to allow enabling `Auto Enables` without receiver stalling.
- [ ] **CTSA (Pin 18):** Add 10k pull-down so transmissions flow when using standard 3-wire serial cables (TX/RX/GND).
- [ ] **Firmware Flow Control:** Re-enable `SIO_WR3_AUTO_EN` in `kernel/io/serial.z80` once physical pull-downs are confirmed.

### 4.2 Zx50_BusProbe_RevB
- [ ] **Display Integration:** Complete `display.py` integration to drive the onboard OLED/LCD diagnostics readout.
- [ ] **Live Backplane Sweep:** Execute `test_runner.py` across all slots on `Zx50_Backplane_RevD` to measure RF crosstalk under high-speed switching.

---

## 5. Next Steps & Active Development

### Phase 1: FPU Microcode Assembler (`fasm`)
1. Implement the multi-pass microcode assembler in Python using a maintainable grammar parser (`lark` / `ply`) per [SystemAssembler.md](file:///Users/marc/Documents/z80/Zx50/fpu/fpu_rev2/SystemAssembler.md).
2. Support decoupled `user_opcodes.def` mapping to automatically generate the EBR 7 dispatch lookup table.
3. Implement delay slot management (automatic `NOP` insertion after `JMP`, `JZ`, `JNZ`, `DJNZ`, `CALL`, `RET`).
4. Emit `.hex`, `.bin`, `.sym`, and `.map` files, and test with the existing test suite and `fpu_emu`.

### Phase 2: FPU Status Save/Restore (`SSAV` / `SRES`) & Microcode Optimization
1. Implement 1-depth status register save (`SSAV`) and restore (`SRES`) opcodes in `ControlBlock` and `Registers`.
2. Optimize the `ADD_F32` microcode sequence in `micro_code.py` using 3-address `EXP_SUB C, EA, EB` (saving 4 cycles and eliminating `FL` register stashing).
3. Port complete transcendental and floating-point subroutines (`MUL_F32`, `DIV_F32`) to `.fasm` source files.

### Phase 3: Zx50 OS Kernel Virtual Memory & Multitasking
1. **Paging Manager**: Add `Page` allocation tracking in `PCB_Entry` to dynamically assign physical 4KB memory pages to transient applications.
2. **Standard Application Window (`0x4000`)**: Compile all user applications to `ORG 0x4000`; map application pages into `0x4000` on launch and unmap on exit.
3. **Preemptive Multitasking**: Connect CTC Channel 3 timer interrupts (100 Hz) to a context-switching scheduler to run concurrent isolated tasks.
