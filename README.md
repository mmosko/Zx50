# Zx50 Distributed Computer

> **A retro-modern, modular computing platform built around the Zilog Z80 microprocessor — featuring paged virtual
memory, high-speed Shadow DMA, and FPGA coprocessing.**

---

## 1. Welcome to the Zx50

The **Zx50** is a custom, modular computing architecture that marries the classic 8-bit computing ethos of the
late-1970s and 1980s with modern high-speed digital engineering.

At the heart of the system is the **Zilog Z80** microprocessor (inducted into
the [IEEE Spectrum Chip Hall of Fame](https://spectrum.ieee.org/chip-hall-of-fame-zilog-z80-microprocessor),
see the official [Zilog Z80 Datasheet](https://www.zilog.com/docs/z80/um0080.pdf)). 
The Zx50 reimagines the Z80 as a modern distributed computing workstation.

### What makes the Zx50 "Retro-Modern"?

* **Bare-Metal Simplicity**: The CPU executes pure, unadulterated Z80 machine code. You can program it in assembly, C,
  or native BASIC just like classic machines.
* **Breaking the 64KB Limit**: A custom hardware Memory Management Unit (MMU) implemented in a CPLD provides 4KB paged
  virtual memory across 1MB+ of physical SRAM.
* **Dual-Bus Highway**: In addition to the standard Z80 bus, a dedicated **40 MHz Shadow DMA Bus** streams data (network
  packets, disk blocks, and peer-to-peer memory transfers) in the background without halting the Z80.
* **Hardware Acceleration**: A modern FPGA coprocessor offloads 32-bit and 64-bit floating-point math, emulating the
  vintage AMD Am9511 APU with single-cycle lookups.
* **Deep Visibility**: Built-in microcontroller instrumentation (RP2040 and Microchip PIC) allows real-time bus
  snooping, cycle-by-cycle single stepping, and telemetry via an active front panel and bus probe.

---

## 2. Core Silicon & Chip Manifest

The Zx50 blends period-accurate Zilog NMOS/CMOS silicon with modern programmable logic and companion microcontrollers:

| Chip / Component              | Technology          | Primary Role in Zx50                                                                                                                               |
|:------------------------------|:--------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------|
| **Zilog Z84C0020**            | CMOS CPU            | **Central Processor**: Runs at 8 MHz – 10 MHz with 16-bit addressing and an 8-bit data path.                                                       |
| **Zilog Z84C30**              | CMOS CTC            | **Counter/Timer Circuit**: 4 independent channels generating periodic system ticks and baud rate clocks.                                           |
| **Zilog Z84C40**              | CMOS DART/SIO       | **Dual Serial Controller**: Dual-channel serial communications (Port 0 for USB console, Port 1 for RS-232) supporting IM 2 vectored interrupts.    |
| **Microchip ATF1508**         | 5V CPLD             | **Memory Controller & MMU**: Address Translation Latch (ATL) mapping 64KB logical address space into 16 independent 4KB pages backed by 1MB+ SRAM. |
| **Lattice MachXO2 / MachXO3** | Flash FPGA          | **Math Coprocessor & SmartNIC**: 32-bit/64-bit floating point APU emulation, fast BRAM LUT math, and future LVDS RDMA distributed clustering.      |
| **WIZnet W5300**              | Hardwired TCP/IP    | **10/100 Ethernet Controller**: Memory-mapped window for wire-speed network packet streaming via Z80 `LDIR`/`LDDR` block transfers.                |
| **WCH CH376S**                | Mass Storage IC     | **USB Host & SD Card Controller**: Hardware FAT16/FAT32 file manager mapped into the Z80 I/O space.                                                |
| **Raspberry Pi RP2040**       | Dual ARM Cortex-M0+ | **Instrumentation & Display**: Drives the Front Panel display/switches and coordinates circular trace buffers on the Bus Probe.                    |
| **Microchip PIC18F4620**      | 8-bit MCU           | **Real-Time Bus Interface**: Works alongside the RP2040 on the Bus Probe for cycle sampling, pin toggling, and non-intrusive bus analysis.         |

---

## 3. System Topology & Card Placement

The Zx50 chassis utilizes an 8-slot passive backplane bus.

### Chassis Slot Tour

* **Card 0: Front Panel**: System human interface featuring a 20x4 LCD, step/run switches, bus activity
  LEDs, and an RP2040 controller mapped to I/O port `0x50`.
* **Card 1: CPU, Clock & FPU FPGA**: Houses the 10 MHz Z80 CPU, the Clock Mezzanine (generating system `ZCLK` and
  `MCLK`), and the FPGA floating-point coprocessor.
* **Card 2: Timer + Serial**: Combines the Z80 CTC and Z80 DART with a dedicated 7.3728 MHz baud oscillator, providing
  dual serial channels (FTDI USB and MAX232 RS-232).
* **Card 3: Memory 0 (Boot / Primary)**: Contains the ATF1508 CPLD MMU, 1MB fast 12ns SRAM, 512KB Flash boot ROM (with
  automatic ROM kill-switch upon boot jump), and Shadow Bus DMA interface.
* **Card 4: Memory 1 (Secondary / NUMA)**: Secondary memory card providing an additional 1MB SRAM and participating in
  peer-to-peer Shadow Bus memory transfers.
* **Card 5: NetStorage (Future)**: Dual-purpose network and storage adapter combining W5300 10/100 Ethernet and CH376S
  USB/SD mass storage with direct 40 MHz Shadow DMA support.
* **Card 6: Expansion Slot (Future)**: Dedicated slot for secondary CPU compute tiles, multi-node LVDS RDMA clustering
  (PGAS), or audio/video synthesizers.
* **Card 7: Bus Probe (Rev B)**: Diagnostic and telemetry card featuring CBT3251 high-speed multiplexers for
  non-intrusive bus snooping, an RP2040 trace analyzer, and a color LCD.

---

## 4. The Backplane Bus & Signals

The passive backplane links all cards across a single multi-conductor bus trunk:

| Bus Group          | Width   | Signals        | Description                                                                                                                           |
|:-------------------|:--------|:---------------|:--------------------------------------------------------------------------------------------------------------------------------------|
| **Address**        | 16-bit  | `A[15:0]`      | Primary Z80 address bus. Snooped by memory card MMUs for 4KB page translations.                                                       |
| **Data**           | 8-bit   | `D[7:0]`       | Primary Z80 bidirectional data bus.                                                                                                   |
| **Control**        | 15-bit  | `C[14:0]`      | `~MREQ`, `~IORQ`, `~RD`, `~WR`, `~M1`, `~WAIT`, `~INT`, `~NMI`, `~RESET`, `~BUSRQ`, `~BUSAK`, `~HALT`, `~RFSH`, `IEI`, `IEO`.         |
| **Shadow Data**    | 9-bit   | `SD[8:0]`      | High-speed DMA data bus (8 data bits + 1 parity bit).                                                                                 |
| **Shadow Control** | 6-bit   | `SC[5:0]`      | `~S_EN` (Bus claim), `SRW` (Read/Write), `~SSTB` (Strobe), `~SINC` (Increment), `~S_BUSY` (Target stall), `~S_DONE` (Terminal count). |
| **GPIO**           | 16-bit  | `GPIO[15:0]`   | General purpose high-speed interconnect and node synchronization lines.                                                               |
| **Clocks**         | 2 lines | `ZCLK`, `MCLK` | `ZCLK` (8–10 MHz) and `MCLK` (4x ZCLK = 32–40 MHz).                                                                                   |

### AC Bus Termination

To preserve signal integrity at high frequencies without the continuous DC power draw of passive pull-up resistors, all
signal lines are **AC terminated** at both physical ends of the backplane using RC networks tied to GND.

---

## 5. Synchronized Clock Domains

The Zx50 operates across three harmonic clock domains:

```
+-------------------------------------------------------------+
|  Oscillator (32 MHz - 40 MHz)                               |
+-------------------------------------------------------------+
         |                                           |
         v (divide by 4)                             v (direct)
+-------------------------+                 +-------------------------+
|  ZCLK (8 MHz - 10 MHz)  |                 |  MCLK (32 MHz - 40 MHz) |
|  Z80 CPU, CTC, DART     |                 |  Shadow DMA, MMU Timing |
+-------------------------+                 +-------------------------+
                                                         |
                                                         v (PLL / 3x - 4x)
                                            +-------------------------+
                                            |  FPGA (96 MHz - 160 MHz)|
                                            |  FPU Coprocessor Math   |
                                            +-------------------------+
```

1. **`ZCLK` (8 MHz – 10 MHz)**: The fundamental processor clock driving CPU instruction fetch and peripheral cycles.
2. **`MCLK` (32 MHz – 40 MHz = 4x `ZCLK`)**: The synchronous master clock coordinating high-speed burst DMA and CPLD
   state machines.
3. **`FPGA Clock` (96 MHz – 160 MHz = 3x to 4x `MCLK`)**: Synthesized internally inside FPGA coprocessors for
   single-cycle math and DSP acceleration.

---

## 6. High-Speed Shadow DMA

The **Shadow Bus** runs in parallel with the primary Z80 bus to eliminate I/O bottlenecks:

* **Cycle-Stealing Transfers**: Using fast 12ns SRAM, memory cards can service a DMA burst during intervals when the Z80
  is not accessing memory, avoiding `~BUSRQ`/`~BUSAK` pauses.
* **Direct Peer-to-Peer Streaming**: NetStorage can stream Ethernet packets or USB file blocks directly into memory card
  SRAM at **40 MHz** without routing bytes through CPU registers.
* **Deterministic Handshaking**: Uses hardware-level strobes (`~SSTB`, `~SINC`) with target stall flow control
  (`~S_BUSY`).

---

## 7. Software Ecosystem

* **[`zx50_monitor/`](file:///Users/marc/Documents/z80/Zx50/zx50_monitor)**: The self-hosting OS kernel and monitor.
  Transitions from SST39SF040 Flash ROM to SRAM via a hardware "Phantom Jump", featuring interrupt-driven asynchronous
  I/O and lock-free Single-Producer / Single-Consumer (SPSC) ring buffers.
* **[`msbasic/`](file:///Users/marc/Documents/z80/Zx50/msbasic)**: Microsoft BASIC adapted to run natively with full
  terminal, file, and hardware integration.
* **[`z80pack/`](file:///Users/marc/Documents/z80/Zx50/z80pack)**: Full emulator and development testbed for running and
  testing Zx50 software without physical hardware.

---

## 8. Repository Layout

* [`boards/`](file:///Users/marc/Documents/z80/Zx50/boards): KiCad hardware schematics, PCB layouts, and exported
  netlists.
* [`docs/hardware/`](file:///Users/marc/Documents/z80/Zx50/docs/hardware): Detailed hardware subsystem specifications,
  errata, and pinouts.
* [`firmware/`](file:///Users/marc/Documents/z80/Zx50/firmware): Microcontroller firmware for the RP2040 and Microchip
  PIC.
* [`mmu/`](file:///Users/marc/Documents/z80/Zx50/mmu): Verilog HDL code for the ATF1508 CPLD memory controller.
* [`fpu/`](file:///Users/marc/Documents/z80/Zx50/fpu): Verilog HDL and simulation testbenches for the MachXO FPGA math
  coprocessor.
* [`AGENTS.md`](file:///Users/marc/Documents/z80/Zx50/AGENTS.md): Architecture guidelines, design philosophy, and coding
  standards for AI assistants.
