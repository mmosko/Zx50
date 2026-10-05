"""BusPad hardware adapter: zero-pads a narrower Readable to a target bit width."""

from typing import Optional
from fpu_emu.hardware.readable import Readable


class BusPad(Readable):
    """Zero-pads or sign-extends a narrower Readable to a wider bit width (e.g. 32 bits).

    In hardware, this models zero-extending or sign-extending signals when connecting
    narrow registers to wider buses/multiplexers:
    e.g., {22'b0, imm} or {{20{ea[11]}}, ea[11:0]}.
    """

    def __init__(
        self,
        input_source: Readable,
        target_size_in_bits: int,
        signed: bool = False,
        name: Optional[str] = None,
    ) -> None:
        assert target_size_in_bits > 0, "Target size in bits must be positive"
        self._name = name or f"pad_{target_size_in_bits}"
        self._source = input_source
        self._target_size_in_bits = target_size_in_bits
        self._target_num_bytes = (target_size_in_bits + 7) // 8
        self._target_mask = (1 << target_size_in_bits) - 1
        self._signed = signed

        src_bits = int(getattr(input_source, "size_in_bits", len(input_source.read()) * 8))
        assert target_size_in_bits >= src_bits, (
            f"Target size ({target_size_in_bits}) must be >= source size ({src_bits})"
        )
        self._src_sign_bit = 1 << (src_bits - 1)
        self._sign_ext_mask = self._target_mask ^ ((1 << src_bits) - 1)

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
        """Returns the padded value as little-endian bytes of length size_in_bytes."""
        raw_int = self.read_int()
        return raw_int.to_bytes(self._target_num_bytes, byteorder="little")

    def read_int(self) -> int:
        """Returns the padded value directly as an unsigned integer."""
        val = self._source.read_int()
        if self._signed and (val & self._src_sign_bit):
            val |= self._sign_ext_mask
        return val & self._target_mask

