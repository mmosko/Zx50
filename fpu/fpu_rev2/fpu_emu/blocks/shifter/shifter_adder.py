"""Dedicated 6-bit carry-chain adder/subtractor for the ShifterBlock."""

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.readable import Readable


@fpga_resource(
    approach="Dual dedicated 6-bit CCU2C carry-chain adder/subtractor units (subtractor + adder) for shifter operations",
    luts=12,
    slices_ccu2c=6,
    delay_ns=1.8,
    cycles=1,
    shared_unit="shifter_adder",
)
class ShifterAdder(Readable):
    """Dedicated 6-bit carry-chain adder/subtractor for the ShifterBlock.

    In the Zx50 FPU, ShifterBlock contains two dedicated 6-bit carry-chain adders
    (3 CCU2C slices each, 6 slices total):
      1) Subtractor (sub_adder): computes (31 - bit_pos) & 0x1F for LZC
      2) Adder (add_adder): computes (32 + lo_zeros) & 0x3F for 64-bit LZC in parallel/cycle 2
         without single-adder resource conflicts or multi-cycle pipelining penalties.
    """

    WIDTH: int = 6
    MAX_VAL: int = (1 << WIDTH) - 1  # 63 (0x3F)
    MASK: int = MAX_VAL

    def __init__(self, name: str = "shifter_adder") -> None:
        self._name = name
        self._bus = Bus(name=name, size_in_bits=self.WIDTH)
        self._val: int = 0

    def add(self, a: int, b: int) -> int:
        """6-bit unsigned addition: (a + b) & 0x3F."""
        assert 0 <= a <= self.MAX_VAL, f"Operand a=0x{a:X} out of 6-bit range (0..{self.MAX_VAL})"
        assert 0 <= b <= self.MAX_VAL, f"Operand b=0x{b:X} out of 6-bit range (0..{self.MAX_VAL})"
        self._val = (a + b) & self.MASK
        self._bus.set(self._val)
        return self._val

    def sub(self, a: int, b: int) -> int:
        """6-bit unsigned subtraction: (a - b) & 0x3F."""
        assert 0 <= a <= self.MAX_VAL, f"Operand a=0x{a:X} out of 6-bit range (0..{self.MAX_VAL})"
        assert 0 <= b <= self.MAX_VAL, f"Operand b=0x{b:X} out of 6-bit range (0..{self.MAX_VAL})"
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
