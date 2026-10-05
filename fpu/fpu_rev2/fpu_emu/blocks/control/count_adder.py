"""Dedicated 6-bit counter adder / decrementer for register C."""

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.readable import Readable
from fpu_emu.hardware.register import Register


@fpga_resource(
    approach="6-bit dedicated CCU2C carry-chain decrementer for C counter",
    luts=6,
    slices_ccu2c=3,
    delay_ns=1.8,
    cycles=1,
    shared_unit="count_adder",
)
class CountAdder(Readable):
    """6-bit dedicated adder for C (really a dedicated DEC by 1).

    In the Zx50 FPU, register C is a 6-bit loop / shift counter (0..63).
    A dedicated 6-bit decrementer calculates C - 1.
    It is used by DJNZ (Decrement and Jump if Not Zero) to update C
    and evaluate the Zero Flag in a single cycle.
    """

    WIDTH: int = 6
    MAX_VAL: int = (1 << WIDTH) - 1  # 63 (0x3F)
    MASK: int = MAX_VAL

    def __init__(self, c: Register) -> None:
        self._c = c
        self._bus = Bus(name="count_adder", size_in_bits=self.WIDTH)

    def dec(self) -> None:
        """Calculates (C - 1) & 0x3F and updates the internal bus."""
        c_val = self._c.read_int()
        assert 0 <= c_val <= self.MAX_VAL, f"C register 0x{c_val:X} out of 6-bit range (0..{self.MAX_VAL})"
        new_val = (c_val - 1) & self.MASK
        self._bus.set(new_val)

    def read(self) -> bytes:
        # Combinatorial logic: decrements current C register output
        self.dec()
        return self._bus.read()

    def read_int(self) -> int:
        """Reads the current decremented output directly as an unsigned integer."""
        self.dec()
        return self._bus.read_int()

    @property
    def val(self) -> int:
        """The 6-bit decremented C value (bits 0..5)."""
        return self.read_int() & self.MASK

    @property
    def is_zero(self) -> bool:
        """True if the decremented value is zero."""
        return self.val == 0
