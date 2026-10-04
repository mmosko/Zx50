from typing import List

from fpu_emu.hardware.readable import Readable


class Mux(Readable):
    def __init__(self, name: str, inputs: List[Readable]) -> None:
        self._name = name
        self._inputs = inputs
        self._select = None

    def select(self, index: int) -> None:
        assert 0 <= index < len(
            self._inputs
        ), f"Mux {self._name}: Selection index {index} out of range (0..{len(self._inputs) - 1})"
        self._select = index

    def read(self) -> bytes:
        assert self._select is not None, f"Mux {self._name}: Read attempted before select() was set"
        return self._inputs[self._select].read()

    def read_int(self) -> int:
        """Convenience method to read directly as an unsigned int."""
        return int.from_bytes(self.read(), byteorder="big")
