import select
import sys
import os

import display
from bus import BusController
from pic18_link import PIC18Link

# Define your application version here
APP_VERSION = "RevA-0.1.0"

class Zx50Console:
    """A lightweight line-processing CLI for MicroPython."""

    def __init__(self):
        self.pic = PIC18Link(uart_id=0, tx_gpio=0, rx_gpio=1)
        self.bus = BusController()

        self.poll_obj = select.poll()
        self.poll_obj.register(sys.stdin, select.POLLIN)
        self.prompt = "Zx50> "

    def cmdloop(self):
        """Standard line-processing REPL loop."""

        # Grab the underlying OS build string
        mpy_build = os.uname().version
        board_hw = os.uname().machine

        print("\n==================================================")
        print(f" Zx50 Bus Probe - Interactive Terminal")
        print(f" Firmware: {APP_VERSION}")
        print(f" Hardware: {board_hw}")
        print(f" Core:     MicroPython {mpy_build}")
        print("==================================================")
        print("Type 'help' for a list of commands.\n")

        sys.stdout.write(self.prompt)

        while True:
            # Poll stdin without blocking so we don't freeze the Pico
            poll_res = self.poll_obj.poll(10)

            if poll_res:
                line = sys.stdin.readline().strip()
                if line:
                    self._execute(line)

                # Re-print the prompt after command execution
                sys.stdout.write(self.prompt)

    def _execute(self, line):
        """Uses reflection to route commands to the correct do_method."""
        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        # Handle identifiers that contain special characters directly
        if cmd == "idn?":
            self.do_idn(args)
            return

        # Look for a method named do_<cmd> (e.g., "do_bus" or "do_pic")
        func = getattr(self, f"do_{cmd}", self.default)
        func(args)

    # ==========================================
    # CLI COMMAND DEFINITIONS (Like cmd.Cmd)
    # ==========================================
    def default(self, args):
        print("ERR UNKNOWN_COMMAND. Type 'help' for a list of commands.")

    def do_help(self, args):
        print("Available Subsystems:")
        print("  pic   - Commands for the PIC18F4620 Z80 Controller")
        print("  bus   - Commands for the Multiplexer routing")
        print("  idn?  - Get device identity")
        print("Type 'pic help' or 'bus help' for subsystem commands.")

    def do_idn(self, args):
        print("OK Zx50_PROBE_REVA")

    def do_pic(self, args):
        # If the user just typed "pic", inject "help" so the module prints its menu
        if not args:
            args = ["help"]

        response = self.pic.handle_command(args)
        print(response)

    def do_bus(self, args):
        # If the user just typed "bus", inject "help" so the module prints its menu
        if not args:
            args = ["help"]

        response = self.bus.handle_command(args)
        print(response)

        # Update the physical OLED/LCD if routing changed successfully
        if "OK" in response and args and args[0].upper() in ["SELECT", "GHOST"]:
            display.update("ROUTING ACTIVE", f"TX: {self.bus.current_tx_str}", f"RX: {self.bus.current_rx_str}")


def main():
    # Assumes display.py exists and is working. Comment out if not ready yet!
    display.init()
    display.update("BOOTING...", "Hardware Initialized", "Waiting for Console")

    console = Zx50Console()
    console.cmdloop()


if __name__ == '__main__':
    main()
