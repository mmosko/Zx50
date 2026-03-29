import pyvisa
import time
from datetime import datetime


class TektronixMDO:
    def __init__(self, address):
        self.address = address
        self.rm = pyvisa.ResourceManager('@py')
        self.scope = None

    def _ts(self):
        return datetime.now().strftime("%H:%M:%S")

    def connect(self):
        print(f"[{self._ts()}] Connecting to {self.address}...")
        self.scope = self.rm.open_resource(self.address)
        self.scope.timeout = 10000
        self.scope.write("*CLS;HEADer OFF")

    def disconnect(self):
        if self.scope:
            try:
                self.scope.write("AFG:OUTPUT:STATE OFF")
                self.scope.close()
            except:
                pass

    def match_channels(self):
        """Hard-locks the scope to the successful 2V/div manual settings."""
        self.scope.write("CH1:IMP MEG;COUP DC;SCA 2.0;OFFS 0.0")
        self.scope.write("CH4:IMP MEG;COUP DC;SCA 2.0;OFFS 0.0")
        self.scope.write("AUTORange:STATE OFF")

    def configure_afg(self, frequency_hz, amplitude_vpp=4.5):
        self.scope.write("AFG:FUNCTION SQUARE")
        self.scope.write(f"AFG:FREQUENCY {frequency_hz}")
        self.scope.write(f"AFG:AMPLITUDE {amplitude_vpp}")
        self.scope.write("AFG:OFFSET 2.25")
        self.scope.write("AFG:OUTPUT:STATE ON")

    def setup_acquisition_manual(self, freq):
        self.match_channels()
        self.scope.write(f"HOR:SCA {0.4 / freq}")
        self.scope.write("TRIG:A:MODe AUTO;EDGE:SOU CH1;LEV:CH1 2.25")
        self.scope.write("ACQ:STATE RUN")
        self.scope.write("MEASU:STATI:RES")

    def configure_acquisition(self, stat_population=50):
        self.scope.write("HOR:RECO 2000")
        slots = [
            (1, "PK2pk", "CH1"), (2, "PK2pk", "CH4"), (3, "PHAse", "CH1", "CH4"),
            (4, "RISe", "CH4"), (5, "FALL", "CH4"), (6, "HIGH", "CH4"),
            (7, "LOW", "CH4"), (8, "PWIdth", "CH4")
        ]
        for s in slots:
            self.scope.write(f"MEASU:MEAS{s[0]}:TYP {s[1]}")
            self.scope.write(f"MEASU:MEAS{s[0]}:SOU1 {s[2]}")
            if len(s) > 3: self.scope.write(f"MEASU:MEAS{s[0]}:SOU2 {s[3]}")
            self.scope.write(f"MEASU:MEAS{s[0]}:STATE ON")
        self.scope.write(f"MEASU:STATI:MODE ALL;WEIG {stat_population}")

    def _wait_for_all_stats(self, target_count=50, timeout=10.0):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                c1 = int(float(self.scope.query("MEASU:MEAS1:COUNt?").strip()))
                c4 = int(float(self.scope.query("MEASU:MEAS4:COUNt?").strip()))
                if c1 >= target_count and c4 >= target_count: return True
            except:
                pass
            time.sleep(0.5)
        return False

    def get_all_measurements(self):
        """Implementing the STOP -> READ -> RUN workflow for consistent data."""
        # 1. Wait for stats to accumulate while running
        self._wait_for_all_stats()

        # 2. STOP acquisition to freeze the values for reading
        self.scope.write("ACQuire:STATE STOP")

        results = []
        # 3. Read each slot INDIVIDUALLY to avoid buffer truncation
        for i in range(1, 9):
            try:
                m = float(self.scope.query(f"MEASU:MEAS{i}:MEAN?").strip())
                s = float(self.scope.query(f"MEASU:MEAS{i}:STDdev?").strip())
                results.append((None, None) if m >= 9.9e37 else (m, s))
            except:
                results.append((None, None))

        # 4. Resume acquisition
        self.scope.write("ACQuire:STATE RUN")
        return results