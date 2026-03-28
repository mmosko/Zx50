"""
Zx50 Automated Backplane Characterization Runner
------------------------------------------------
Refactored with an Abstract IO Layer for USB and Wi-Fi.
"""

import json
import time
from dataclasses import asdict

from measurements import SignalStats, Measurement, SourceWaveform
from pico_usb import PicoUSB
from pico_wifi import PicoWiFi
from pin_connection import PicoConnection
from scope_control import TektronixMDO

# --- Hardware Configuration ---
SCOPE_ADDR = 'TCPIP0::172.16.1.43::inst0::INSTR'

# Connection Toggle: 'USB' or 'WIFI'
PICO_MODE = 'USB'

# USB Settings
PICO_PORT = '/dev/ttyACM0'
PICO_BAUD = 115200

# Wi-Fi Settings
PICO_IP = '172.16.1.108'
PICO_PORT_TCP = 5050

# --- Test Definitions ---
TEST_FREQS = [100_000, 1_000_000, 10_000_000]
QUICK_TEST_MATRIX = [
    (42, 42),  # Primary Signal Integrity (CLK)
    (42, 40),  # Crosstalk to Pin 40 (~HALT~)
    (42, 41),  # Crosstalk to Pin 41
    (42, 43),  # Crosstalk to Pin 43
    (42, 44)  # Crosstalk to Pin 44 (MCLK)
]

class Zx50TestRunner:
    def __init__(self, pico_io: PicoConnection, scope_addr: str):
        self.pico = pico_io  # Dependency injected!
        self.scope = TektronixMDO(scope_addr)

    def connect(self):
        """Initializes hardware connections."""
        self.pico.connect()

        resp = self.pico.send_cmd("IDN?")
        if "OK" not in resp:
            raise ConnectionError(f"Pico verification failed: {resp}")

        self.scope.connect()
        self.scope.match_channels()
        self.scope.configure_acquisition(record_length=10000, stat_population=50)

    def disconnect(self):
        """Safely tears down hardware connections."""
        self.pico.disconnect()
        try:
            self.scope.disconnect()
        except Exception:
            pass

    def _build_stats(self, raw_tuple) -> SignalStats:
        if not raw_tuple or raw_tuple[0] is None:
            return SignalStats()
        if len(raw_tuple) == 2:
            return SignalStats(mean=raw_tuple[0], stddev=raw_tuple[1])
        else:
            return SignalStats(mean=raw_tuple[0], stddev=raw_tuple[1], min_val=raw_tuple[2], max_val=raw_tuple[3],
                               count=raw_tuple[4])

    def get_measurements(self, tx_pin, rx_pin, freq, amp_vpp=4.0) -> Measurement:
        tx_resp = self.pico.send_cmd(f"SELECT TX {tx_pin}")
        rx_resp = self.pico.send_cmd(f"SELECT RX {rx_pin}")

        if "ERR" in tx_resp or "ERR" in rx_resp:
            print(f"  [!] Routing Error - TX:{tx_resp} RX:{rx_resp}")

        tx_sig = tx_resp.split()[3] if len(tx_resp.split()) > 3 else "UNKNOWN"
        rx_sig = rx_resp.split()[3] if len(rx_resp.split()) > 3 else "UNKNOWN"

        ch1_vpp_raw = self.scope.get_vpp_stats("CH1")
        ch4_vpp_raw = self.scope.get_vpp_stats("CH4")
        phase_raw = self.scope.get_phase_stats("CH1", "CH4")
        rise_raw = self.scope.get_rise_time_stats("CH4")
        fall_raw = self.scope.get_fall_time_stats("CH4")

        high_raw, _, low_raw, _ = self.scope.get_logic_levels("CH4")
        pos_over_raw, _, neg_over_raw, _ = self.scope.get_overshoot("CH4")
        pw_raw = self.scope.get_pulse_width("CH4")

        return Measurement(
            tx_pin=tx_pin, rx_pin=rx_pin,
            tx_signal_name=tx_sig, rx_signal_name=rx_sig,
            ch1_vpp=self._build_stats(ch1_vpp_raw),
            ch4_vpp=self._build_stats(ch4_vpp_raw),
            phase=self._build_stats(phase_raw),
            rise_time=self._build_stats(rise_raw),
            fall_time=self._build_stats(fall_raw),

            # Pack the new stats (packaging them as 2-tuples so _build_stats accepts them)
            ch4_vhigh=self._build_stats((high_raw, None)),
            ch4_vlow=self._build_stats((low_raw, None)),
            ch4_pos_overshoot=self._build_stats((pos_over_raw, None)),
            ch4_neg_overshoot=self._build_stats((neg_over_raw, None)),
            ch4_pulse_width=self._build_stats(pw_raw)
        )

    def run_sweep(self):
        print("\n--- Starting Automatic Sweep ---")
        sweep_data = {
            "metadata": {
                "timestamp": int(time.time()),
                "scope_addr": self.scope.address,
                "connection_mode": PICO_MODE
            },
            "test_runs": []
        }

        for freq in TEST_FREQS:
            print(f"\n=> Testing Frequency: {freq / 1e6} MHz")
            self.scope.configure_afg(frequency_hz=freq, amplitude_vpp=4.0)

            print("Running Scope AutoSet (Wait 6s)...")
            self.scope.scope.write("AUTOSet EXECute")
            time.sleep(6)

            current_run = {
                "source_waveform": asdict(SourceWaveform(frequency_hz=freq, waveform_type="SQUARE", amplitude_vpp=4.0)),
                "measurements": []
            }

            for tx_pin, rx_pin in QUICK_TEST_MATRIX:
                print(f"  Measuring TX:{tx_pin} -> RX:{rx_pin}...", end="", flush=True)
                meas_obj = self.get_measurements(tx_pin, rx_pin, freq, amp_vpp=4.0)
                current_run["measurements"].append(asdict(meas_obj))
                print(" Logged.")

            sweep_data["test_runs"].append(current_run)

        json_name = f"zx50_sweep_{sweep_data['metadata']['timestamp']}.json"
        with open(json_name, "w") as f:
            json.dump(sweep_data, f, indent=4)
        print(f"\nSweep Complete. Data saved to {json_name}")


def main():
    # 1. Instantiate the correct IO class based on the toggle
    if PICO_MODE == 'USB':
        pico_io = PicoUSB(PICO_PORT, PICO_BAUD)
    else:
        pico_io = PicoWiFi(PICO_IP, PICO_PORT_TCP)

    # 2. Inject it into the runner
    runner = Zx50TestRunner(pico_io, SCOPE_ADDR)

    try:
        runner.connect()
        runner.run_sweep()
    except KeyboardInterrupt:
        print("\nSweep aborted by user.")
    except Exception as e:
        print(f"\nHardware Error: {e}")
    finally:
        runner.disconnect()


if __name__ == "__main__":
    main()