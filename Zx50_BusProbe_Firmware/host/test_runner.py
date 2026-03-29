"""
Zx50 Automated Backplane Characterization Runner
------------------------------------------------
Integrated Version: Individual Slot Reading, USB/WiFi Support,
and Correct HH:MM:SS Logging.
"""

import json
import time
from datetime import datetime
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
PICO_IP = '172.16.1.46'
PICO_PORT_TCP = 5050

# --- Test Definitions ---
TEST_FREQS = [100_000, 1_000_000, 10_000_000]
QUICK_TEST_MATRIX = [
    (42, 42), (42, 40), (42, 44), (42, 38), (42, 48)
]


class Zx50TestRunner:
    def __init__(self, pico_io: PicoConnection, scope_addr: str):
        self.pico = pico_io
        self.scope = TektronixMDO(scope_addr)

    def _ts(self):
        """Returns HH:MM:SS string."""
        return datetime.now().strftime("%H:%M:%S")

    def _build_stats(self, raw_tuple) -> SignalStats:
        """Robustly converts scope tuples into SignalStats objects."""
        if not raw_tuple or raw_tuple[0] is None:
            return SignalStats()

        # Handles 2-tuples (mean, std) or 5-tuples (mean, std, min, max, count)
        if len(raw_tuple) == 2:
            return SignalStats(mean=raw_tuple[0], stddev=raw_tuple[1])
        else:
            return SignalStats(
                mean=raw_tuple[0], stddev=raw_tuple[1],
                min_val=raw_tuple[2], max_val=raw_tuple[3],
                count=raw_tuple[4]
            )

    def connect(self):
        print(f"[{self._ts()}] Initializing Hardware Connections...")
        self.pico.connect()

        resp = self.pico.send_cmd("IDN?")
        if "OK" not in resp:
            raise ConnectionError(f"Pico verification failed: {resp}")

        self.scope.connect()

    def get_measurements(self, tx_pin, rx_pin) -> Measurement:
        """Routes pins and pulls all 8 statistical slots individually."""
        tx_resp = self.pico.send_cmd(f"BUS SELECT TX {tx_pin}")
        rx_resp = self.pico.send_cmd(f"BUS SELECT RX {rx_pin}")

        if "ERR" in tx_resp or "ERR" in rx_resp:
            print(f"  [!] Routing Error - TX:{tx_resp} RX:{rx_resp}")

        # Restore: Parse signal names from Pico Response
        tx_sig = tx_resp.split()[3] if len(tx_resp.split()) > 3 else "UNKNOWN"
        rx_sig = rx_resp.split()[3] if len(rx_resp.split()) > 3 else "UNKNOWN"

        # Clear statistical buffer for the new routing path
        self.scope.scope.write("MEASU:STATI:RES")
        time.sleep(0.5)

        # New: Pull measurements using the robust individual-query method
        batch = self.scope.get_all_measurements()

        return Measurement(
            tx_pin=tx_pin, rx_pin=rx_pin,
            tx_signal_name=tx_sig, rx_signal_name=rx_sig,
            ch1_vpp=self._build_stats(batch[0]),  # Slot 1
            ch4_vpp=self._build_stats(batch[1]),  # Slot 2
            phase=self._build_stats(batch[2]),  # Slot 3
            rise_time=self._build_stats(batch[3]),  # Slot 4
            fall_time=self._build_stats(batch[4]),  # Slot 5
            ch4_vhigh=self._build_stats(batch[5]),  # Slot 6
            ch4_vlow=self._build_stats(batch[6]),  # Slot 7
            ch4_pulse_width=self._build_stats(batch[7]),  # Slot 8
            ch4_pos_overshoot=SignalStats(),
            ch4_neg_overshoot=SignalStats()
        )

    def run_sweep(self):
        print(f"\n[{self._ts()}] --- Starting Automatic Sweep ---")
        sweep_data = {
            "metadata": {
                "timestamp": int(time.time()),
                "scope_addr": self.scope.address,
                "connection_mode": PICO_MODE
            },
            "test_runs": []
        }

        for freq in TEST_FREQS:
            print(f"\n[{self._ts()}] => Testing Frequency: {freq / 1e6} MHz")

            # Setup physical stimulus
            self.scope.configure_afg(frequency_hz=freq, amplitude_vpp=4.5)

            # Initial routing to give the scope something to see
            self.pico.send_cmd(f"bus select tx 42")
            self.pico.send_cmd(f"bus select rx 42")
            time.sleep(1.0)

            # Locked-Manual Setup (Centers the 4.5V signal at 2V/div)
            self.scope.setup_acquisition_manual(freq)
            self.scope.configure_acquisition(stat_population=50)

            current_run = {
                "source_waveform": asdict(SourceWaveform(freq, "SQUARE", 4.5)),
                "measurements": []
            }

            for tx_pin, rx_pin in QUICK_TEST_MATRIX:
                # FIXED: Newline and HH:MM:SS timestamps
                print(f"[{self._ts()}] Measuring TX:{tx_pin} -> RX:{rx_pin}...")

                meas_obj = self.get_measurements(tx_pin, rx_pin)
                current_run["measurements"].append(asdict(meas_obj))

                print(f"[{self._ts()}] Logged.")

            sweep_data["test_runs"].append(current_run)

        json_name = f"zx50_sweep_{sweep_data['metadata']['timestamp']}.json"
        with open(json_name, "w") as f:
            json.dump(sweep_data, f, indent=4)
        print(f"\n[{self._ts()}] Sweep Complete. Saved to {json_name}")


def main():
    if PICO_MODE == 'USB':
        pico_io = PicoUSB(PICO_PORT, PICO_BAUD)
    else:
        pico_io = PicoWiFi(PICO_IP, PICO_PORT_TCP)

    runner = Zx50TestRunner(pico_io, SCOPE_ADDR)

    try:
        runner.connect()
        runner.run_sweep()
    except Exception as e:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Hardware Error: {e}")
    finally:
        runner.pico.disconnect()
        runner.scope.disconnect()


if __name__ == "__main__":
    main()