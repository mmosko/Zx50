from typing import List, Optional

from fpu_emu.hardware.clock import Clock


class LutRom:
    def __init__(self, name: str, size: int, width: int, clock: Clock, initialize: Optional[List[int]] = None):
        self._name = name
        self._size = size
        self._width = width
        self._mask = (1 << width) - 1
        self._clock = clock
        self._last_read_tick = -1
        self._last_write_tick = -1
        self._readonly = (initialize is not None) if (initialize is None) else initialize
        if initialize:
            assert len(initialize) == self._size
            self._data = initialize.copy()
        else:
            self._data = [0] * size

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> int:
        return self._size

    def read(self, addr: int) -> int:
        assert 0 <= addr < self._size, f"Address {addr} out of bounds"
        assert self._last_read_tick != self._clock.cycles, f"EBR {self._name}: Multiple reads in cycle {self._clock.cycles}"
        self._last_read_tick = self._clock.cycles
        return self._data[addr]

class LutRam(LutRom):
    def __init__(self, name: str, size: int, width: int, clock: Clock):
        super().__init__(name, size, width, clock, None)

    def write(self, addr: int, data: int) -> None:
        assert 0 <= addr < self._size, f"Address {addr} out of bounds"
        assert 0 <= data <= self._mask, f"Data 0x{data:X} exceeds width of {self._width} bits"
        assert self._last_write_tick != self._clock.cycles, f"EBR {self._name}: Multiple writes in cycle {self._clock.cycles}"
        assert not self._readonly, f"EBR {self._name}: Cannot write to read-only buffer"

        self._last_write_tick = self._clock.cycles
        self._data[addr] = data
