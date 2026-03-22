"""
Zx50 Automated Backplane Characterization Runner
------------------------------------------------
This script coordinates a Pi Pico (via USB Serial) and a Tektronix Scope (via LAN).
It sweeps high-frequency signals across the Zx50 backplane to measure Signal Integrity
(Attenuation/Phase Shift) and adjacent-pin Crosstalk (Noise Coupling).
"""

import serial
import time
import csv
from scope_control import TektronixMDO

# --- Hardware Configuration ---
SCOPE_ADDR = 'TCPIP0::172.16.1.43::inst0::INSTR'
PICO_PORT = '/dev/cu.usbmodem1101'  # Update based on OS assignment upon connection
PICO_BAUD = 115200

# --- Test Definitions ---
# If True, only tests the QUICK_TEST_PINS array. Useful for rapid debugging.
ENABLE_QUICK_TEST = True

# Neighborhood test matrix: (TX Pin, RX Pin)
# When TX == RX, we measure Signal Integrity.
# When TX != RX, we measure Crosstalk (bleed to neighboring pins).
QUICK_TEST_MATRIX = [
    # Pin 8 Neighborhood (CLK)
    (8, 8), (8, 6), (8, 7), (8, 9), (8, 10), (8, 11),
    # Pin 10 Neighborhood (MCLK)
    (10, 10), (10, 8), (10, 9), (10, 11), (10, 12), (10, 13)
]

# We test at DC-equivalent (100kHz), mid-band (1MHz), and Z80 high-speed (10MHz)
TEST_FREQS = [100_000, 1_000_000, 10_000_000]


def send_pico_cmd(pico_serial, cmd):
    """
    Sends an ASCII command to the Pi Pico and blocks until an 'OK' or 'ERR' is returned.
    Implements a 2-second timeout to prevent deadlocks if the serial buffer crashes.
    """
    pico_serial.write((cmd + "\n").encode('utf-8'))
    start_time = time.time()

    while time.time() - start_time < 2.0:
        if pico_serial.in_waiting:
            return pico_serial.readline().decode('utf-8').strip()
        time.sleep(0.01)
    return "ERR TIMEOUT"


def main():
    print("--- Zx50 Automated Backplane Characterization ---")

    # 1. Initialize Pico Connection
    try:
        print(f"Opening Serial to Pico on {PICO_PORT}...")
        pico = serial.Serial(PICO_PORT, PICO_BAUD, timeout=1)

        resp = send_pico_cmd(pico, "IDN?")
        if "OK" not in resp:
            print(f"Failed to verify Pico: {resp}")
            return

        # GHOST command safely disables all hardware multiplexers
        send_pico_cmd(pico, "GHOST")
    except Exception as e:
        print(f"Pico Connection Error: {e}")
        return

    # 2. Initialize Scope Connection
    scope = TektronixMDO(SCOPE_ADDR)
    try:
        scope.connect()
        scope.match_channels()
    except Exception as e:
        print(f"Scope Connection Error: {e}")
        pico.close()
        return

    # 3. Setup CSV Logging
    csv_filename = f"zx50_sweep_{int(time.time())}.csv"
    print(f"\nOpening log file: {csv_filename}")

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Headers support both Signal Integrity (TX=RX) and Crosstalk (TX!=RX)
        writer.writerow(["Frequency_Hz", "TX_Pin", "TX_Signal", "RX_Pin", "RX_Signal", "CH1_Vpp", "CH4_Vpp"])

        # 4. Execute Sweep
        for freq in TEST_FREQS:
            print(f"\n=== Testing Frequency: {freq / 1e6} MHz ===")
            scope.configure_afg(frequency_hz=freq)

            # AutoSet frames the waveform so the measurement engine doesn't return NaN
            print("Running Scope AutoSet...")
            scope.scope.write("AUTOSet EXECute")
            time.sleep(6)  # Wait for mechanical relays to settle

            # Iterate through the test matrix
            for tx_pin, rx_pin in QUICK_TEST_MATRIX:
                print(f"  Routing TX:{tx_pin} -> RX:{rx_pin}...", end="", flush=True)

                # Command hardware routing
                tx_resp = send_pico_cmd(pico, f"SELECT TX {tx_pin}")
                rx_resp = send_pico_cmd(pico, f"SELECT RX {rx_pin}")

                if "ERR" in tx_resp or "ERR" in rx_resp:
                    print(f" ROUTING ERROR! TX:{tx_resp} RX:{rx_resp}")
                    continue

                # Extract logical signal names (e.g., from "OK TX 8 CLK")
                tx_sig = tx_resp.split()[3] if len(tx_resp.split()) > 3 else "UNKNOWN"
                rx_sig = rx_resp.split()[3] if len(rx_resp.split()) > 3 else "UNKNOWN"

                # Execute measurements
                ch1_vpp = scope.get_amplitude("CH1")
                ch4_vpp = scope.get_amplitude("CH4")

                # Log raw data to CSV (Math like Phase Shift and Attenuation is handled in Jupyter)
                writer.writerow([freq, tx_pin, tx_sig, rx_pin, rx_sig, ch1_vpp, ch4_vpp])
                print(" Done.")

    # 5. Teardown
    print("\nSweep Complete. Shutting down...")
    send_pico_cmd(pico, "GHOST")  # Isolate test equipment from backplane
    pico.close()
    scope.disconnect()
    print(f"Data saved to {csv_filename}")


if __name__ == "__main__":
    main()