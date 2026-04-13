from dataclasses import dataclass, field
from amaranth import Signal


@dataclass
class BackplaneBus:
    """ Physical connections to the Z80 Backplane (via buffers where applicable) """
    # System Clock
    mclk: Signal = field(default_factory=lambda: Signal())
    reset_n: Signal = field(default_factory=lambda: Signal(reset=1))
    boot_en_n: Signal = field(default_factory=lambda: Signal(reset=1))  # Pin 88

    # Address Bus (buffered, but always active and one-way, direct to CPLD)
    z80_a: Signal = field(default_factory=lambda: Signal(16))

    # Control Signals (Physically connected to the 'B_Z80' buffered nets!)
    # Note: During RESET_N = 0, these pins receive the 4-bit config switch ID.
    b_z80_mreq_n: Signal = field(default_factory=lambda: Signal(reset=1))
    b_z80_iorq_n: Signal = field(default_factory=lambda: Signal(reset=1))
    b_z80_rd_n: Signal = field(default_factory=lambda: Signal(reset=1))
    b_z80_wr_n: Signal = field(default_factory=lambda: Signal(reset=1))
    b_z80_m1_n: Signal = field(default_factory=lambda: Signal(reset=1))

    # Interrupt Daisy Chain (Buffered side)
    b_z80_iei: Signal = field(default_factory=lambda: Signal(reset=1))
    b_z80_ieo: Signal = field(default_factory=lambda: Signal(reset=1))

    # Open-Drain Backplane Controls (1 = Z/Released)
    wait_n: Signal = field(default_factory=lambda: Signal(reset=1))
    int_n: Signal = field(default_factory=lambda: Signal(reset=1))

    # Transceiver Direction and Enables
    z80_d_oe_n: Signal = field(default_factory=lambda: Signal(reset=1))
    d_dir: Signal = field(default_factory=lambda: Signal(reset=0))  # 0 = Card -> Bus


@dataclass
class ShadowBus:
    """ Physical connections to the DMA Shadow Backplane """
    # Transceiver Controls
    sh_d_oe_n: Signal = field(default_factory=lambda: Signal(reset=1))
    sh_c_dir: Signal = field(default_factory=lambda: Signal(reset=0))  # 0 = Master Driving

    # Control Signals (Inout/Open-Drain)
    sh_en_n: Signal = field(default_factory=lambda: Signal(reset=1))
    sh_stb_n: Signal = field(default_factory=lambda: Signal(reset=1))
    sh_inc_n: Signal = field(default_factory=lambda: Signal(reset=1))
    sh_rw_n: Signal = field(default_factory=lambda: Signal(reset=1))
    sh_done_n: Signal = field(default_factory=lambda: Signal(reset=1))
    sh_busy_n: Signal = field(default_factory=lambda: Signal(reset=1))


@dataclass
class MemoryBus:
    """ Physical connections to the internal SRAM, ROM, and LUT """
    # The physical internal data bus (shared by Z80, Shadow, and Memory)
    l_d: Signal = field(default_factory=lambda: Signal(8))

    # Address Translation Logic (LUT)
    atl_d: Signal = field(default_factory=lambda: Signal(8))
    atl_a: Signal = field(default_factory=lambda: Signal(4))  # Fixed to 4 bits [0:3]
    atl_oe_n: Signal = field(default_factory=lambda: Signal(reset=1))
    atl_ce_n: Signal = field(default_factory=lambda: Signal(reset=1))
    atl_we_n: Signal = field(default_factory=lambda: Signal(reset=1))

    # Internal Memory Addresses & Standard Controls
    l_a: Signal = field(default_factory=lambda: Signal(11))  # [0:10] strictly
    oe_n: Signal = field(default_factory=lambda: Signal(reset=1))
    we_n: Signal = field(default_factory=lambda: Signal(reset=1))

    # Specific Chip Selects & LEDs
    # Note: ram_ce0_n is physically tied to the TX LED circuit on Pin 99.
    ram_ce0_n: Signal = field(default_factory=lambda: Signal(reset=1))
    ram_ce1_n: Signal = field(default_factory=lambda: Signal(reset=1))
    rom_ce2_n: Signal = field(default_factory=lambda: Signal(reset=1))

    # Generic RX LED (Pin 100)
    led_rx: Signal = field(default_factory=lambda: Signal(reset=1))