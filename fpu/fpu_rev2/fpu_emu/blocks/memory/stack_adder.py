"""Dedicated 9-bit counter adder for SP."""

from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.readable import Readable
from fpu_emu.hardware.register import Register


class StackAdder(Readable):
    """8-bit dedicated adder for SP+1 or SP-1. (SP is 7 bits)

    It is used by PUSH or POP
    and evaluate the Zero Flag, OVERFLOW, and UNDERFLOW.
    """

    OP_INC = 1
    OP_DEC = -1

    WIDTH: int = 7
    MAX_VAL: int = (1 << WIDTH) - 1  # 127 (0x7F)
    MASK: int = MAX_VAL

    def __init__(self, sp: Register) -> None:
        self._sp = sp
        self._bus = Bus(name="sp_adder", size_in_bits=self.WIDTH + 1)
        self._op = self.OP_INC

    def set_op(self, op: int):
        self._op = op

    def _run(self) -> None:
        """Calculates (SP +/- 1) & 0xFF and updates the internal 8-bit bus."""
        sp_val = self._sp.read_int()
        assert 0 <= sp_val <= self.MAX_VAL, f"SP register 0x{sp_val:X} out of 7-bit range (0..{self.MAX_VAL})"
        new_val = (sp_val + self._op) & 0xFF
        self._bus.set(new_val)

    def read(self) -> bytes:
        self._run()
        return self._bus.read()

    def read_int(self) -> int:
        """Reads the current adjusted output directly as an unsigned integer (8 bits)."""
        self._run()
        return self._bus.read_int()

    @property
    def val(self) -> int:
        """The 7-bit SP value (bits 0..6)."""
        return self.read_int() & self.MASK

    @property
    def is_overflow(self) -> bool:
        """True if SP increment resulted in overflow past 127 (bit 7 set)."""
        return self._op == self.OP_INC and bool(self.read_int() & (1 << self.WIDTH))

    @property
    def is_underflow(self) -> bool:
        """True if SP decrement resulted in underflow below 0 (borrow / bit 7 set)."""
        return self._op == self.OP_DEC and bool(self.read_int() & (1 << self.WIDTH))

    @property
    def is_zero(self) -> bool:
        """True if the adjusted SP value is zero (and no underflow/overflow)."""
        return self.read_int() == 0
