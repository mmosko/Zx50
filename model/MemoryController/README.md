# ZX50 Distributed Memory Controller

This repository contains the CPLD core for the **ZX50 Memory Expansion Card**, written in Python using
the [Amaranth HDL](https://amaranth-lang.org/).

The ZX50 is a modular, multi-card Z80 computer system. Because multiple memory cards share a single backplane, this
controller implements a **Distributed MMU architecture**. Cards actively "snoop" the bus, dynamically claiming or
yielding 4KB memory pages on the fly to prevent physical bus collisions. It also provides arbitration for a secondary "
Shadow Bus" used for Direct Memory Access (DMA).

For a deep dive into the physical PCB design, logical paging scheme, and timing requirements, please reference the
original architecture document: *
*[ZX50 Memory Architecture](https://github.com/mmosko/Zx50/blob/main/docs/hardware/Zx50_Memory.md)**.

## Why Amaranth HDL?

This project was ported from traditional Verilog to Amaranth HDL to leverage modern software engineering principles for
hardware design:

* **Object-Oriented Bus Management:** Physical pins are grouped into clean Python `@dataclass` structures (
  `BackplaneBus`, `MemoryBus`, etc.) rather than passing hundreds of loose wires through module ports.
* **Decoupled FSM Invariants:** The Moore state machine separates *transition logic* (when to change states) from
  *invariant logic* (what the pins do inside a state) using Python structural pattern matching (`match/case`), ensuring
  no missing states or unintended latches.
* **Modern Testbenches:** Replaces spaghetti Verilog testbenches with Python `async/await` coroutines. The
  `Z80BackplaneMock` allows us to "plug in" multiple digital-twin cards into a simulated backplane and mathematically
  prove they don't collide using standard Python `assert` statements.

## System Architecture

### 1\. The Distributed MMU

Instead of a centralized arbiter, each card monitors Z80 `OUT (C), r` instructions.

* If a card sees a write to its specific configuration port (e.g., `0x3A` for Card `0xA`), it updates its internal LUT
  and **claims** the 4KB logical page.
* If the card sees a write to *any other* card's port (e.g., `0x30` through `0x3F`), it instantly **drops** ownership of
  that page.

### 2\. Address Translation & Routing

The controller intercepts Z80 addresses and routes them through an external SRAM Address Translation Lookaside (ATL)
table. It combinatorialy decodes the physical page to drive `RAM_CE0`, `RAM_CE1`, or `ROM_CE`.

* **The ROM Kill-Switch:** If the Z80 maps a page into the lower 32K, the boot ROM is permanently disabled for that
  session, exposing the underlying RAM.
* **The A11 Hardware Bug:** Accurately models a physical PCB quirk where address line A11 routes to the RAM Chip
  Selects, forcing 4KB logical pages to be striped across two 2K physical boundaries.

### 3\. The Shadow DMA Bus (Priority 2)

*(In Progress)* The controller arbitrates between the Z80 (Priority 1) and the DMA Shadow Bus (Priority 2). If the DMA
is active but the Z80 suddenly requests the card, the DMA is stalled (`WAIT`/`BUSY` asserted) until the Z80 completes
its transaction.

-----

## Directory Map

* `/zx50/` - Core Hardware Source
    * `zx50_mem_control.py` - The top-level CPLD elaboratable module.
    * `buses.py` - Dataclass definitions for the physical traces.
    * `mem_state.py` - The Enum defining the master State Machine.
    * `mem_state_invariants.py` - Combinatorial pin mappings for every FSM state.
    * `main.py` - The build script to generate `zx50_mem_control_generated.v`.
* `/tests/` - Python-based Testbenches
    * `cpu_mock.py` - Contains the `Z80BackplaneMock` for multi-card integration testing.
    * `test_reset_latch.py` - Proves DIP switches and Boot ROM straps initialize correctly.
    * `test_mmu_snoop.py` - Proves the Distributed MMU successfully steals pages across two physical cards.

-----

## 🛠 Current Progress & Resume Point

**Completed:**

- [x] Python project structure (`/zx50` and `/tests`).
- [x] Bus Dataclasses (`bp`, `sh`, `loc`).
- [x] State Machine Enums & Combinatorial Invariants matrix.
- [x] Reset Sequence & Boot Latch Initialization.
- [x] **Distributed MMU Snooping Protocol** (Fully tested across 2 cards).
- [x] **Address Translation Routing** (Chip Select logic, ROM Kill-switch, A11 Bug multiplexing).
- [x] Z80 Priority-1 FSM Transitions (`IDLE` -\> `RD`/`WR`/`MMU`).

**Next Up:**

1. **Z80 Memory Testing:** Write `test_z80_mem_access.py` using the newly added `mem_read` and `mem_write` backplane
   mocks to prove `ram_ce0_n`, `ram_ce1_n`, and transceivers route correctly across 2 cards.
2. **DMA FSM Transitions:** Wire up the triggers for `DMA_MASTER_READ`, `DMA_MASTER_WRITE`, `DMA_ARB_WAIT`, and
   `DMA_SLAVE_LISTEN` states.

