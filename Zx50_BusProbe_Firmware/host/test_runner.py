"""
Zx50 Automated Backplane Characterization Runner
------------------------------------------------
Refactored to use object-oriented measurement classes and Wi-Fi Pico control.
"""

import socket
import time
import csv
import json
from dataclasses import asdict

from dataclasses import dataclass, asdict
from typing import Optional
from scope_control import TektronixMDO

# --- Hardware Configuration ---
SCOPE_ADDR = 'TCPIP0::172.16.1.43::inst0::INSTR'
PICO_IP = '172.16.1.108'
PICO_PORT = 5050

# --- Test Definitions ---
TEST_FREQS = [100_000, 1_000_000, 10_000_000]
# Neighborhood test matrix: (TX Pin, RX Pin)
# Centered around Pin 42 (CLK) with adjacent pins as receivers to measure crosstalk.
QUICK_TEST_MATRIX = [
    (42, 42),  # Primary Signal Integrity (CLK)
    (42, 40),  # Crosstalk to Pin 40 (~HALT~)
    (42, 41),  # Crosstalk to Pin 41
    (42, 43),  # Crosstalk to Pin 43
    (42, 44)   # Crosstalk to Pin 44 (MCLK)
]


# ==========================================
# DATA STRUCTURES
# ==========================================

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
    source: SourceWaveform
    tx_pin: int
    rx_pin: int
    tx_signal_name: str
    rx_signal_name: str

    # Specific metric containers
    ch1_vpp: SignalStats
    ch4_vpp: SignalStats
    phase: SignalStats
    rise_time: SignalStats
    fall_time: SignalStats
    # Add v_high, v_low, overshoot, etc. as you expand scope_control.py


# ==========================================
# RUNNER CLASS
# ==========================================

