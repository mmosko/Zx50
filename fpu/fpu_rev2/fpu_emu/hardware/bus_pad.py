"""BusPad hardware adapter: zero-pads a narrower Readable to a target bit width."""

from typing import Optional
from fpu_emu.hardware.readable import Readable


class BusPad(Readable):
    """Zero-pads a narrower Readable (such as a 6-bit or 10-bit Register/Bus) to a wider bit width (e.g. 32 bits).

    In hardware, this models zero-extending signals when connecting narrow registers to wider buses/multiplexers:
    e.g., {22'b0, imm} or {26'b0, c}.
    """

    def __init__(self, input_source: Readable, target_size_in_bits: int, name: Optional[str] = None) -> None:
        assert target_size_in_bits > 0, "Target size in bits must be positive"
        self._name = name or f"pad_{target_size_in_bits}"
        self._source = input_source
        self._target_size_in_bits = target_size_in_bits
        self._target_num_bytes = (target_size_in_bits + 7) // 8
        self._target_mask = (1 << target_size_in_bits) - 1

    @property
    def name(self) -> str:
        return self._name

    @property
    def source(self) -> Readable:
        return self._source

    @property
    def size_in_bits(self) -> int:
        return self._target_size_in_bits

    @property
    def size_in_bytes(self) -> int:
        return self._target_num_bytes

    def read(self) -> bytes:
        """Returns the zero-padded value as little-endian bytes of length size_in_bytes."""
        raw_int = self._source.read_int() & self._target_mask
        return raw_int.to_bytes(self._target_num_bytes, byteorder="little")

    def read_int(self) -> int:
        """Returns the zero-padded value directly as an unsigned integer."""
        return self._source.read_int() & self._target_mask
