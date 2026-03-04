
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

```text
A[0:7]   => Card port address
A[8]     => 0 -> slave, 1 -> master
A[8]     => 0 -> read, 1 -> write (always in reference to the card)
A[10]    => reserved
A[11:15] => Physical Address P[16:20]
D[0:7]   => Physical Address P[8:15]
```

For an I/O card, the physical address bits might be block addresses or some other address,
e.g. a 512 byte sector.

To read a block from disk to memory, the CPU would send:

- To memory card: SLAVE, WRITE, base address
- To disk card: MASTER, READ, block address

After the CPU initializes the receiver, it initializes the sender.  The sender
will then

- assert S_EN
- put SD[0:7] on the bus
- Strobe S_STRB when it is valid
- wait a MCLK cycle
- assert S_INC to tell receiver to go to next address and loop
- assert S_DONE when finished instead of S_INC.
- deassert S_EN

The slave may assert S_BUSY to pause the sender.


To write a block to disk, the CPU would send:

- To memory card: SLAVE, READ, base address
- To disk ccard: MASTER, WRITE, block address

- Need to work out the details

Is this ok...  or should the READer (producer of data) always be the master?  

In the case of writing to disk, the disk knows it wants 512 bytes so it can
do the SINC correctly.  Need to work this out.













