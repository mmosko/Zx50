# Zx50 Bus Memory Architecture

The goal of the Zx50 memory architecture is to map any 4KB region of the Z80's logical 64KB address space to any physical 4KB page on a memory card. 

## 1. Address Translation Overview

The Z80 has a 64KB logical address space divided into **16 logical pages of 4KB each**. 
Each Zx50 memory card contains 1MB of physical SRAM, which is divided into **256 physical pages of 4KB each**.

The core job of the CPLD on each memory card is to act as an Address Translation Latch (ATL). When the Z80 accesses memory, the CPLD intercepts the top 4 bits of the address bus and translates them into an 8-bit physical page address using an external SRAM Look-Up Table (LUT).

```text
Address Translation:
Z80 A[15:12] (4 bits)  => MMU Translation LUT => Physical SRAM P[19:12] (8 bits)
Z80 A[11:0]  (12 bits) => Passed straight through to SRAM
```

### Boot Behavior & Card IDs
To prevent bus contention, only one card is allowed to drive the bus for any given logical page. 
* Cards are assigned a 4-bit Card ID via duplexed config pins during system reset.
* **Card 0** is the designated "Boot Card". On power-up, Card 0 automatically maps its physical pages to the Z80's logical pages to ensure the CPU has executable memory at `0x0000` immediately after reset.

## 2. Paging Protocol

To map a physical page to a logical Z80 page, the CPU performs an I/O Write using the `OUT (C), D` instruction. The Zx50 MMU listens to the base port `0x30`.

```text
Z80 I/O Write Map:
A[15:8] (B Reg) => The Logical Z80 Page to map (0x00 to 0x0F)
A[7:0]  (C Reg) => 0x30 | Target Card ID 
D[7:0]  (Data)  => The Physical 4KB Page to map into the slot (0x00 to 0xFF)
```

**Example:** To map Physical Page `0x85` on Card `0x0` into the Z80's Logical Page `0` (address `0x0000`):
* `B` = `0x00`
* `C` = `0x30` (Port 0x30 | Card 0)
* `D` = `0x85`
* Execute `OUT (C), D`

Whenever a card is explicitly assigned a page, all other cards on the bus snoop the transaction and automatically invalidate their own mappings for that logical page to resolve conflicts automatically.

## 3. Shadow Bus & DMA Protocol (Future / V2)

The Zx50 specification includes a "Shadow Bus" protocol designed for high-speed, cycle-stealing Direct Memory Access (DMA) between memory cards and peripherals without routing data through the Z80.

Memory cards have a second port address base for Shadow Bus operations (e.g., `0x40 - 0x4F`), and disk controllers would use a different range (e.g., `0x50 - 0x5F`). 

```text
Shadow Bus Configuration (Conceptual):
A[0:7]   => Card port address
A[8:14]  => Operand[8:14]
A[15]    => OpCode
D[0:7]   => Operand[0:7]
```
The CPU configures the SLAVE device (receiver) first, followed by the MASTER device (sender). Once the Master is configured, it takes over the Shadow Bus, asserting `S_EN`, strobing data bytes, and using `S_INC` / `S_DONE` to manage the block transfer entirely in the background.

**Current Implementation Note (NoDMA Fallback):**
Due to routing constraints on the Atmel ATF1508AS CPLD, the active physical firmware variant is `zx50_cpld_nodma`. The DMA, Arbiter, and Shadow Bus logic have been structurally bypassed to ensure a successful fit. Full Shadow Bus functionality requires a larger CPLD (ATF1514AS) or a modern FPGA upgrade.
