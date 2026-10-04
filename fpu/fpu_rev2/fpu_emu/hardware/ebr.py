from typing import Optional, List

from fpu_emu.hardware.clock import Clock


class EBR:
    def __init__(self, name: str, size: int, width: int, read_only_buffer: Optional[List[int]], clock: Clock):
        self._name = name
        assert self._is_power_of_two(size)
        self._size = size
        self._width = width
        self._mask = (1 << width) - 1
        self._clock = clock
        self._last_read_tick = -1
        self._last_write_tick = -1
        self._readonly = read_only_buffer is not None
        if read_only_buffer:
            assert len(read_only_buffer) == self._size
            self._data = read_only_buffer.copy()
        else:
            self._data = [0] * size

    @classmethod
    def _is_power_of_two(cls, n: int):
        return n > 0 and (n & (n - 1)) == 0

    @property
    def name(self) -> str:
        return self._name

    def read(self, addr: int) -> int:
        assert 0 <= addr < self._size, f"Address {addr} out of bounds"
        assert self._last_read_tick != self._clock.cycles, f"EBR {self._name}: Multiple reads in cycle {self._clock.cycles}"
        self._last_read_tick = self._clock.cycles
        return self._data[addr]

    def write(self, addr: int, data: int) -> None:
        assert 0 <= addr < self._size, f"Address {addr} out of bounds"
        assert 0 <= data <= self._mask, f"Data 0x{data:X} exceeds width of {self._width} bits"
        assert self._last_write_tick != self._clock.cycles, f"EBR {self._name}: Multiple writes in cycle {self._clock.cycles}"
        assert not self._readonly, f"EBR {self._name}: Cannot write to read-only buffer"

        self._last_write_tick = self._clock.cycles
        self._data[addr] = data
