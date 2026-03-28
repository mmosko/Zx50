import pyvisa
import time


class TektronixMDO:
    """
    A PyVISA wrapper class for controlling a Tektronix MDO3034 Oscilloscope.
    Handles LAN connection, AFG configuration, and pulling precision statistical
    measurements (Vpp, Rise, Fall, Phase) via SCPI commands.
    """

    def __init__(self, address):
        self.address = address
        self.rm = pyvisa.ResourceManager('@py')
        self.scope = None

    def connect(self):
        """Establishes the LAN connection and conditions the scope."""
        print(f"Connecting to {self.address}...")
        self.scope = self.rm.open_resource(self.address)
        self.scope.timeout = 5000  # 5s timeout

        idn = self.scope.query("*IDN?").strip()
        print(f"Connected to: {idn}")

        self.scope.write("*CLS")
        self.scope.write("HEADer OFF")

    def disconnect(self):
        """Safely shuts down the AFG and closes the socket."""
        if self.scope:
            self.scope.write("AFG:OUTPUT:STATE OFF")
            self.scope.close()
            print("\nScope disconnected.")

    def match_channels(self):
        """Forces CH1 and CH4 to 1M Ohm, DC Coupled."""
        print("Matching CH1 and CH4 internal configurations (1M Ohm, DC Coupling)...")
        self.scope.write("CH1:COUPling DC")
        self.scope.write("CH4:COUPling DC")
        self.scope.write("CH1:IMPedance MEG")
        self.scope.write("CH4:IMPedance MEG")
        self.scope.write("SELECT:CH1 ON")
        self.scope.write("SELECT:CH4 ON")

    def configure_afg(self, frequency_hz, waveform="SQUARE", amplitude_vpp=3.3):
        """Configures the internal Arbitrary Function Generator."""
        print(f"\n=> Configuring AFG: {frequency_hz / 1e6} MHz {waveform}")
        self.scope.write(f"AFG:FUNCTION {waveform}")
        self.scope.write(f"AFG:FREQUENCY {frequency_hz}")
        self.scope.write(f"AFG:AMPLITUDE {amplitude_vpp}")
        self.scope.write("AFG:OFFSET 1.65")
        self.scope.write("AFG:OUTPUT:STATE ON")
        time.sleep(0.5)

    # --- NEW: Statistical & Hardware Configuration ---

    def configure_acquisition(self, record_length=10000, stat_population=50):
        """
        Upgrades the scope from fast screen-updates to high-fidelity statistical capture.
        """
        print(f"Configuring Acquisition: {record_length} points, N={stat_population} pop.")
        # Increase the horizontal resolution for better timing fidelity
        self.scope.write(f"HORizontal:RECOrdlength {record_length}")

        # Enable statistics and set the population size (N) for Mean/StdDev
        self.scope.write("MEASUrement:STATIstics:MODE ALL")
        self.scope.write(f"MEASUrement:STATIstics:WEIghting {stat_population}")

    def _get_statistical_measurement(self, meas_type, source_ch, target_ch=None, delay_s=0.5):
        """
        A private universal helper that resets the math engine, waits for the
        buffer to fill with N samples, and extracts the Mean and StdDev.
        """
        # Configure the primary source
        self.scope.write(f"MEASUrement:IMMed:SOURce1 {source_ch}")

        # Configure the secondary source (Only needed for Phase/Delay)
        if target_ch:
            self.scope.write(f"MEASUrement:IMMed:SOURce2 {target_ch}")

        self.scope.write(f"MEASUrement:IMMed:TYPE {meas_type}")

        # 1. Clear the old running statistics from the previous pin test
        self.scope.write("MEASUrement:STATIstics:RESet")

        # 2. Give the scope time to physically acquire N new waveforms
        time.sleep(delay_s)

        # 3. Pull the Mean and Standard Deviation
        raw_mean = self.scope.query("MEASUrement:IMMed:MEAN?").strip()
        raw_std = self.scope.query("MEASUrement:IMMed:STDdev?").strip()

        try:
            mean_val = float(raw_mean)
            std_val = float(raw_std)
            # 9.9e37 is Tektronix's NaN (Cannot calculate, e.g. flatline)
            if mean_val >= 9.9e37: return None, None
            return mean_val, std_val
        except ValueError:
            return None, None

    # --- NEW: Specific Metric Extractors ---

    def get_vpp_stats(self, channel):
        """Returns (Mean Vpp, StdDev Vpp)."""
        return self._get_statistical_measurement("PK2pk", channel)

    def get_rise_time_stats(self, channel):
        """Returns (Mean Rise Time, StdDev Rise Time) in seconds."""
        return self._get_statistical_measurement("RISe", channel)

    def get_fall_time_stats(self, channel):
        """Returns (Mean Fall Time, StdDev Fall Time) in seconds."""
        return self._get_statistical_measurement("FALL", channel)

    def get_phase_stats(self, source_ch="CH1", target_ch="CH4"):
        """Returns (Mean Phase, StdDev Phase) in degrees."""
        return self._get_statistical_measurement("PHAse", source_ch, target_ch)

    def get_logic_levels(self, channel):
        """Returns (Mean V_high, StdDev V_high, Mean V_low, StdDev V_low)."""
        high_mean, high_std = self._get_statistical_measurement("HIGH", channel)
        low_mean, low_std = self._get_statistical_measurement("LOW", channel)
        return high_mean, high_std, low_mean, low_std

    def get_overshoot(self, channel):
        """Returns (Mean Pos Overshoot %, StdDev Pos %, Mean Neg %, StdDev Neg %)."""
        pos_mean, pos_std = self._get_statistical_measurement("POVershoot", channel)
        neg_mean, neg_std = self._get_statistical_measurement("NOVershoot", channel)
        return pos_mean, pos_std, neg_mean, neg_std

    def get_pulse_width(self, channel):
        """Returns (Mean Pulse Width, StdDev Pulse Width) in seconds."""
        return self._get_statistical_measurement("PWIdth", channel)
