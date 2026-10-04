"""Dedicated 10-bit adder for UPC (Microcode Program Counter)."""

from dataclasses import dataclass

from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.readable import Readable
from fpu_emu.hardware.register import Register


@dataclass(frozen=True)
class UpcAdderResult:
    """Result of a 10-bit UPC addition operation."""

    val: int
    carry: bool


class UpcAdder(Readable):
    """Dedicated 10-bit adder for UPC + 1.

    In the Zx50 FPU microsequencer, the UPC is a 10-bit address counter (0..1023).
    A dedicated 10-bit incrementer calculates UPC + 1.
    If the counter overflows (1023 + 1 = 1024), carry is asserted, indicating an error.
    """
    WIDTH: int = 10
    MAX_VAL: int = (1 << WIDTH) - 1  # 1023 (0x3FF)
    MASK: int = MAX_VAL

    def __init__(self, upc: Register) -> None:
        self._upc = upc
        self._upc_adder_bus = Bus(name="upc_adder", size_in_bits=self.WIDTH+1)

    def inc(self):
        """Adds 1 to a 10-bit UPC value.

        :param upc: 10-bit current UPC (0..1023)
        :return: UpcAdderResult containing the incremented 10-bit value and carry flag
        """
        upc_val = self._upc.read_int()
        assert 0 <= upc_val <= self.MAX_VAL, f"UPC 0x{upc_val:X} out of 10-bit range (0..{self.MAX_VAL})"
        raw = upc_val + 1

        # bit 11 is the carry flag
        self._upc_adder_bus.set(raw)

    def read(self) -> bytes:
        # This is combinatorial logic, so it is always +1 from whatever the upc register outputs
        self.inc()
        return self._upc_adder_bus.read()

    def read_int(self) -> int:
        """Reads the current adder output directly as an unsigned integer."""
        self.inc()
        return self._upc_adder_bus.read_int()

    @property
    def val(self) -> int:
        """The 10-bit incremented UPC value (bits 0..9)."""
        return self.read_int() & self.MASK

    @property
    def carry(self) -> bool:
        """The carry/overflow bit (bit 10, mask 0x400)."""
        return (self.read_int() & (1 << self.WIDTH)) != 0

    # def add(self, upc: int, step: int = 1) -> UpcAdderResult:
    #     """Adds an offset to a 10-bit UPC value.
    #
    #     :param upc: 10-bit current UPC (0..1023)
    #     :param step: Step to add (default 1)
    #     :return: UpcAdderResult containing the incremented 10-bit value and carry flag
    #     """
    #     assert 0 <= upc <= cls.MAX_VAL, f"UPC 0x{upc:X} out of 10-bit range (0..{cls.MAX_VAL})"
    #     raw = upc + step
    #     carry = raw > cls.MAX_VAL or raw < 0
    #     return UpcAdderResult(val=raw & cls.MASK, carry=carry)
