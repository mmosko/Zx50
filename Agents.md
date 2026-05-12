# Zx50 Project Guidelines for Gemini Code Assist

## Project Overview

The Zx50 is a custom, multi-node Z80 distributed computing cluster (NUMA/PGAS architecture) built from scratch. It
features custom Kicad boards (CPU, Memory, Backplane, Front Panel, Power Supply, Bus Probe).  The current generation
of the memory controller uses an ATF1508 CPLD.  The next generation relies on
Lattice MachXO3 FPGAs for memory management, RDMA networking over LVDS, and hardware acceleration.  

## References

- `docs/hardware` describes the custom hardware
   - Most hardware projects have a netlist exported to aid in AI parsing. 
- `docs/software` describes firmware used in the project.

## Hardware

- Zx50_Backplane_RevC : The current backplane
- Zx50_Backplane_RevD : an update to improve termination.
- Zx50_BusProbe_RevA : A tool for in-circute debugging and profiling of the system.  Has 
  quite a few problems, and we will move away from it soon.
- Zx50_BusProbe_RevB : The next gen bus probe, currently in assembly.
- Zx50_Clock_Mezzanine : The 1st gen clock module for the Zx50_Cpu card.  No longer used.
- Zx50_Clock_Messagnin_RevB : The current gen clock module fo rthe Zx50_Cpu card.
- Zx50_FrontPanelCard : a bus card to drive the Zx50_FrontPanelDisplay.
- Zx50_FrontPanelDisplay : Switches and displays
- Zx50_MemoryCard_RevA : The first memory card, supplanted by Rev A1 with hot fixes
- Zx50_MemoryCard_RevA1 : The current gen memory card, a patched up RevA
- Zx50_MemoryCard_RevB : A Lattice MachXO2 based memory card
- Zx50_MemoryCard_RevC : A Lattice MachX03 based memory card
- Zx50_PowerSupply_RevA : the system power supply (if not using bench supply)
- Zx50_Serial : Serial I/O card, not yet assembled or tested.

## Firmware

- Zx50_BusProbe_Firmware : host, PICO and PIC firmware.  This card uses a PICO with USB and wifi
  connectivity to test and control the bus.  The PIC is the bus interface and can toggle pins or
  read pins.
- Zx50_FrontPanel_Firmware : The Zx50_FrontPanelCard PICO firmware.
- mmu/model_rev1 : ATF1508 verilog for the MMU/Arbiter/DMA CPLD control.
- mmu/mmu_only : ATF1508 verilog for the MMU only (to aid debugging)

## Coding Rules

- Keep the cylomatic complexity low.  Use modular, testable code.
- There must be good coverage unit testing so we have maintainable code.
- For Verilog, 
   - use sub component modules and there must be one or more testbenchs for each module.
   - Test benches should fail with `$fatal` on errors so the Makefile bombs right away.
- Try to avoid magic numbers in the code, define them as named constants at the top
  of the file (or wherever is correct for the language).
- Prefer an API approach.  A module should export a clear public API.  Users
  of a module should never manipulate member variables in other classes/modules.
- Data classes are OK, but they need to be simple records (e.g. Data class), maybe
  with data conversion behavior (e.g. `into` or `try_from`).

## Notes on the next generation Memory card (Rev C)
### Architectural Philosophy: Control Plane vs. Data Plane

Always adhere to this strict division of labor between hardware and software:

* **The Data Plane (Verilog/FPGA):** Must handle the fast-path. This includes direct memory reads/writes, cycle-stealing
  from the Z80 using 12ns SRAM, `~WAIT` state generation, and wire-speed 8b/10b packet framing. Keep Verilog state
  machines strictly deterministic.
* **The Control Plane (RISC-V Softcore):** Must handle complex logic, exceptions, timeouts, lock arbitration (mutexes),
  dynamic PGAS routing tables, mailbox interrupt generation, and APU math emulation.

### Verilog & FPGA Guidelines

* **Zero-Contention DMA:** Prefer transparent cycle-stealing using the fast 12ns SRAM over explicitly asserting
  `~BUSRQ`/`~BUSAK` to pause the Z80.
* **Custom 8b/10b Protocol:** We use a custom physical layer. Do not generate standard Ethernet MAC logic. Use
  context-aware K-characters to define opcodes (e.g., `READ_SINGLE`, `WRITE_BLOCK`) to minimize payload overhead.
* **No Multi-Cycle Math in the Fast Path:** If a complex calculation is required on the fly (like CRC-8 or Modulo
  arithmetic for EOF checksums), generate Verilog that utilizes BRAM Lookup Tables (LUTs) to resolve the math in a
  single clock cycle.
* **Hardware Replay:** Implement error recovery at the PHY level. If an incoming packet fails the CRC/Disparity check,
  the Verilog must instantly fire a `NACK` and the transmitting FPGA must automatically dump a Replay Buffer to retry
  the transmission without alerting the Z80.

### Z80 Assembly Guidelines

* **Maximize Throughput:** When writing routines to move data to the network or the APU, heavily favor Z80
  block-transfer instructions (`LDIR` for memory-to-memory, `OTIR` for memory-to-I/O ports).
* **PGAS Interaction:** Treat remote memory exactly like local memory. The FPGA will handle the `~WAIT` states.
* **Spinlocks:** Use the I/O space for atomic operations. Lock requests are made via `IN A, (PORT)`. If the lock is
  acquired, it returns `0x00`. If busy, it returns `0xFF`. Use tight `JR NZ` loops for spinlocks.

### RISC-V C Firmware Guidelines

* **Role:** The C code is the "SmartNIC" firmware running on the MachXO3 at ~50MHz.
* **Bit-Twiddling is King:** Rely on the RISC-V for format translations. For example, when emulating the Am9511 APU,
  write highly optimized C functions to bit-shift the proprietary 32-bit Am9511 floating-point format into standard
  IEEE-754 `float` types before doing the math, and translate them back for the Z80.
* **Mailbox Management:** Firmware should parse incoming remote commands, structure the data into local SRAM buffers,
  and only pull the Z80's `~INT` pin when the payload is fully ready.

### Hardware Pragmatism & Tooling

* **Component Choices:** Prioritize reliable, easy-to-assemble hardware over "perfect" theoretical solutions (e.g.,
  preferring pre-crimped JST-SM pigtails or direct wire soldering over attempting to hand-crimp 1.00mm pitch headers).
* **Debugging:** Code should account for hardware visibility. Assume a custom RP2040-based Bus Probe is sitting on the
  backplane snooping the Address/Data lines via CBT3251 multiplexers.