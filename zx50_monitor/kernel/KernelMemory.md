# Zx50 Kernel Memory Architecture

N.B. This is a design document, not what is currently implemented

This document defines the memory management system for the Zx50 Operating System, including physical page allocation, MMU hardware interaction, and context switching.

## 1. Hardware MMU & Physical Addressing

The Zx50 utilizes a hardware Memory Management Unit (MMU) capable of mapping 4KB physical memory pages into any 4KB logical window of the Z80's 64KB address space.

To future-proof the OS for up to 16 expansion cards (16MB total RAM), physical pages are identified internally as a 16-bit `WORD`:
* **Upper Byte (Port):** The hardware I/O port of the memory card (`0x30` to `0x3F`). 
* **Lower Byte (Page):** The specific physical page on that card (`0x00` to `0xFF`).

*Note: The ROM card is permanently assigned to port `0x30`.*

## 2. Logical Memory Map

The Z80's 64KB logical address space is divided strictly between Kernel Space and User Space.

* **`0x0000 - 0x3FFF` (16KB Kernel Space):** Reserved for the OS ROM, Kernel RAM, OS Variables, and the Kernel Stack. 
  * Physical pages `0x3000` through `0x3003` are permanently reserved for this space.
* **`0x4000 - 0xFFFF` (48KB User Space):** The application execution window. Apps are compiled with `ORG 0x4000` and are swapped in and out of this space by the scheduler.

## 3. The Allocator (`PAGE_OWNERSHIP`)

The OS tracks physical memory usage via a flat 1KB byte-array named `PAGE_OWNERSHIP`. This table tracks 1024 physical pages (representing 4 memory cards).

**Byte Values:**
* `0x00` = Free
* `0xFF` = System / Kernel Reserved
* `0x01` to `0x0A` = Owned by a specific application (represented by its `PROG_TABLE` PID).

### Allocation Strategies
* **Version 1 (Current): Linear Scan.** The OS uses the Z80's hardware-accelerated `CPIR` instruction to perform a rapid linear scan of `PAGE_OWNERSHIP` to find the first `0x00` byte, claim it with the requesting PID, and calculate the resulting Port/Page `WORD`.
* **Version 2 (Future): Free-List Ring Buffer.** To achieve `O(1)` allocation, the OS will eventually maintain a 2KB FIFO ring buffer of free physical pages. 

## 4. Application Tracking (PCB)

The Program Control Block (`PCB_Entry`) manages the execution state and physical memory footprint of each loaded application.

```assembly
; Run States
STATE_EMPTY     EQU 0x00
STATE_ACTIVE    EQU 0x01
STATE_PAUSED    EQU 0x02    ; Swapped out

STRUCT PCB_Entry
    Name        TEXT 8      ; App Name
    Base        WORD        ; Logical entry address (e.g., 0x4000)
    Size        WORD        ; App footprint in bytes
    Chksum      WORD        ; 16-bit validation checksum
    RunState    BYTE        ; EMPTY, ACTIVE, or PAUSED
    AppSP       WORD        ; Saved Stack Pointer
    PageMap     BLOCK 24    ; Array of up to 12 physical Port/Page WORDs
ENDS
```

## 5. The "Sliding Window" Loader

Because the MMU allows physical pages to be fragmented, applications do not require contiguous physical memory. The `xmodem` loader capitalizes on this to load massive applications using a tiny logical footprint.

1. **Request Page:** The loader calls `Sys_AllocPage` to get a free physical `WORD`.
2. **Map Scratchpad:** It maps this physical page into a temporary logical window (e.g., `0x8000`).
3. **Fill Page:** It streams 4KB of serial data into the `0x8000` window.
4. **Slide Window:** Once full, it requests a *new* physical page, maps it over top of `0x8000`, and continues downloading.
5. **Commit:** All allocated pages are sequentially logged in the app's `PageMap`.

## 6. Context Switching (The "Blind OUT" Optimization)

The 100Hz `System_Tick` timer is responsible for preemptive multitasking. 

When switching to a new application, comparing logical memory states is computationally expensive on the Z80. Instead, the scheduler uses the **"Blind OUT"** optimization:

1. The scheduler reads the new application's `PageMap` array.
2. It executes a tight loop of `OUT (C), A` instructions to blindly blast the entire `PageMap` directly to the MMU hardware.
3. Because the `OUT` instruction takes only 12 T-states, a full 48KB application (12 pages) can be completely mapped into hardware in microseconds with zero conditional logic.
4. The scheduler restores the `AppSP` and executes `RETI`, seamlessly resuming the application.