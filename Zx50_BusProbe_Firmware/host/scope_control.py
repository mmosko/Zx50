import pyvisa
import time


class TektronixMDO:
    """
    A PyVISA wrapper class for controlling a Tektronix MDO3034 Oscilloscope.
    Handles LAN connection, AFG (Arbitrary Function Generator) configuration,
    and pulling precision measurements via SCPI commands.
    """

    def __init__(self, address):
        self.address = address
        # '@py' forces PyVISA to use the pyvisa-py pure Python backend
        # instead of looking for National Instruments drivers on macOS/Linux.
        self.rm = pyvisa.ResourceManager('@py')
        self.scope = None

    def connect(self):
        """Establishes the LAN connection and conditions the scope for data extraction."""
        print(f"Connecting to {self.address}...")
        self.scope = self.rm.open_resource(self.address)
        self.scope.timeout = 5000  # 5000ms (5s) timeout for blocking operations

        # Verify connection and print scope model/firmware
        idn = self.scope.query("*IDN?").strip()
        print(f"Connected to: {idn}")

        # *CLS clears any pending internal errors or measurement queues
        self.scope.write("*CLS")

        # CRITICAL: Forces the scope to stop prepending "MEASUREMENT:IMMED:VALUE"
        # to its responses so Python can natively parse the floating-point numbers.
        self.scope.write("HEADer OFF")

    def disconnect(self):
        """Safely shuts down the AFG and closes the socket."""
        if self.scope:
            self.scope.write("AFG:OUTPUT:STATE OFF")
            self.scope.close()
            print("\nScope disconnected.")

    def match_channels(self):
        """
        Forces CH1 and CH4 to identical 1M Ohm, DC Coupled configurations.
        If left at 50/75 Ohm termination, the scope acts as a heavy voltage divider,
        artificially crushing the signal amplitude and ruining the attenuation math.
        """
        print("Matching CH1 and CH4 internal configurations (1M Ohm, DC Coupling)...")
        self.scope.write("CH1:COUPling DC")
        self.scope.write("CH4:COUPling DC")

        # Set both to 1 MegaOhm (MEG) input impedance
        self.scope.write("CH1:IMPedance MEG")
        self.scope.write("CH4:IMPedance MEG")

        # Ensure traces are visible on screen
        self.scope.write("SELECT:CH1 ON")
        self.scope.write("SELECT:CH4 ON")

    def configure_afg(self, frequency_hz, waveform="SQUARE", amplitude_vpp=3.3):
        """
        Configures the scope's internal Arbitrary Function Generator.
        Defaults to a 3.3Vpp Square wave to simulate digital TTL logic.
        """
        print(f"\n=> Configuring AFG: {frequency_hz / 1e6} MHz {waveform}")
        self.scope.write(f"AFG:FUNCTION {waveform}")
        self.scope.write(f"AFG:FREQUENCY {frequency_hz}")
        self.scope.write(f"AFG:AMPLITUDE {amplitude_vpp}")
        self.scope.write("AFG:OFFSET 1.65")  # Centers a 3.3Vpp wave between 0V and 3.3V
        self.scope.write("AFG:OUTPUT:STATE ON")
        time.sleep(0.5)  # Give the internal AFG relays time to settle

    def get_amplitude(self, channel):
        """
        Commands the scope's immediate measurement engine to calculate Peak-to-Peak voltage.
        Returns a float, or None if the scope cannot calculate it (e.g., no signal).
        """
        self.scope.write(f"MEASUrement:IMMed:SOURce1 {channel}")
        self.scope.write("MEASUrement:IMMed:TYPE PK2pk")
        time.sleep(0.5)  # Wait for the scope to capture enough waveform data

        raw_val = self.scope.query("MEASUrement:IMMed:VALue?").strip()
        try:
            val = float(raw_val)
            # Tektronix returns 9.9e37 (NaN) if it fails to calculate a value
            if val >= 9.9e37: return None
            return val
        except ValueError:
            return None

    def get_phase_delay(self, source_ch="CH1", target_ch="CH4"):
        """
        Measures the phase shift in degrees between two channels.
        Used to detect severe inductance or capacitance on the backplane traces.
        """
        self.scope.write(f"MEASUrement:IMMed:SOURce1 {source_ch}")
        self.scope.write(f"MEASUrement:IMMed:SOURce2 {target_ch}")
        self.scope.write("MEASUrement:IMMed:TYPE PHAse")
        time.sleep(0.5)

        raw_val = self.scope.query("MEASUrement:IMMed:VALue?").strip()
        try:
            val = float(raw_val)
            if val >= 9.9e37: return None
            return val
        except ValueError:
            return None