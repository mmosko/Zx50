# ==========================================
# DATA STRUCTURES
# ==========================================
from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceWaveform:
    frequency_hz: float
    waveform_type: str
    amplitude_vpp: float


@dataclass
class SignalStats:
    mean: Optional[float] = None
    stddev: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    count: Optional[int] = None


@dataclass
class Measurement:
    tx_pin: int
    rx_pin: int
    tx_signal_name: str
    rx_signal_name: str

    # Existing
    ch1_vpp: SignalStats
    ch4_vpp: SignalStats
    phase: SignalStats
    rise_time: SignalStats
    fall_time: SignalStats

    # NEW: Advanced Metrics
    ch4_vhigh: SignalStats
    ch4_vlow: SignalStats
    ch4_pos_overshoot: SignalStats
    ch4_neg_overshoot: SignalStats
    ch4_pulse_width: SignalStats