class Zx50TestRunner:
    def __init__(self, pico_ip, pico_port, scope_addr):
        self.pico_addr = (pico_ip, pico_port)
        self.scope = TektronixMDO(scope_addr)
        self.pico_sock = None
        self.csv_file = None
        self.csv_writer = None

    def connect(self):
        """Initializes LAN connections to both the Scope and the Pico."""
        print(f"Connecting to Pico via TCP {self.pico_addr[0]}:{self.pico_addr[1]}...")
        self.pico_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.pico_sock.settimeout(5.0)  # 5 seconds to allow the banner to arrive
        self.pico_sock.connect(self.pico_addr)

        # Read the buffer until the welcome banner finishes and we see the prompt
        self._wait_for_prompt()

        resp = self.send_pico_cmd("IDN?")
        if "OK" not in resp:
            raise ConnectionError(f"Pico verification failed: {resp}")

        self.scope.connect()
        self.scope.match_channels()

        # Configure scope for 50-sample statistical population
        self.scope.configure_acquisition(record_length=10000, stat_population=50)

    def _wait_for_prompt(self):
        """Helper method: reads the TCP stream until the Zx50> prompt appears."""
        buffer = ""
        while "Zx50>" not in buffer:
            try:
                chunk = self.pico_sock.recv(1024).decode('utf-8')
                if not chunk:
                    break  # Socket was closed
                buffer += chunk
            except socket.timeout:
                print("  [Warning] Timeout waiting for Zx50> prompt.")
                break
        return buffer

    def send_pico_cmd(self, cmd) -> str:
        """Sends a command to the Pico via TCP and reads the complete response."""
        self.pico_sock.sendall((cmd + "\n").encode('utf-8'))

        # Wait for the Pico to finish executing and send the prompt back
        response = self._wait_for_prompt()

        # Parse the block of text for the OK or ERR line
        for line in response.split('\n'):
            clean_line = line.strip()
            if clean_line.startswith("OK") or clean_line.startswith("ERR"):
                return clean_line

        return "ERR UNKNOWN_RESPONSE"

    def disconnect(self):
        """Safely tears down hardware connections."""
        if self.pico_sock:
            try:
                # 1. Safe the hardware
                self.send_pico_cmd("GHOST")

                # 2. Tell the Pico server to cleanly drop our socket
                self.send_pico_cmd("BYE")

            except Exception:
                pass  # Ignore if the socket is already dead
            finally:
                self.pico_sock.close()

        try:
            self.scope.disconnect()
        except Exception:
            pass

    def send_pico_cmd(self, cmd) -> str:
        """Sends a command to the Pico via TCP and reads the response."""
        self.pico_sock.sendall((cmd + "\n").encode('utf-8'))
        try:
            # Read until we get a newline, ignoring the "Zx50> " prompt
            response = self.pico_sock.recv(1024).decode('utf-8')
            for line in response.split('\n'):
                if line.startswith("OK") or line.startswith("ERR"):
                    return line.strip()
            return "ERR UNKNOWN_RESPONSE"
        except socket.timeout:
            return "ERR TIMEOUT"

    def _build_stats(self, raw_tuple) -> SignalStats:
        """
        Helper to convert the raw tuple from scope_control.py into a SignalStats object.
        (Assuming your scope_control returns a tuple: mean, stddev, min, max, count)
        """
        if not raw_tuple or raw_tuple[0] is None:
            return SignalStats()

        # Unpack the tuple based on what scope_control returns
        # Adjust unpacking logic if scope_control only returns (mean, std) for now
        if len(raw_tuple) == 2:
            return SignalStats(mean=raw_tuple[0], stddev=raw_tuple[1])
        else:
            return SignalStats(mean=raw_tuple[0], stddev=raw_tuple[1],
                               min_val=raw_tuple[2], max_val=raw_tuple[3], count=raw_tuple[4])

    def get_measurements(self, tx_pin, rx_pin, freq, amp_vpp=3.3) -> Measurement:
        """
        Routes the hardware, triggers the scope, and constructs a Measurement object.
        """
        # 1. Command Pico Routing
        tx_resp = self.send_pico_cmd(f"SELECT TX {tx_pin}")
        rx_resp = self.send_pico_cmd(f"SELECT RX {rx_pin}")

        if "ERR" in tx_resp or "ERR" in rx_resp:
            print(f"  [!] Routing Error - TX:{tx_resp} RX:{rx_resp}")

        tx_sig = tx_resp.split()[3] if len(tx_resp.split()) > 3 else "UNKNOWN"
        rx_sig = rx_resp.split()[3] if len(rx_resp.split()) > 3 else "UNKNOWN"

        # 2. Extract Data from Scope
        # Note: Depending on your exact scope_control.py implementation, you might
        # need to update the scope methods to query MEAS:IMMed:MINi?, MAXi?, and COUNt?
        ch1_vpp_raw = self.scope.get_vpp_stats("CH1")
        ch4_vpp_raw = self.scope.get_vpp_stats("CH4")
        phase_raw = self.scope.get_phase_stats("CH1", "CH4")
        rise_raw = self.scope.get_rise_time_stats("CH4")
        fall_raw = self.scope.get_fall_time_stats("CH4")

        # 3. Assemble the Object
        source = SourceWaveform(frequency_hz=freq, waveform_type="SQUARE", amplitude_vpp=amp_vpp)

        return Measurement(
            source=source,
            tx_pin=tx_pin,
            rx_pin=rx_pin,
            tx_signal_name=tx_sig,
            rx_signal_name=rx_sig,
            ch1_vpp=self._build_stats(ch1_vpp_raw),
            ch4_vpp=self._build_stats(ch4_vpp_raw),
            phase=self._build_stats(phase_raw),
            rise_time=self._build_stats(rise_raw),
            fall_time=self._build_stats(fall_raw)
        )

    def init_csv(self, filename: str):
        """Creates the CSV file and dynamically generates headers from the dataclasses."""
        self.csv_file = open(filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # Flatten the headers
        headers = ["Freq_Hz", "TX_Pin", "TX_Sig", "RX_Pin", "RX_Sig"]
        metrics = ["CH1_Vpp", "CH4_Vpp", "Phase", "Rise", "Fall"]
        stat_fields = ["Mean", "StdDev", "Min", "Max", "Count"]

        for m in metrics:
            for s in stat_fields:
                headers.append(f"{m}_{s}")

        self.csv_writer.writerow(headers)

    def log_measurements(self, meas: Measurement):
        """Flattens the Measurement object and writes it to the CSV."""
        if not self.csv_writer:
            return

        row = [
            meas.source.frequency_hz, meas.tx_pin, meas.tx_signal_name,
            meas.rx_pin, meas.rx_signal_name
        ]

        # Flatten the SignalStats objects
        stats_objs = [meas.ch1_vpp, meas.ch4_vpp, meas.phase, meas.rise_time, meas.fall_time]
        for stat in stats_objs:
            row.extend([stat.mean, stat.stddev, stat.min_val, stat.max_val, stat.count])

        self.csv_writer.writerow(row)
        self.csv_file.flush()  # Ensure data writes to disk immediately

    def run_sweep(self):
        """The main test execution loop, logging to a structured JSON file."""
        print("\n--- Starting Automatic Sweep ---")

        # 1. Initialize the master dictionary for the JSON file
        sweep_data = {
            "metadata": {
                "timestamp": int(time.time()),
                "scope_addr": self.scope.address,
                "pico_addr": f"{self.pico_addr[0]}:{self.pico_addr[1]}"
            },
            "test_runs": []
        }

        for freq in TEST_FREQS:
            print(f"\n=> Testing Frequency: {freq / 1e6} MHz")

            # Note: I updated amplitude to 4.0 based on your recent 1M Ohm bench test
            self.scope.configure_afg(frequency_hz=freq, amplitude_vpp=4.0)

            print("Running Scope AutoSet (Wait 6s)...")
            self.scope.scope.write("AUTOSet EXECute")
            time.sleep(6)

            # 2. Create a "run block" for this specific source frequency
            current_run = {
                "source_waveform": asdict(SourceWaveform(frequency_hz=freq, waveform_type="SQUARE", amplitude_vpp=4.0)),
                "measurements": []
            }

            for tx_pin, rx_pin in QUICK_TEST_MATRIX:
                print(f"  Measuring TX:{tx_pin} -> RX:{rx_pin}...", end="", flush=True)

                # Fetch the full Measurement dataclass
                meas_obj = self.get_measurements(tx_pin, rx_pin, freq, amp_vpp=4.0)

                # Convert to dict and REMOVE the redundant source data before appending
                meas_dict = asdict(meas_obj)
                del meas_dict['source']

                # Append just the pin routing and stats to this frequency's array
                current_run["measurements"].append(meas_dict)
                print(" Logged.")

            # Add this completed frequency block to the master list
            sweep_data["test_runs"].append(current_run)

        # 3. Dump the entire structured dictionary to a JSON file at the very end
        json_name = f"zx50_sweep_{sweep_data['metadata']['timestamp']}.json"
        with open(json_name, "w") as f:
            json.dump(sweep_data, f, indent=4)

        print(f"\nSweep Complete. Data saved to {json_name}")


def main():
    runner = Zx50TestRunner(PICO_IP, PICO_PORT, SCOPE_ADDR)
    try:
        runner.connect()
        runner.run_sweep()
    except Exception as e:
        print(f"\nHardware Error: {e}")
    finally:
        runner.disconnect()


if __name__ == "__main__":
    main()