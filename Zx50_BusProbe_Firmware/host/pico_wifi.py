import socket
import time

from pin_connection import PicoConnection


class PicoWiFi(PicoConnection):
    """TCP (Wi-Fi) implementation of the PicoConnection interface."""

    def __init__(self, ip: str, port: int, timeout: float = 5.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = None

    def connect(self) -> None:
        print(f"Connecting to Pico via Wi-Fi at {self.ip}:{self.port}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.ip, self.port))

        # Eat the welcome banner and wait for the initial 'Zx50>' prompt
        self._wait_for_prompt()

    def disconnect(self) -> None:
        if self.sock:
            try:
                self.send_cmd("bus ghost")  # Updated here
                self.send_cmd("bye")  # 'bye' is at the root level, so it stays as-is
            except:
                pass
            finally:
                self.sock.close()
                self.sock = None

    def _wait_for_prompt(self) -> str:
        """Helper: Reads the TCP stream until 'Zx50>' appears."""
        buffer = ""
        start_time = time.time()

        while "Zx50>" not in buffer:
            # Hard failsafe timeout
            if time.time() - start_time > self.timeout:
                print("  [Warning] Wi-Fi Timeout waiting for Zx50> prompt.")
                break

            try:
                # Receive in small chunks
                chunk = self.sock.recv(1024).decode('utf-8', errors='ignore')
                if not chunk:
                    # Empty byte string means the server closed the connection
                    break
                buffer += chunk
            except socket.timeout:
                print("  [Warning] Socket timeout waiting for data.")
                break
            except OSError as e:
                print(f"  [Warning] Socket error: {e}")
                break

        return buffer

    def send_cmd(self, cmd: str) -> str:
        if not self.sock:
            return "ERR NO_CONNECTION"

        try:
            # Send the command with a standard newline
            full_cmd = f"{cmd}\n".encode('utf-8')
            self.sock.sendall(full_cmd)

            # Read everything the Pico prints until the prompt comes back
            response = self._wait_for_prompt()

            # Sift through the output block to find the exact OK or ERR line
            for line in response.split('\n'):
                clean_line = line.strip()
                if clean_line.startswith("OK") or clean_line.startswith("ERR"):
                    return clean_line

            return "ERR UNKNOWN_RESPONSE"
        except Exception as e:
            return f"ERR SOCKET_EXCEPTION: {e}"