import serial
import time

from pin_connection import PicoConnection


class PicoUSB(PicoConnection):
    """Serial (USB) implementation of the PicoConnection interface."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None

    def connect(self) -> None:
        print(f"Connecting to Pico via USB on {self.port}...")
        self.serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)

        # 1. Purge any garbage data left in the OS serial buffers
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

        # 2. Send a blank carriage return to force the Pico to print a fresh prompt
        self.serial.write(b"\r\n")
        self._wait_for_prompt()

    def disconnect(self) -> None:
        if self.serial and self.serial.is_open:
            try:
                self.send_cmd("bus ghost")  # Updated here
            except:
                pass
            self.serial.close()

    def _wait_for_prompt(self) -> str:
        """Helper: Reads the serial stream until 'Zx50>' appears or it times out."""
        buffer = ""
        start_time = time.time()

        while "Zx50>" not in buffer:
            # Hard timeout catch to prevent infinite hanging
            if time.time() - start_time > self.timeout:
                print("  [Warning] USB Timeout waiting for Zx50> prompt.")
                break

            if self.serial.in_waiting > 0:
                # Use errors='ignore' so a random scrambled byte doesn't crash the script
                chunk = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                buffer += chunk
            else:
                time.sleep(0.01)  # Sleep 10ms to prevent pegging the CPU at 100%

        return buffer

    def send_cmd(self, cmd: str) -> str:
        if not self.serial or not self.serial.is_open:
            return "ERR NO_CONNECTION"

        # 1. THE FIX: Nuke any leftover 'Zx50>' prompts from the previous command
        self.serial.reset_input_buffer()

        # 2. THE FIX: Use only \r (MicroPython's preferred execute char)
        full_cmd = f"{cmd}\r".encode('utf-8')

        print(f"    [TX] -> {cmd}")  # X-RAY Vision
        self.serial.write(full_cmd)
        self.serial.flush()

        # Read everything the Pico prints until the prompt comes back
        response = self._wait_for_prompt()

        # X-RAY Vision: Print exactly what the Pico sent back (stripping newlines for readability)
        print(f"    [RX] <- {repr(response)}")

        # Sift through the output block to find the exact OK or ERR line
        for line in response.split('\n'):
            clean_line = line.strip()
            if clean_line.startswith("OK") or clean_line.startswith("ERR"):
                return clean_line

        return "ERR UNKNOWN_RESPONSE"