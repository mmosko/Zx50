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

    WIDTH: int = 8
    MAX_VAL: int = (1 << WIDTH) - 1
    MASK: int = MAX_VAL

    def __init__(self, sp: Register) -> None:
        self._sp = sp
        self._bus = Bus(name="sp_adder", size_in_bits=self.WIDTH)
        self._op = self.OP_INC

    def set_op(self, op: int):
        self._op = op

    def _run(self) -> None:
        """Calculates (SP +/- 1) & 0x1FF and updates the internal bus."""
        sp_val = self._sp.read_int()
        assert 0 <= sp_val <= self.MAX_VAL, f"SP register 0x{sp_val:X} out of 6-bit range (0..{self.MAX_VAL})"
        new_val = (sp_val + self._op) & self.MASK
        self._bus.set(new_val)

    def read(self) -> bytes:
        # Combinatorial logic: decrements current C register output
        self._run()
        return self._bus.read()

    def read_int(self) -> int:
        """Reads the current adjusted output directly as an unsigned integer."""
        self._run()
        return self._bus.read_int()

    @property
    def val(self) -> int:
        """The 9-bit SP value."""
        return self.read_int() & self.MASK

    @property
    def is_zero(self) -> bool:
        """True if the decremented value is zero."""
        return self.val == 0
