# Zx50 Bus

Verilog and simulation of dual phase bus.



# Zx50 Bus Memory architecture

The goal is to map any 4KB region of the physical 64KB to a 4KB page on a memory card.  Any
4KB page can map to any 4KB physical memory region.

```text
Address:
A[12:15] => 4K page ID (4 bits, 16 pages)
A[0:11]  => Byte address within page (12 bits, 4KB)
```

The Zx50 memory card is a 1MB physical SRAM device (likly 2x 4Mbit chips).  Thus,
it has 256x 4KB pages.

The job of the 1MB memory card is to map the 4KB page address A[12:15] to an 8-bit physical page
address:

```text
A[12:15] => P[12:20]
A[0:11]  => P[0:11]
```

One approach in a CPLD is to have 16x 8-bit latch and A[12:15] selects the latch.
Call these the address translation latches (ATLs).  These could be a different SRAM (or similar),
e.g. a 32x8 SRAM or larger.

The Zx50 bus may have multiple 1MB cards.  The CPU tells the bus which card is active
for which 4KB page and only one card is ever active for the same page.  This means a card
must have, essentially a two stage decoder:

```text
A[12:15] => 4-bit latch => to enable 16x 8-bit latches.  
```

Call this the page active latch (PAL).

The CPU may choose to have different 1MB cards active at the same time, but there is
only ever one card active for a specific page.

The Zx50 will also have a 32KB ROM card.  The ROM card will use the exact same decoder,
so it can map any 4KB ROM addresss to a 4KB page.  The ROM card only has 8 possible pages, so
it only uses 16x 3-bit ATLs.  The ROM card defaults to active PAL for all pages with a linear
ATL.

We need a way to jumper a 1MB card to also default to active for pages 8-15 (32K-64K) with
a linear map.  I.e. the "boot up" memory.

Future extension might go for up to a 4MB RAM card, but this could behave like 4 cards
(using 4 ports), but only 1 bus slot.

# Timing

The PAL -> ATL -> memory chip path must be quick.  If we use 55ns SRAM chips for the
1MB memory, then we might have about 50ns to play with, but it would be best if the
PAL -> ATL -> memory path was 10 - 30 ns.

# Zx50 Bus Protocol for paging

Each RAM/ROM card has its own port address within a base, e.g. 0x30 - 0x3F (up to 16 cards, 
e.g. 4x cards at 4MB using 4 port addresses).  For now, we will assume a 1MB card that
uses a single port.


The CPU will output:

```text
A[0:7]   => Card port address
A[8:11]  => 4K page address
A[12:15] => reserved 
D[0:7]   => Card physical 4K block (up to 256 of them for 1MB)
```

If card address == A[0:7], then the card is explicitly activated for A[8:11] page.
All other cards must set themselves inactive for that page.

There is currently no support for doing a IO READ to these addresses.

# Shadow Bus Protocol

The use cases:

- read memory to disk
- write memory from disk
- transfer memory to memory.  This would be 256 bytes implicitly?  
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





# Project Organizaiton

```text
Zx50Bus/
├── build/          # (Existing) Simulation compiled binaries
├── docs/           # (Existing) Datasheets and notes
├── gtkw/           # (Existing) GTKWave save files
├── scripts/        # Helper scripts (e.g., a quick .bat file to run POF2JED)
├── sim/            # (Existing) Testbenches (e.g., tb_cpld_core.v)
├── src/            # (Existing) Pure Verilog RTL (zx50_cpld_core.v, etc.)
├── syn/            # Synthesis root directory
│   └── quartus/    # Quartus-specific working directory
│       ├── zx50_memory_card.qpf  # The Quartus Project File
│       ├── zx50_memory_card.qsf  # The Quartus Settings File (Pin mappings!)
│       └── output_files/         # Quartus automatically creates this folder
│           ├── zx50_memory_card.pof  # The raw Altera binary Quartus generates
│           └── zx50_memory_card.jed  # The final Atmel binary you create with POF2JED
└── waves/          # (Existing) VCD/FST waveform dumps
```





