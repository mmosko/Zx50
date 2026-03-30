import logging
import time
from dataclasses import dataclass
from typing import Optional

import pyvisa
from pyvisa import VisaIOError

from measurements import SignalStats

@dataclass
class MeasCmdEntry:
    """Used to configure an array of measurements"""
    kind: str
    cmd: str
    channel: int


class TektronixMDO:
    def __init__(self, address):
        self.address = address
        self._rm = pyvisa.ResourceManager('@py')
        self._scope = None

    def connect(self):
        logging.info(f"Connecting to {self.address}...")
        self._scope = self._rm.open_resource(self.address)
        self._scope.timeout = 10000
        self._scope.read_termination = '\n'
        self._write_termination = '\n'
        self._write("*CLS;HEADer OFF")
        logging.info(f"Connected to {self._query('*IDN?')}")

    def disconnect(self):
        if self._scope:
            try:
                logging.info("Disconnecting")
                self._write("AFG:OUTPUT:STATE OFF")
                self._scope.close()
            except:
                pass

    def initialize(self):
        """Initialize scope"""
        logging.info("Initialize scope")
        self._write('*RST')  # Reset
        self._write('*CLS')  # Clear status

        # Set up for optimal data transfer
        self._write('DAT:ENC RIB')  # Binary encoding
        self._write('DAT:WID 2')  # 16-bit data
        self._write('VERB OFF')

        self._write('ACQuire:STATE OFF')
        self._write("AUTORange:STATE OFF")
        self._setup_channels()
        # Wait for scope to complete

    def configure_afg(self, frequency_hz, amplitude_vpp=4.75):
        logging.info(f"Configure AFG {frequency_hz} Hz {amplitude_vpp} Vpp")

        try:
            self._write("AFG:OUTPut:LOAd:IMPEDance HIGHZ")
            self._write("AFG:FUNCTION SQUARE")
            self._write(f"AFG:FREQUENCY {frequency_hz}")
            self._write(f"AFG:AMPLITUDE {amplitude_vpp}")
            self._write(f"AFG:OFFSET 2.5")
            # self._write("AFG:LEVELPreset CMOS_5_0V")
            self._write("AFG:STATE ON")
            self._write("AFG:OUTPut:STATE ON")
            afg_state = self._query("AFG:OUTPut:STATE?")
            logging.info(f"AFG STATE: {afg_state}")
        except VisaIOError as e:
            # The error details are in the exception object 'e'
            logging.error(f"A PyVISA error occurred: {e.args[0]}")
            logging.error(f"The specific VISA error code is: {e.error_code}")
        except Exception as e:
            # Handle other potential exceptions
            logging.error(f"An unexpected error occurred: {e}")

    def get_all_measurements(self, stat_population=100):
        """Full suite for Signal Integrity (TX == RX)."""
        return self._measure_parameters(self._get_full_metric_list(), stat_population)

    def get_crosstalk_measurements(self, stat_population=100):
        """Lite suite for Crosstalk (TX != RX) - Peak-to-Peak only."""
        metrics = [
            MeasCmdEntry('pk2pk', 'TYP PK2Pk;SOURCE1 CH1', 1),
            MeasCmdEntry('pk2pk', 'TYP PK2Pk;SOURCE1 CH4', 4),
        ]
        return self._measure_parameters(metrics, stat_population)

    def _get_full_metric_list(self):
        """Standard metrics for driven pins."""
        return [
            MeasCmdEntry('pk2pk', 'TYP PK2Pk;SOURCE1 CH1', 1),
            MeasCmdEntry('pk2pk', 'TYP PK2Pk;SOURCE1 CH4', 4),
            MeasCmdEntry('rise', 'TYP RISE;SOURCE1 CH4', 4),
            MeasCmdEntry('fall', 'TYP FALL;SOURCE1 CH4', 4),
            MeasCmdEntry('phase', 'TYP PHASE;SOURCE1 CH1; SOURCE2 CH4', 4),
            MeasCmdEntry('vhigh', 'TYP HIGH;SOURCE1 CH4', 4),
            MeasCmdEntry('vlow', 'TYP LOW;SOURCE1 CH4', 4),
            MeasCmdEntry('pov', 'TYP POVershoot;SOURCE1 CH4', 4),
            MeasCmdEntry('nov', 'TYP NOVershoot;SOURCE1 CH4', 4),
            MeasCmdEntry('pwid', 'TYP PWID;SOURCE1 CH4', 4),
        ]

    def setup_acquisition(self, freq):
        logging.debug(f"Setup Acquisition {freq} Hz")
        self._write(f"HOR:SCA {0.4 / freq}")
        # self._write('ACQ:MODE SAM')  # Sample mode
        # self._write('ACQ:STOPA SEQ')  # Single sequen
        # self._write("ACQ:STATE RUN")
        # self._write("MEASU:STATI:RES")
        self._setup_trigger()

    # === Private Methods

    def _setup_channels(self):
        self._write(f'SEL:CH1 ON')
        self._write(f'SEL:CH2 OFF')
        self._write(f'SEL:CH3 OFF')
        self._write(f'SEL:CH4 ON')
        self._write("CH1:IMP MEG;COUP DC;SCA 2.0;OFFS 0.0; POS 0.0")
        self._write("CH4:IMP MEG;COUP DC;SCA 2.0;OFFS 0.0; POS -3.0")

    def _measure_parameters(self, meas_commands, stat_population=50):
        """Generalized measurement runner using provided command list."""
        results = {}

        # Measure each parameter
        for chunk in _chunk_list(meas_commands, 4):
            self._write("HOR:RECO 2000")
            self._write(f"MEASU:STATI:WEIG {stat_population}")
            self._write("MEASUrement:GAT FULLRECORD")

            self._write("ACQUIRE:STATE STOP")
            self._write("MEASU:CLEAR ALL")
            for idx, entry in enumerate(chunk):
                logging.debug(f"idx {idx} param {entry.kind} cmd {entry.cmd}")
                # Reset stats
                self._write(f"MEASU:MEAS{idx + 1}:STATE ON")
                self._write(f"MEASU:MEAS{idx + 1}:STATS RESET")
                self._write(f"MEASU:MEAS{idx + 1}:{entry.cmd}")

            self._write("MEASU:STATI:MODE ALL")
            self._write("MEASU:STATS:STATE ON")
            self._write("MEASU:STATI RES")
            self._write("ACQUIRE:STATE RUN")

            # Need to pause here to give the stats buffer time to clear
            time.sleep(2)

            self._wait_for_all_stats(channel=1, target_count=stat_population)

            for idx, entry in enumerate(chunk):
                m = float(self._query(f"MEASU:MEAS{idx + 1}:MEAN?").strip())
                s = float(self._query(f"MEASU:MEAS{idx + 1}:STDdev?").strip())
                mn = float(self._query(f"MEASU:MEAS{idx + 1}:MINI?").strip())
                mx = float(self._query(f"MEASU:MEAS{idx + 1}:MAX?").strip())
                units = self._query(f"MEASU:MEAS{idx + 1}:UNITS?").strip().strip('\"')
                self._write(f"MEASU:MEAS{idx + 1}:STATE OFF")
                stats = SignalStats(count=stat_population, units=units, mean=m, stddev=s, min_val=mn,max_val=mx) if m < 9.9e37 else SignalStats()
                logging.info(f'measurement {entry.kind} ch {entry.channel} stats {stats}')
                results[(entry.kind, entry.channel)] = stats

            self._write("ACQUIRE:STATE STOP")
            self._write("MEASU:STATS:STATE OFF")
            self._write("MEASU:STATI:MODE OFF")
        return results

    def _setup_trigger(self, channel=1, level=0.0, edge='RISE'):
        """Configure trigger"""
        try:
            self._write(f'TRIGger:A:EDGE:SOUrce CH{channel}')  # Edge trigger
            self._write(f'TRIG:A:EDGE:SOU CH{channel}')
            self._write(f'TRIGger:A:LEVel:CH{channel} TTL')
            self._write(f'TRIG:A:EDGE:SLO {edge}')
        except Exception as e:
            logging.error(e)

    def _wait_for_all_stats(self, channel, target_count=50, timeout=60.0):
        start_time = time.time()
        next_progress = 25
        while time.time() - start_time < timeout:
            try:
                raw_count = self._query(f"MEASU:MEAS{channel}:COUNt?")
                c = int(float(raw_count.strip()))
                if c >= target_count:
                    return True
                else:
                    if c > next_progress:
                        logging.info(f"ch {channel} count {c}, waiting for {target_count}")
                        next_progress = c + 25
            except:
                pass
            time.sleep(1.0)
        logging.error(f"Timed out waiting for {target_count} samples")
        return False

    def _write(self, message):
        logging.debug(f"[TX] => {message}")
        self._scope.write(f"{message}")
        result = self._query("*OPC?")
        if result != "1":
            logging.error("Scope did not return status 1 for OPC")

    def _query(self, query) -> str:
        logging.debug(f"[TX] => {query}")
        result = self._scope.query(query)
        logging.debug(f"[RX] <= {result}")
        return result


def _chunk_list(data, size):
    it = iter(data)
    for _ in range(0, len(data), size):
        # Create a dictionary from the next 'size' items
        yield [v for v in [next(it) for _ in range(min(size, len(data) - _))]]
