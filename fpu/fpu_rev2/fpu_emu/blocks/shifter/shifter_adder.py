"""Dedicated 7-bit carry-chain adder/subtractor for the ShifterBlock."""

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.readable import Readable


@fpga_resource(
    approach="Dual dedicated 7-bit CCU2C carry-chain adder/subtractor units (subtractor + adder) with operand input MUXes",
    luts=30,
    slices_ccu2c=8,
    ffs=4,
    delay_ns=2.0,
    cycles=1,
    shared_unit="shifter_adder",
)
class ShifterAdder(Readable):
    """Dedicated 7-bit carry-chain adder/subtractor for the ShifterBlock.

    In the Zx50 FPU, ShifterBlock contains two dedicated 7-bit carry-chain adders
    (4 CCU2C slices each, 8 slices total):
      1) Subtractor (sub_adder): computes (31 - bit_pos) for LZC, (32 - count) or
         (64 - count) for LSL carry capture, and (count - 1) for LSR carry capture.
      2) Adder (add_adder): computes (32 + lo_zeros) for 64-bit LZC in parallel/cycle 2
         without single-adder resource conflicts or multi-cycle pipelining penalties.

    NOTE: Because multiple operations (LZC, LSL, LSR) share the sub_adder, an input
    multiplexer (4:1 7-bit MUX on input A, 4:1 7-bit MUX on input B) routes the operands:
      - Input A MUX selects: 31 (LZC), 32 (LSL32), 64 (LSL64), or count (LSR)
      - Input B MUX selects: bit_pos (LZC), count (LSL), or 1 (LSR)
    The input multiplexers are not explicitly modeled as separate classes, but are accounted
    for in the LUT (14 LUT4s) and FF (4 FFs) counts above.
    """

    WIDTH: int = 7
    MAX_VAL: int = (1 << WIDTH) - 1  # 127 (0x7F)
    MASK: int = MAX_VAL

    def __init__(self, name: str, clock: Clock) -> None:
        self._name = name
        self._bus = Bus(name=name, size_in_bits=self.WIDTH)
        self._val: int = 0
        self._clock: Clock = clock
        self._last_tick: int = -1

    def add(self, a: int, b: int) -> int:
        """7-bit unsigned addition: (a + b) & 0x7F."""
        assert 0 <= a <= self.MAX_VAL, f"Operand a=0x{a:X} out of 7-bit range (0..{self.MAX_VAL})"
        assert 0 <= b <= self.MAX_VAL, f"Operand b=0x{b:X} out of 7-bit range (0..{self.MAX_VAL})"
        assert self._last_tick != self._clock.cycles, "Multiple operations in same tick"
        self._last_tick = self._clock.cycles
        self._val = (a + b) & self.MASK
        self._bus.set(self._val)
        return self._val

    def sub(self, a: int, b: int) -> int:
        """7-bit unsigned subtraction: (a - b) & 0x7F."""
        assert 0 <= a <= self.MAX_VAL, f"Operand a=0x{a:X} out of 7-bit range (0..{self.MAX_VAL})"
        assert 0 <= b <= self.MAX_VAL, f"Operand b=0x{b:X} out of 7-bit range (0..{self.MAX_VAL})"
        assert self._last_tick != self._clock.cycles, "Multiple operations in same tick"
        self._last_tick = self._clock.cycles
        self._val = (a - b) & self.MASK
        self._bus.set(self._val)
        return self._val

    def read(self) -> bytes:
        return self._bus.read()

    def read_int(self) -> int:
        return self._bus.read_int()

    @property
    def val(self) -> int:
        return self._val
