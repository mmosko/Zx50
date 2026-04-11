from amaranth.lib.enum import Enum


class MemState(Enum):
    # =========================================================================
    # Resting & Transition States
    # =========================================================================
    # Safe resting state. Transceivers closed, memory asleep, backplane lines floating.
    IDLE = 0

    # "The Brick Wall." Asserts WAIT and SH_BUSY to freeze the Z80 and Shadow
    # backplanes for 1 clock cycle while transceivers spin up or reverse direction.
    MUTE_ACTIVE = 1

    # Dropping off the bus. Transceivers shut instantly, open-drain lines yield
    # to Z. Allows the next master to take over immediately without stalling.
    MUTE_PASSIVE = 2

    # =========================================================================
    # Z80 Master States
    # =========================================================================
    # Z80 is reading from this card's local memory. (Data: Card -> Z80)
    Z80_MREQ_RD = 3

    # Z80 is writing to this card's local memory. (Data: Z80 -> Card)
    Z80_MREQ_WR = 4

    # Z80 is performing an I/O request targeting the MMU/DMA config registers
    # on this specific card.
    Z80_IORQ_MMU_SET = 5

    # =========================================================================
    # DMA Shadow Bus States
    # =========================================================================
    # DMA has requested the backplane but the Z80 is currently busy.
    # Pulls WAIT/BUSY low to stall the system until the Z80 cycle finishes.
    DMA_ARB_WAIT = 6

    # DMA Master owns the bus. Reading local memory and broadcasting to the
    # Shadow backplane. Master actively drives the control bus. (Data: Card -> Bus)
    DMA_MASTER_READ = 7

    # DMA Master owns the bus. Reading from the Shadow backplane and writing
    # to local memory. Master actively drives the control bus. (Data: Bus -> Card)
    DMA_MASTER_WRITE = 8

    # Card is targeted by a remote DMA Master. Transceiver open inward.
    # Memory receives write strobes mirrored from the Master. (Data: Bus -> Card)
    DMA_SLAVE_LISTEN = 9

    # =========================================================================
    # Interrupt Handling
    # =========================================================================
    # DMA transfer is complete. CPLD pulls INT_N low to interrupt the Z80.
    DMA_INT_SET = 10

    # Z80 acknowledges the interrupt. Transceiver opens (Card -> Z80) to drop
    # the 8-bit interrupt vector onto the bus. CPLD releases INT_N back to Z.
    DMA_INT_REPLY = 11
