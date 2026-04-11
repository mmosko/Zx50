from amaranth import Signal
from .mem_state import MemState
from .buses import BackplaneBus, ShadowBus, MemoryBus


def get_invariants(state: MemState, bp: BackplaneBus, sh: ShadowBus, loc: MemoryBus, dma_addr: Signal):
    """
    Returns a list of Amaranth combinatorial assignments that define the physical
    pin states for a given FSM state.

    NOTE: Any pin not explicitly assigned here will safely fall back to the
    IDLE/Z default defined at the top of the main FSM's m.d.comb block.
    """

    match state:
        # =========================================================================
        # Resting & Transition States
        # =========================================================================
        case MemState.IDLE | MemState.MUTE_PASSIVE:
            return []  # Completely safe. All defaults apply (Card drops off bus).

        case MemState.MUTE_ACTIVE:
            return [
                # The "Brick Wall": Freeze both buses while transceivers flip.
                bp.wait_n.eq(0),
                sh.sh_busy_n.eq(0)
            ]

        # =========================================================================
        # Z80 Memory Access
        # =========================================================================
        case MemState.Z80_MREQ_RD:
            return [
                # Transceivers
                bp.z80_d_oe_n.eq(0),
                bp.d_dir.eq(0),  # 0 = Card -> Z80

                # Address Routing (Z80 holds the wheel)
                loc.l_a.eq(bp.z80_a[0:11]),  # Lower 11 bits bypass LUT
                loc.atl_a.eq(bp.z80_a[12:16]),  # Upper 4 bits hit the LUT SRAM

                # LUT Control (External SRAM drives ATL_D)
                loc.atl_ce_n.eq(0),
                loc.atl_oe_n.eq(0),
                loc.atl_we_n.eq(1),

                # Internal Memory Control
                loc.oe_n.eq(0),
                loc.we_n.eq(1)
            ]

        case MemState.Z80_MREQ_WR:
            return [
                # Transceivers
                bp.z80_d_oe_n.eq(0),
                bp.d_dir.eq(1),  # 1 = Z80 -> Card

                # Address Routing
                loc.l_a.eq(bp.z80_a[0:11]),
                loc.atl_a.eq(bp.z80_a[12:16]),

                # LUT Control (External SRAM drives ATL_D to decode physical page)
                loc.atl_ce_n.eq(0),
                loc.atl_oe_n.eq(0),
                loc.atl_we_n.eq(1),

                # Internal Memory Control
                loc.oe_n.eq(1),
                loc.we_n.eq(0)
            ]

        case MemState.Z80_IORQ_MMU_SET:
            return [
                # Transceivers
                bp.z80_d_oe_n.eq(0),
                bp.d_dir.eq(1),  # 1 = Z80 -> Card

                # Z80 is writing to the LUT SRAM configuration
                loc.atl_a.eq(bp.z80_a[0:4]),  # IO Port address selects the LUT slot
                # (loc.l_d physically carries the Z80 data into the LUT data pins)

                # LUT Control (Write Mode)
                loc.atl_ce_n.eq(0),
                loc.atl_oe_n.eq(1),  # Important: Let Z80 drive the data lines
                loc.atl_we_n.eq(0)
            ]

        # =========================================================================
        # DMA Shadow Bus Master
        # =========================================================================
        case MemState.DMA_ARB_WAIT:
            return [
                # Stall the Z80 and the Shadow Bus while we wait for a safe window
                bp.wait_n.eq(0),
                sh.sh_busy_n.eq(0),

                # Keep our finger on the elevator button
                sh.sh_en_n.eq(0)
            ]

        case MemState.DMA_MASTER_READ:
            return [
                # Transceivers & Backplane Request
                sh.sh_d_oe_n.eq(0),
                bp.d_dir.eq(0),  # 0 = Card -> Shadow Bus
                sh.sh_c_dir.eq(0),  # Master drives control lines
                sh.sh_en_n.eq(0),  # Hold the bus claim

                # Address Routing (DMA counter holds the wheel)
                loc.l_a.eq(dma_addr[0:11]),

                # LUT Control (Bypass Mode)
                loc.atl_ce_n.eq(1),  # Disable external LUT chip
                loc.atl_oe_n.eq(1),
                loc.atl_d.eq(dma_addr[12:20]),  # CPLD natively outputs the upper 8 bits

                # Internal Memory Control
                loc.oe_n.eq(0),
                loc.we_n.eq(1)
            ]

        case MemState.DMA_MASTER_WRITE:
            return [
                # Transceivers & Backplane Request
                sh.sh_d_oe_n.eq(0),
                bp.d_dir.eq(1),  # 1 = Shadow Bus -> Card
                sh.sh_c_dir.eq(0),  # Master drives control lines
                sh.sh_en_n.eq(0),  # Hold the bus claim

                # Address Routing
                loc.l_a.eq(dma_addr[0:11]),

                # LUT Control (Bypass Mode)
                loc.atl_ce_n.eq(1),
                loc.atl_oe_n.eq(1),
                loc.atl_d.eq(dma_addr[12:20]),

                # Internal Memory Control
                loc.oe_n.eq(1),
                loc.we_n.eq(0)  # Master asserts WE
            ]

        # =========================================================================
        # DMA Shadow Bus Slave
        # =========================================================================
        case MemState.DMA_SLAVE_LISTEN:
            return [
                # Transceivers
                sh.sh_d_oe_n.eq(0),
                bp.d_dir.eq(1),  # 1 = Shadow Bus -> Card
                sh.sh_c_dir.eq(1),  # Slave listens to control lines

                # Address Routing (Remote Master dictates address via DMA counter payload)
                loc.l_a.eq(dma_addr[0:11]),

                # LUT Control (Bypass Mode)
                loc.atl_ce_n.eq(1),
                loc.atl_oe_n.eq(1),
                loc.atl_d.eq(dma_addr[12:20]),

                # Internal Memory Control
                loc.oe_n.eq(1),
                loc.we_n.eq(sh.sh_stb_n)  # Mirror the Master's strobe precisely!
            ]

        # =========================================================================
        # Interrupts
        # =========================================================================
        case MemState.DMA_INT_SET:
            return [
                bp.int_n.eq(0)
            ]

        case MemState.DMA_INT_REPLY:
            return [
                # Z80 is asking for the vector. We open the Z80 transceiver to reply.
                bp.z80_d_oe_n.eq(0),
                bp.d_dir.eq(0)  # 0 = Card -> Z80
                # (The logic to output the specific 0x40 vector will be handled
                # by injecting the vector into l_d at the top level)
            ]

        case _:
            # This fails generation immediately if a new state is added to the Enum
            # but forgotten in this match block.
            raise ValueError(f"State machine generation failed: Unhandled state '{state}' in invariants mapping.")
