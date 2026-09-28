"""Master Clock model for cycle-accurate FPU timing."""


class Clock:
    """Cycle counter and time tracking at target FPGA frequency (default 80 MHz)."""

    def __init__(self, freq_hz: float = 80_000_000.0):
        if freq_hz <= 0:
            raise ValueError(f"Clock frequency must be positive, got {freq_hz}")
        self._cycles: int = 0
        self._freq_hz: float = freq_hz

    @property
    def cycles(self) -> int:
        """Returns total elapsed clock cycles."""
        return self._cycles

    @property
    def freq_hz(self) -> float:
        """Returns clock frequency in Hertz."""
        return self._freq_hz

    @property
    def elapsed_seconds(self) -> float:
        """Returns elapsed wall time in seconds based on cycle count."""
        return self._cycles / self._freq_hz

    @property
    def elapsed_us(self) -> float:
        """Returns elapsed wall time in microseconds."""
        return (self._cycles / self._freq_hz) * 1_000_000.0

    def tick(self, count: int = 1) -> int:
        """Advances clock by `count` cycles. Returns new total cycle count."""
        if count < 0:
            raise ValueError(f"Clock tick count cannot be negative, got {count}")
        self._cycles += count
        return self._cycles

    def reset(self):
        """Resets the cycle counter to zero."""
        self._cycles = 0

    def __repr__(self) -> str:
        return f"<Clock cycles={self._cycles} freq={self._freq_hz / 1e6:.1f}MHz>"
