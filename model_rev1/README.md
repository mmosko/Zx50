# ZX50 Memory Controller (CPLD)

## Overview
The ZX50 Memory Controller is the heart of the ZX50 memory card, implemented in an Atmel ATF1508AS CPLD. It acts as the bridge between the Z80 Backplane and the local physical memory chips (RAM, ROM, and the ATL SRAM).

By transitioning to a purely **combinatorial routing matrix** for memory accesses, the CPLD avoids clock-domain crossing latency and Z80 hold-time violations, providing cycle-accurate, zero-wait-state memory access.

## Hardware Architecture

```plantuml
@startuml
!theme plain
skinparam componentStyle rectangle

package "Z80 Backplane" {
  [Z80 CPU / Bus] as Z80
}

package "ZX50 Memory Card" {
  [74ABT245 Transceiver] as XCVR
  [CPLD (zx50_mem_control)] as CPLD
  [IS61C256AL (ATL)] as ATL
  [CY7C1049 (RAM 0/1)] as RAM
  [SST39SF040 (ROM)] as ROM
}

Z80 <--> XCVR : Z80 Data
Z80 --> CPLD : Z80 Addr / Control
XCVR <--> CPLD : Local Data (l_d)

CPLD --> ATL : atl_a (Logical Page)\natl_ce_n, atl_oe_n, atl_we_n
ATL -> RAM : atl_d (Physical Page Offset)

CPLD --> RAM : l_a (Page Offset)\nram_ce_n, oe_n, we_n
CPLD --> ROM : Linear Addr (atl_d + l_a)\nrom_ce_n, oe_n
@enduml
```

## Operating Modes & Combinatorial Invariants
The CPLD does not use a clocked State Machine for memory access. Instead, it relies on strictly prioritized combinatorial logic governed by the Z80's physical strobes (`MREQ`, `IORQ`, `RD`, `WR`). This guarantees that chip selects and write enables are asserted and de-asserted exactly in phase with the CPU.

### 1. Safe Default (Idle)
When the Z80 is not targeting the card, all transceivers are disabled (`z80_d_oe_n = 1`), and all local memory chips are deselected (`ce_n = 1`, `we_n = 1`).

### 2. MMU Write (`mmu_direct_wr`)
**Trigger:** `IORQ = 0`, `WR = 0`, Port = `0x3X`, and `X == card_addr`.
* **Invariants:**
    * Transceiver opens inward (`d_dir = 1`).
    * `atl_a` is driven by Z80 A11-A8 (Logical Page from CPU `B` register).
    * `atl_ce_n = 0`, `atl_oe_n = 1`.
    * `atl_we_n` is bound directly to the Z80 `WR_n` strobe to perfectly satisfy SRAM hold times.

### 3. ROM Read (`effective_use_rom`)
**Trigger:** Memory cycle (`MREQ = 0`), Card ID = 0, ROM is enabled, and Z80 is addressing the lower 32K (`A15 = 0`).
* **Invariants:**
    * ATL SRAM is completely bypassed (`atl_ce_n = 1`).
    * CPLD reconstructs the linear address to bypass the A11 hardware bug, driving `atl_d` with `{3'b000, z80_a[15:11]}`.
    * `rom_ce2_n = 0`, `oe_n` bound to Z80 `RD_n`.

### 4. RAM Access (`ram_hit`)
**Trigger:** Memory cycle (`MREQ = 0`), CPLD owns the logical page (`page_ownership[z80_a[15:12]] == 1`), and it is not a ROM Read.
* **Invariants:**
    * `atl_a` is driven by Z80 A15-A12 (Logical Page).
    * `atl_ce_n = 0`, `atl_oe_n = 0` (ATL outputs Physical Page onto `atl_d`).
    * RAM Chip Select (`ram_ce0_n` or `ram_ce1_n`) is toggled exclusively by the `A11` bit.
    * `we_n` and `oe_n` are bound directly to Z80 `WR_n` and `RD_n`.

## Sequence Diagram: MMU Configuration & RAM Access

```plantuml
@startuml
!theme plain
actor "Z80 CPU" as Z80
participant "CPLD (Combinatorial)" as CPLD
participant "ATL SRAM" as ATL
participant "Physical RAM" as RAM

== MMU Setup (OUT (C), r) ==
Z80 -> CPLD: IORQ_n=0, Port=0x30, Data=0x12
activate CPLD
note right of CPLD: Snoop Hit! Updates\npage_ownership synchronously
Z80 -> CPLD: WR_n=0
CPLD -> ATL: CE_n=0, WE_n=0, Addr=Logical Page
activate ATL
ATL -> ATL: Latch Data (0x12)
Z80 -> CPLD: WR_n=1
CPLD -> ATL: WE_n=1
deactivate ATL
deactivate CPLD

== Memory Write (LD (HL), A) ==
Z80 -> CPLD: MREQ_n=0, Addr=Logical Page + Offset
activate CPLD
CPLD -> ATL: CE_n=0, OE_n=0
activate ATL
ATL --> RAM: D[7:0] = Physical Page (0x12)
deactivate ATL
CPLD -> RAM: CE_n=0 (Based on A11)
activate RAM
Z80 -> CPLD: WR_n=0, Data=0xAA
CPLD -> RAM: WE_n=0, Data=0xAA
RAM -> RAM: Write 0xAA to 0x12XXX
Z80 -> CPLD: WR_n=1
CPLD -> RAM: WE_n=1
deactivate RAM
deactivate CPLD
@enduml
```

## Synchronous State Logic
While data routing is purely combinatorial, the CPLD maintains a synchronous core clocked by `mclk` to manage safe state transitions:
1.  **Hardware Reset:** On the rising edge of `reset_n`, the CPLD latches the physical DIP switches from the shared backplane control lines into `card_addr`. It resets `page_ownership` based on whether the card is flagged to provide the boot ROM.
2.  **Distributed MMU Snooping:** Every card monitors I/O writes to port `0x3X`. If `X` matches a card's ID, it claims the page in its `page_ownership` mask. If `X` belongs to another card, it instantly drops ownership.
3.  **ROM Kill-Switch:** If any CPU maps an MMU page into the lower 32K space (Logical pages 0-7), the boot ROM is permanently disabled (`rom_enabled = 0`), seamlessly replacing the boot ROM with dynamic RAM.
