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

## 3. Shadow Bus & DMA Protocol

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

# Shadow Bus Protocol

The use cases:

- read memory to disk
- write memory from disk
- transfer memory to memory.  
- read memory to a video card
- file transfer to/from serial card (might be kind of hard)

The CPU performs two port writes.  It first configures the bus slave
(usually a memory card), and then configures the bus master (usually a
peripheral).  But, memory to memory transfers are allowed, so a memory card
could be a bus master.

Memory cards have a second port address for ShadowBus operations, e.g. 0x40 - 0x4F.
For the memory card, the CPU will specify a 256 Byte word as the start of
the operation.

Disk controller would have ports in the range 0x50 - 0x5F (this is configurable via
an 8-position switch, they do not need to be 0x5x).

There will be several writes **to the same port** with a different value in A[8:9] to
indicate what is being written. We can communicate 14 bits of data with each write

This is for the memory card.  The Disk Card (CH376) would have a more complex command
structure, TBD.

```text
A[0:7]   => Card port address
A[8:14]  => Operand[8:14]
A[15]    => OpCode
D[0:7]   => Operand[0:7]
```

Opcode 0:
Master/Slave          = Operand[14] (1 = master, 0 = slave)
Direction             = Operand[13] (0 = to bus, 1 = from bus)
PhysicalAddress[0:12] = Operand[0:12]

Address 1:
PhysicalAddress[13:19] = Operand[0:6]
ByteCount[0:7]         = Operand[7:14] (up to 256 bytes)

NOTE: A DMA transfer should NOT cross a 4KB boundary, as physical pages are not
guaranteed to be contiguous in the virtual memory space.

Process:

CPU configures SLAVE fist, to read memory to the bus

OUT card0, Opcode 0(Slave, ToBus, PA[0:12])
OUT card0, Opcode 1(PA[13:19], 8'b0)

CPU Configures MASTER last, to get memory from the bus, for 89 bytes

OUT card1, Opcode 0(Master, FromBus, PA[0:12])
OUT card1, Opcode 1(PA[13:19], 89)

After the 2nd OUT to card 1, card 1 will take over the shadow bus and do the transfer.

If card 1 were a disk controller, the OUT would need to specify the actual COMMAND and
other parameters.

Each MCLK cycle:
- Assert S_EN
- Assert Strobe
- Read byte
- Deassert Strobe, a
- Assert SINC
- Deasert SINC, Assert Strobe
- Read Byte
- ... 
- until ByteCount, then assert S_DONE instead of SINC
- Deassert S_EN
- Raise Z80_INT
  - Must wait for valid time to raise INT
  - Must respond to the INT READ
