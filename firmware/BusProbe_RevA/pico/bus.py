import machine
from pin_map import BACKPLANE_PINS, MUX_ADDR, LOCAL_GPIO_MAP, REMOTE_GPIO_MAP

class BusController:
    def __init__(self):
        # Initialize MUX GPIOs
        self.rx_pins = {name: machine.Pin(pin_num, machine.Pin.OUT) for name, pin_num in LOCAL_GPIO_MAP.items()}
        self.tx_pins = {name: machine.Pin(pin_num, machine.Pin.OUT) for name, pin_num in REMOTE_GPIO_MAP.items()}

        # State tracking
        self.current_tx_str = "None"
        self.current_rx_str = "None"

        # Start in a safe, isolated state
        self.ghost_all()

    def ghost_all(self):
        """Isolates both the Sender and Receiver cards from the backplane."""
        for i in range(4):
            # 15 (0b1111) is the phantom address that selects nothing
            self.rx_pins[f"CHIP{i}"].value(1)
            self.tx_pins[f"CHIP{i}"].value(1)

        self.current_tx_str = "Isolated"
        self.current_rx_str = "Isolated"

    def _route_signal(self, target_pins, mux_addr, channel):
        """Executes a break-before-make routing sequence."""
        # 1. BREAK: Disable the 74LS154 decoder
        for i in range(4):
            target_pins[f"CHIP{i}"].value(1)
        # 2. SELECT: Set the multiplexer channel
        for i in range(3):
            target_pins[f"PORT{i}"].value((channel >> i) & 1)
        # 3. MAKE: Enable the specific MUX
        for i in range(4):
            target_pins[f"CHIP{i}"].value((mux_addr >> i) & 1)

    def handle_command(self, args):
        """Parses and executes a command destined for the BUS subsystem."""
        if not args:
            return "ERR MISSING_BUS_COMMAND"

        cmd = args[0].upper()

        # Subsystem Help Menu
        if cmd in ["HELP", "?"]:
            return (
                "BUS Subsystem Commands:\n"
                "  bus select <tx|rx> <pin> - Route a backplane pin\n"
                "  bus ghost                - Isolate all multiplexers\n"
                "  bus state                - Show current routing"
            )

        elif cmd == "GHOST":
            self.ghost_all()
            return "OK GHOST MUX_ISOLATED"

        elif cmd == "SELECT":
            if len(args) == 3:
                target = args[1].upper()
                try:
                    pin_num = int(args[2])
                except ValueError:
                    return "ERR PIN_MUST_BE_INTEGER"

                if target not in ["TX", "RX"]:
                    return "ERR INVALID_TARGET_MUST_BE_TX_OR_RX"

                if pin_num not in BACKPLANE_PINS:
                    return f"ERR PIN_{pin_num}_UNMAPPED_OR_POWER"

                # Fetch routing details from pin map
                signal_name = BACKPLANE_PINS[pin_num]["signal"]
                mux_name = BACKPLANE_PINS[pin_num]["mux"]
                mux_addr = MUX_ADDR[mux_name]
                channel = BACKPLANE_PINS[pin_num]["channel"]

                # Execute physical routing
                if target == "TX":
                    self._route_signal(self.tx_pins, mux_addr, channel)
                    self.current_tx_str = f"{pin_num} - {signal_name}"
                else:
                    self._route_signal(self.rx_pins, mux_addr, channel)
                    self.current_rx_str = f"{pin_num} - {signal_name}"

                return f"OK {target} {pin_num} {signal_name}"
            return "ERR SYNTAX_BUS_SELECT_TX|RX_PIN"

        elif cmd == "STATE":
            return f"OK TX:{self.current_tx_str} RX:{self.current_rx_str}"

        return f"ERR UNKNOWN_BUS_COMMAND_{cmd}"