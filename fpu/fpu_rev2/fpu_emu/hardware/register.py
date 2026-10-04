from typing import Union
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.readable import Readable
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import StatusFlag


class Register(Readable):
    def __init__(self, name: Reg, size_in_bits: int, clock: Clock):
        assert size_in_bits > 0, "Register size in bits must be positive"
        self._name = name
        self._size_in_bits = size_in_bits
        self._num_bytes = (size_in_bits + 7) // 8  # Ceiling division
        self._mask = (1 << size_in_bits) - 1       # e.g., 6-bit -> 0x3F, 10-bit -> 0x03FF
        self._clock = clock
        self._last_write_tick: int = -1
        self._data = bytearray(self._num_bytes)

    @property
    def name(self) -> Reg:
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

    def read_int(self) -> int:
        """Convenience method to read register payload directly as an unsigned int."""
        return int.from_bytes(self._data, byteorder="big")

    def write(self, buf: Union[bytes, bytearray]) -> None:
        """Writes raw bytes into the register, automatically masking to size_in_bits."""
        assert self._last_write_tick != self._clock.cycles, (
            f"Register {self._name}: Multiple writes in cycle {self._clock.cycles}"
        )
        assert len(buf) == self._num_bytes, (
            f"Register {self._name}: Expected {self._num_bytes} bytes for {self._size_in_bits}-bit register, got {len(buf)}"
        )

        self._last_write_tick = self._clock.cycles

        # Convert to integer, apply bitmask for exact bit width, and store back as bytes
        raw_val = int.from_bytes(buf, byteorder="big")
        masked_val = raw_val & self._mask
        self._data[:] = masked_val.to_bytes(self._num_bytes, byteorder="big")

    def reset(self) -> None:
        self._data = bytearray(self._num_bytes)
        self._last_write_tick = -1


class StatusRegister(Register):
    def __init__(self, name: Reg, size_in_bits: int, clock: Clock):
        super().__init__(name, size_in_bits, clock)
        # We allow each bit to be set individually
        self._last_bit_write_tick = [0] * 8

    def is_bit_set(self, bit: StatusFlag) -> bool:
        """Returns True if the specified bit index is set."""
        assert 0 <= bit.value < self._size_in_bits, f"Bit index {bit} out of bounds"
        val = int.from_bytes(self._data, byteorder="big")
        return bool(val & (1 << bit.value))

    def set_bit(self, bit: StatusFlag, value: Union[bool, int]) -> None:
        """
        Sets (True/1) or clears (False/0) a specific bit index (0 to size_in_bits - 1).

        """
        assert 0 <= bit.value < self._size_in_bits, (
            f"Register {self._name}: Bit index {bit} out of bounds (0..{self._size_in_bits - 1})"
        )
        assert self._last_bit_write_tick[bit.value] != self._clock.cycles, (
            f"Register {self._name} bit {bit}: Multiple writes in cycle {self._clock.cycles}"
        )

        current_val = int.from_bytes(self._data, byteorder="big")

        if value:
            new_val = current_val | (1 << bit.value)
        else:
            new_val = current_val & ~(1 << bit.value)

        self._last_bit_write_tick[bit.value] = self._clock.cycles
        self._data[:] = new_val.to_bytes(self._num_bytes, byteorder="big")

    def reset(self) -> None:
        super().reset()
        self._last_bit_write_tick = [0] * 8
