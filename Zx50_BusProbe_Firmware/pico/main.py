import select
import sys
import os
import time

import display
from bus import BusController
from pic18_link import PIC18Link

# --- CONFIGURATION ---
APP_VERSION = "RevA-0.1.0"
USE_WIFI = True  # Set to False to drop back to purely USB Serial
TCP_PORT = 5050  # Port for the laptop host script to connect to


class Zx50Console:
    """A lightweight line-processing CLI for MicroPython with optional TCP Socket Server."""

    def __init__(self):
        self.pic = PIC18Link(uart_id=0, tx_gpio=0, rx_gpio=1)
        self.bus = BusController()

        self.poll_obj = select.poll()
        self.poll_obj.register(sys.stdin, select.POLLIN)
        self.prompt = "Zx50> "

        # Network state
        self.pico_ip = "127.0.0.1"
        self.server_sock = None
        self.client_sock = None
        self.client_buffer = ""

        if USE_WIFI:
            self._setup_wifi()

    def _get_banner(self):
        """Generates the welcome banner for both USB and TCP clients."""
        mpy_build = os.uname().version
        board_hw = os.uname().machine
        banner = "\n==================================================\n"
        banner += f" Zx50 Bus Probe - Interactive Terminal\n"
        banner += f" Firmware: {APP_VERSION}\n"
        banner += f" Hardware: {board_hw}\n"
        banner += f" Core:     MicroPython {mpy_build}\n"
        if self.server_sock:
            banner += f" Network:  TCP {self.pico_ip}:{TCP_PORT}\n"
        banner += "==================================================\n"
        banner += "Type 'help' for a list of commands.\n"
        return banner

    def _setup_wifi(self):
        """Connects to Wi-Fi and starts a non-blocking TCP server."""
        import network
        import socket
        try:
            import secrets
        except ImportError:
            display.update("NETWORK ERROR", "secrets.py missing!", "Falling back to USB")
            print("ERR: secrets.py not found. Network disabled.")
            return

        display.update("BOOTING...", "Connecting Wi-Fi...", secrets.WIFI['ssid'][:20])

        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(secrets.WIFI['ssid'], secrets.WIFI['password'])

        max_wait = 15
        while max_wait > 0:
            if wlan.status() < 0 or wlan.status() >= 3:
                break
            max_wait -= 1
            time.sleep(1)

        if wlan.status() != 3:
            display.update("NETWORK ERROR", "Failed to connect.", "Check secrets.py")
            print("ERR: Network connection failed.")
            return

        self.pico_ip = wlan.ifconfig()[0]
        print(f"Wi-Fi Connected! IP: {self.pico_ip}")

        # Setup non-blocking TCP Server
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(('', TCP_PORT))
        self.server_sock.listen(1)
        self.server_sock.setblocking(False)

    def _check_tcp_client(self):
        """Non-blocking check for new connections or incoming TCP data."""
        if not self.server_sock:
            return

        # 1. Accept new clients
        if not self.client_sock:
            try:
                self.client_sock, addr = self.server_sock.accept()
                self.client_sock.setblocking(False)
                print(f"\n[TCP Client Connected: {addr[0]}]")
                sys.stdout.write(self.prompt)

                # Push the welcome banner and prompt to the new Wi-Fi client
                welcome_msg = self._get_banner() + "\n" + self.prompt
                self.client_sock.send(welcome_msg.encode('utf-8'))

            except OSError:
                pass  # No new connection

        # 2. Read from existing client
        if self.client_sock:
            try:
                data = self.client_sock.recv(1024)
                if data:
                    self.client_buffer += data.decode('utf-8')
                    # Process lines if they exist
                    if '\n' in self.client_buffer:
                        lines = self.client_buffer.split('\n')
                        for line in lines[:-1]:
                            clean_line = line.strip()
                            if clean_line:
                                self._execute(clean_line, is_tcp=True)

                            # Push the prompt back after executing (or if they just hit Enter)
                            try:
                                self.client_sock.send(self.prompt.encode('utf-8'))
                            except OSError:
                                pass

                        self.client_buffer = lines[-1]
                else:
                    # Empty data means disconnect
                    self.client_sock.close()
                    self.client_sock = None
                    print("\n[TCP Client Disconnected]")
                    sys.stdout.write(self.prompt)
            except OSError:
                pass  # No data ready

    def cmdloop(self):
        """Standard line-processing REPL loop handling both USB and TCP."""

        # Print the banner and prompt locally to the USB serial connection
        sys.stdout.write(self._get_banner() + "\n" + self.prompt)

        # Initial UI update
        comm_mode = f"Wi-Fi: {self.pico_ip}" if self.server_sock else "USB Serial Active"
        display.update("IDLE", comm_mode, f"TX: None  RX: None")

        while True:
            # 1. Check TCP Client (if enabled)
            self._check_tcp_client()

            # 2. Check USB Serial
            poll_res = self.poll_obj.poll(10)
            if poll_res:
                line = sys.stdin.readline().strip()
                if line:
                    self._execute(line, is_tcp=False)
                sys.stdout.write(self.prompt)

    def _send_response(self, response, is_tcp):
        """Routes the output string back to the requestor."""
        # Ensure it always has a newline for parsing
        out_str = response.strip() + "\n"

        # Always echo to USB terminal for debugging
        print(response)

        # If the request came from TCP, send it back over TCP
        if is_tcp and self.client_sock:
            try:
                self.client_sock.send(out_str.encode('utf-8'))
            except OSError:
                pass

    def _execute(self, line, is_tcp=False):
        """Uses reflection to route commands to the correct do_method."""
        parts = line.split()
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        # Handle identifiers that contain special characters directly
        if cmd == "idn?":
            self.do_idn(args, is_tcp)
            return

        # Look for a method named do_<cmd>
        func = getattr(self, f"do_{cmd}", self.default)
        func(args, is_tcp)

    # ==========================================
    # CLI COMMAND DEFINITIONS
    # ==========================================
    def default(self, args, is_tcp):
        self._send_response("ERR UNKNOWN_COMMAND. Type 'help' for a list of commands.", is_tcp)

    def do_help(self, args, is_tcp):
        resp = "Available Subsystems:\n"
        resp += "  pic   - Commands for the PIC18F4620 Z80 Controller\n"
        resp += "  bus   - Commands for the Multiplexer routing\n"
        resp += "  idn?  - Get device identity\n"
        resp += "Type 'pic help' or 'bus help' for subsystem commands."
        self._send_response(resp, is_tcp)

    def do_idn(self, args, is_tcp):
        self._send_response("OK Zx50_PROBE_REVA", is_tcp)

    def do_pic(self, args, is_tcp):
        if not args:
            args = ["help"]
        response = self.pic.handle_command(args)
        self._send_response(response, is_tcp)

    def do_bus(self, args, is_tcp):
        if not args:
            args = ["help"]
        response = self.bus.handle_command(args)
        self._send_response(response, is_tcp)

        # Update the physical OLED/LCD if routing changed successfully
        if "OK" in response and args and args[0].upper() in ["SELECT", "GHOST"]:
            display.update("ROUTING ACTIVE", f"TX: {self.bus.current_tx_str}", f"RX: {self.bus.current_rx_str}")


def main():
    display.init()

    console = Zx50Console()
    console.cmdloop()


if __name__ == '__main__':
    main()