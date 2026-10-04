from typing import Union

from fpu_emu.hardware.readable import Readable


class Bus(Readable):
    """A combinational signal path."""

    def __init__(self, name: str, size_in_bits: int):
        assert size_in_bits > 0, "Bus size in bits must be positive"
        self._name = name
        self._size_in_bits = size_in_bits
        self._num_bytes = (size_in_bits + 7) // 8  # Ceiling division
        self._mask = (1 << size_in_bits) - 1  # e.g., 6-bit -> 0x3F, 10-bit -> 0x03FF
        self._data = bytearray(self._num_bytes)

    @property
    def name(self) -> str:
        return self._name

    @property
    def size_in_bits(self) -> int:
        return self._size_in_bits

    @property
    def size_in_bytes(self) -> int:
        return self._num_bytes

    def read(self) -> bytes:
        """Returns an immutable snapshot of raw bytes containing the masked bit state."""
        return bytes(self._data)

    def set(self, buf: Union[bytes, bytearray]) -> None:
        """Asynchronously sets the bus value."""
        assert len(buf) == self._num_bytes, (
            f"Bus {self._name}: Expected {self._num_bytes} bytes for "
            f"{self._size_in_bits}-bit bus, got {len(buf)}"
        )

        raw_val = int.from_bytes(buf, byteorder="big")
        masked_val = raw_val & self._mask
        self._data[:] = masked_val.to_bytes(self._num_bytes, byteorder="big")