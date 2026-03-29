import json
import math


def analyze_zx50_data(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)

    print(f"{'Freq (MHz)':<10} | {'RX Pin':<10} | {'Signal':<10} | {'Vpp (mV)':<10} | {'Isolation (dB)':<15}")
    print("-" * 65)

    for run in data['test_runs']:
        freq_mhz = run['source_waveform']['frequency_hz'] / 1e6

        # Find the reference measurement (TX:42 -> RX:42) for this frequency
        ref_vpp = None
        for m in run['measurements']:
            if m['tx_pin'] == 42 and m['rx_pin'] == 42:
                ref_vpp = m['ch4_vpp']['mean']
                break

        for m in run['measurements']:
            vpp = m['ch4_vpp']['mean'] or 0.0

            # Calculate Isolation relative to the source signal
            if ref_vpp and ref_vpp > 0 and m['rx_pin'] != 42:
                isolation = 20 * math.log10(vpp / ref_vpp)
            else:
                isolation = 0.0

            print(
                f"{freq_mhz:<10.1f} | {m['rx_pin']:<10} | {m['rx_signal_name']:<10} | {vpp * 1000:<10.1f} | {isolation:<15.2f}")


if __name__ == "__main__":
    analyze_zx50_data('zx50_sweep_1774768987.json')