from ast import Slice
from dataclasses import dataclass

from amaranth import Module, Cat, Mux, Value, Elaboratable
from amaranth.hdl.ast import Signal
from .mem_state import MemState
from .buses import BackplaneBus, ShadowBus, MemoryBus
from .mem_state_invariants import get_invariants

@dataclass
class HitDetector:
    mmu_snoop_wr: Value
    mmu_direct_wr: Value
    logical_page: Slice  # A8-A11 is a slice of the z80_a signal
    current_page_owned: Slice  # bit_select returns a slice
    z80_mem_hit: Value

class ZX50MemControl(Elaboratable):
    def __init__(self):
        # 1. Instantiate our neatly grouped bus objects!
        self.bp = BackplaneBus()
        self.sh = ShadowBus()
        self.loc = MemoryBus()

        # Internal registers
        self.dma_addr = Signal(20, name="dma_addr")
        self.card_addr = Signal(4, name="card_addr")      # Holds the latched DIP switch value
        self.has_boot_rom = Signal()    # Holds the latched BOOT_EN_N pin

        # 16 bits representing ownership of the 16 logical 4K pages
        self.page_ownership = Signal(16, name="page_own")
        self.rom_enabled = Signal()

        # A11 bug means the L_a[11] (12th bit) is an internal signal
        self.active_a11 = Signal()

    def elaborate(self, platform):
        m = Module()

        # Determine the active A11 bit
        # (This will eventually mux with self.dma_addr[11] when DMA is active)
        m.d.comb += self.active_a11.eq(self.bp.z80_a[11])

        self.reset_capture(m)

        # ==========================================
        # 2. Hit Detection (Combinatorial)
        # ==========================================
        hit = self.hit_detection()
        self.mmu_snooping(m, hit)
        self.memory_routing(m, hit)

        # 2. Combinatorial Defaults (The Anti-Latch Shield)
        # Every pin defaults to its safe/idle state here.
        # If a state doesn't explicitly override it, it safely falls back to this.
        m.d.comb += [
            self.bp.z80_d_oe_n.eq(1),
            self.bp.d_dir.eq(0),
            self.bp.wait_n.eq(1),
            self.bp.int_n.eq(1),

            self.sh.sh_d_oe_n.eq(1),
            self.sh.sh_c_dir.eq(0),
            self.sh.sh_en_n.eq(1),
            self.sh.sh_busy_n.eq(1),

            self.loc.atl_ce_n.eq(1),
            self.loc.atl_oe_n.eq(1),
            self.loc.atl_we_n.eq(1),
            self.loc.oe_n.eq(1),
            self.loc.we_n.eq(1)
        ]

        # ==========================================
        # 3. Master State Machine & Transitions
        # ==========================================
        with m.FSM(reset=MemState.IDLE.name) as fsm:

            for state in MemState:
                with m.State(state.name):

                    # 1. Apply Pin Invariants (from our helper file)
                    invariants = get_invariants(state, self.bp, self.sh, self.loc, self.dma_addr)
                    if invariants:
                        m.d.comb += invariants

                    # 2. State Transitions
                    # We match on the current state to determine where we can go next
                    match state:

                        case MemState.IDLE:
                            # -------------------------------------------------
                            # PRIORITY 1: The Z80 Always Wins
                            # -------------------------------------------------
                            with m.If(self.bp.reset_n == 1):
                                with m.If(hit.z80_mem_hit & (self.bp.b_z80_rd_n == 0)):
                                    m.next = MemState.Z80_MREQ_RD.name

                                with m.Elif(hit.z80_mem_hit & (self.bp.b_z80_wr_n == 0)):
                                    m.next = MemState.Z80_MREQ_WR.name

                                with m.Elif(hit.mmu_direct_wr):
                                    m.next = MemState.Z80_IORQ_MMU_SET.name
                                    
                            # -------------------------------------------------
                            # PRIORITY 2: DMA Requests (To be implemented)
                            # -------------------------------------------------
                            # with m.Elif(dma_wants_bus):
                            #     m.next = MemState.MUTE_ACTIVE.name

                        case MemState.Z80_MREQ_RD | MemState.Z80_MREQ_WR:
                            # Stay in this state until the Z80 finishes the request
                            with m.If(self.bp.b_z80_mreq_n == 1):
                                m.next = MemState.IDLE.name

                        case MemState.Z80_IORQ_MMU_SET:
                            with m.If(self.bp.b_z80_iorq_n == 1):
                                m.next = MemState.IDLE.name

        return m

    def reset_capture(self, m: Module):
        # ==========================================
        # 1. Reset Capture & Boot Initialization
        # ==========================================
        with m.If(self.bp.reset_n == 0):
            # Invert the active-low pin (1 = Has ROM, 0 = RAM Only)
            has_rom = ~self.bp.boot_en_n

            m.d.sync += [
                self.card_addr.eq(Cat(
                    self.bp.b_z80_wr_n,
                    self.bp.b_z80_rd_n,
                    self.bp.b_z80_iorq_n,
                    self.bp.b_z80_mreq_n
                )),
                self.has_boot_rom.eq(has_rom),

                # --- MMU Boot State Initialization ---
                self.rom_enabled.eq(has_rom),
                # If we have a ROM, claim the lower 32K (Pages 0-7 = 0x00FF)
                self.page_ownership.eq(Mux(has_rom, 0x00FF, 0x0000))
            ]

    def hit_detection(self) -> HitDetector:
        # ==========================================
        # 2. Hit Detection & Distributed MMU Snooping
        # ==========================================
        mmu_snoop_wr = (self.bp.b_z80_iorq_n == 0) & (self.bp.b_z80_wr_n == 0) & ((self.bp.z80_a[0:8] & 0xF0) == 0x30)
        mmu_direct_wr = mmu_snoop_wr & (self.bp.z80_a[0:8] == (0x30 | self.card_addr))

        # FIX: The logical page depends on the bus cycle type!
        # For OUT (C), r -> The target page is in the Z80 B register on A8-A11.
        # For Mem Access -> The target page is the top 4 bits of the address (A12-A15).
        logical_page = Mux(self.bp.b_z80_iorq_n == 0, self.bp.z80_a[8:12], self.bp.z80_a[12:16])

        # Normal Memory Hit
        current_page_owned = self.page_ownership.bit_select(logical_page, 1)
        z80_mem_hit = (self.bp.b_z80_mreq_n == 0) & current_page_owned

        return HitDetector(
            mmu_snoop_wr=mmu_snoop_wr,
            mmu_direct_wr=mmu_direct_wr,
            logical_page=logical_page,
            current_page_owned=current_page_owned,
            z80_mem_hit=z80_mem_hit,
        )

    def mmu_snooping(self, m: Module, hit: HitDetector):
        # --- Synchronous MMU State Tracking ---
        # We listen to the bus on every clock tick to maintain our ownership mask
        with m.If(self.bp.reset_n == 1):
            with m.If(hit.mmu_snoop_wr):
                with m.If(hit.mmu_direct_wr):
                    # We claim the page!
                    m.d.sync += self.page_ownership.bit_select(hit.logical_page, 1).eq(1)

                    # ROM Kill-Switch: If the CPU maps a page into the lower 32K (Pages 0-7),
                    # we permanently disable the Boot ROM. (A11 == 0).
                    with m.If(self.active_a11 == 0):
                        m.d.sync += self.rom_enabled.eq(0)

                with m.Else():
                    # Another card claimed it! We instantly drop ownership to prevent collisions.
                    m.d.sync += self.page_ownership.bit_select(hit.logical_page, 1).eq(0)

    def memory_routing(self, m: Module, hit: HitDetector):
        # ==========================================
        # 4. Memory Routing & Chip Selects
        # ==========================================

        # --- ROM Checks ---
        # The CPU wants to access the lower 32K of logical memory (A15 == 0)
        z80_hitting_rom = (self.bp.z80_a[15] == 0) & (self.bp.b_z80_mreq_n == 0)

        # Effective use means: This is Card 0, the ROM is enabled, and the CPU is targeting the lower 32K
        effective_use_rom = (self.card_addr == 0) & self.rom_enabled & z80_hitting_rom

        # --- RAM Checks ---
        # Safe to access RAM if: We have a memory hit, we are NOT updating the MMU,
        # and the ROM isn't intercepting the request.
        safe_to_access_ram = hit.z80_mem_hit & ~hit.mmu_direct_wr & ~effective_use_rom

        # Apply the Combinatorial Chip Selects
        m.d.comb += [
            # ROM Chip Select:
            # Active if effective_use_rom AND it is a READ cycle.
            # (the ROM does not have WRITE ability in hardware, must be programmed separately)
            self.loc.rom_ce2_n.eq(~(effective_use_rom & (self.bp.b_z80_wr_n == 1))),

            self.loc.ram_ce0_n.eq(~(safe_to_access_ram & (self.active_a11 == 0))),
            self.loc.ram_ce1_n.eq(~(safe_to_access_ram & (self.active_a11 == 1)))
        ]

        # --- Drive the ATL Data Bus ---
        # If the CPU is updating the MMU, we bridge the local data bus (l_d) to the LUT SRAM (atl_d)
        with m.If(hit.mmu_direct_wr):
            m.d.comb += self.loc.atl_d.eq(self.loc.l_d)
        # (We will add the DMA and ROM ATL overrides here later)
