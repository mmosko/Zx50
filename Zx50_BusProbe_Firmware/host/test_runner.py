"""
Zx50 Automated Backplane Characterization Runner
------------------------------------------------
Integrated Version: Individual Slot Reading, USB/WiFi Support,
and Correct HH:MM:SS Logging.
"""

import json
import logging
import time
from dataclasses import asdict

from measurements import Measurement, SourceWaveform, SignalStats
from pico_null import PicoNull
from pico_usb import PicoUSB
from pico_wifi import PicoWiFi
from pin_connection import PicoConnection
from scope_control import TektronixMDO

# --- Hardware Configuration ---
SCOPE_ADDR = 'TCPIP0::172.16.1.43::inst0::INSTR'

# Connection Toggle: 'USB' or 'WIFI' or 'None' (for debugging)
PICO_MODE = 'WIFI'

# USB Settings
PICO_PORT = '/dev/ttyACM0'
PICO_BAUD = 115200

# Wi-Fi Settings
PICO_IP = '172.16.1.46'
PICO_PORT_TCP = 5050

# --- Test Definitions ---
TEST_FREQS = [100_000, 1_000_000, 10_000_000]
# TEST_FREQS = [100_000]
QUICK_TEST_MATRIX = [
    (42, 42), (42, 40), (42, 44)
    # (42, 42)
]


class Zx50TestRunner:
    def __init__(self, pico_io: PicoConnection, scope_addr: str):
        self.pico = pico_io
        self.scope = TektronixMDO(scope_addr)

    def connect(self):
        logging.info("Initializing Hardware Connections...")
        self.pico.connect()

        resp = self.pico.send_cmd("IDN?")
        if "OK" not in resp:
            raise ConnectionError(f"Pico verification failed: {resp}")

        self.scope.connect()
        self.scope.initialize()

    def disconnect(self):
        self.scope.disconnect()
        self.pico.disconnect()

    def get_measurements(self, tx_pin, rx_pin) -> Measurement:
        """Routes pins and pulls stats. Optimized for crosstalk."""
        tx_resp = self.pico.send_cmd(f"BUS SELECT TX {tx_pin}")
        rx_resp = self.pico.send_cmd(f"BUS SELECT RX {rx_pin}")

        # Restore: Parse signal names from Pico Response
        tx_sig = tx_resp.split()[3] if len(tx_resp.split()) > 3 else "UNKNOWN"
        rx_sig = rx_resp.split()[3] if len(rx_resp.split()) > 3 else "UNKNOWN"

        time.sleep(0.5)

        # Optimization: Only measure pk2pk for crosstalk to save significant time
        is_crosstalk = (tx_pin != rx_pin)
        if is_crosstalk:
            batch = self.scope.get_crosstalk_measurements(stat_population=50)
        else:
            batch = self.scope.get_all_measurements(stat_population=50)

        # Helper to safely get stats or return empty object for skipped metrics
        def get_stat(key):
            return batch.get(key, SignalStats())

        return Measurement(
            tx_pin=tx_pin,
            rx_pin=rx_pin,
            tx_signal_name=tx_sig,
            rx_signal_name=rx_sig,
            ch1_vpp=get_stat(("pk2pk", 1)),
            ch4_vpp=get_stat(("pk2pk", 4)),
            phase=get_stat(("phase", 4)),
            rise_time=get_stat(("rise", 4)),
            fall_time=get_stat(("fall", 4)),
            ch4_vhigh=get_stat(("vhigh", 4)),
            ch4_vlow=get_stat(("vlow", 4)),
            ch4_pulse_width=get_stat(("pwid", 4)),
            ch4_pos_overshoot=get_stat(("pov", 4)),
            ch4_neg_overshoot=get_stat(("nov", 4)),
        )

    def run_sweep(self):
        logging.info(" --- Starting Automatic Sweep ---")
        sweep_data = {
            "metadata": {
                "timestamp": int(time.time()),
                "scope_addr": self.scope.address,
                "connection_mode": PICO_MODE
            },
            "test_runs": []
        }

        for freq in TEST_FREQS:
            logging.info(f" => Testing Frequency: {freq / 1e6} MHz")
            current_run = self._run_freq_sweep(freq)
            sweep_data["test_runs"].append(current_run)

        json_name = f"zx50_sweep_{sweep_data['metadata']['timestamp']}.json"
        with open(json_name, "w") as f:
            json.dump(sweep_data, f, indent=4)
        logging.info(f"Sweep Complete. Saved to {json_name}")

    def _run_freq_sweep(self, freq):
        # Setup physical stimulus
        self.scope.configure_afg(frequency_hz=freq, amplitude_vpp=4.5)
        self.scope.setup_acquisition(freq)

        current_run = {
            "source_waveform": asdict(SourceWaveform(freq, "SQUARE", 4.5)),
            "measurements": []
        }

        for tx_pin, rx_pin in QUICK_TEST_MATRIX:
            # FIXED: Newline and HH:MM:SS timestamps
            logging.info("Measuring TX:{tx_pin} -> RX:{rx_pin}...")

            meas_obj = self.get_measurements(tx_pin, rx_pin)
            trial_measurements = asdict(meas_obj)
            current_run["measurements"].append(trial_measurements)

            logging.info(f"freq {freq}: {trial_measurements}")
            logging.info("Logged.")

        return current_run

            
def main():
    logging.basicConfig(
        format='%(asctime)s [%(levelname)-8s] %(message)s',
        datefmt='%H:%M:%S',
        level=logging.INFO
    )

    if PICO_MODE == 'USB':
        pico_io = PicoUSB(PICO_PORT, PICO_BAUD)
    elif PICO_MODE == 'WIFI':
        pico_io = PicoWiFi(PICO_IP, PICO_PORT_TCP)
    else:
        pico_io = PicoNull()

    runner = Zx50TestRunner(pico_io, SCOPE_ADDR)

    try:
        runner.connect()
        runner.run_sweep()
    except Exception as e:
        logging.error(f"Hardware Error: {e}")
    finally:
        runner.disconnect()


if __name__ == "__main__":
    main()
