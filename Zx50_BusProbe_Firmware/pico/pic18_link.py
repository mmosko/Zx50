import machine
import time

# PIC18F4620 Opcodes
CMD_LD = 0x01
CMD_STORE = 0x02
CMD_IN = 0x03
CMD_OUT = 0x04
CMD_LDIR = 0x05
CMD_SNAPSHOT = 0x07
CMD_GHOST = 0x08
CMD_STEP = 0x11

SYNC_BYTE = 0x5A


class PIC18Link:
    def __init__(self, uart_id=0, tx_gpio=0, rx_gpio=1, baudrate=1000000):
        # Initialize the hardware UART at 1 Mbps
        self.uart = machine.UART(uart_id, baudrate=baudrate,
                                 tx=machine.Pin(tx_gpio), rx=machine.Pin(rx_gpio))
        self.uart.init(bits=8, parity=None, stop=1, timeout=10)

        # Dictionary Dispatcher
        self.dispatcher = {
            "GHOST": self._do_ghost,
            "READ": self._do_read,
            "WRITE": self._do_write,
            "IN": self._do_in,
            "OUT": self._do_out,
            "STEP": self._do_step,
            "LDIR": self._do_ldir,
            "SNAPSHOT": self._do_snapshot,
            "HELP": self._do_help,
            "?": self._do_help
        }

    # ==========================================
    # PRIVATE PRIMITIVES
    # ==========================================
    def _send_packet(self, opcode, address=0x0000, param=0x00):
        addr_h = (address >> 8) & 0xFF
        addr_l = address & 0xFF

        # Flush the input buffer to prevent reading stale ACKs
        while self.uart.any():
            self.uart.read()

        packet = bytearray([SYNC_BYTE, opcode, addr_h, addr_l, param])
        self.uart.write(packet)

    def _wait_for_ack(self, timeout_ms=50):
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.uart.any():
                ack = self.uart.read(1)[0]
                if ack == SYNC_BYTE:
                    return True
        return False

    # ==========================================
    # PRIVATE Z80 COMMANDS
    # ==========================================
    def _set_ghost_mode(self, enable):
        param = 1 if enable else 0
        self._send_packet(CMD_GHOST, param=param)
        return self._wait_for_ack()

    def _mem_read(self, address):
        self._send_packet(CMD_LD, address)
        if self._wait_for_ack():
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < 10:
                if self.uart.any():
                    return self.uart.read(1)[0]
        return None

    def _mem_write(self, address, data):
        self._send_packet(CMD_STORE, address, param=data)
        return self._wait_for_ack()

    def _mem_ldir(self, address, data_bytes):
        self._send_packet(CMD_LDIR, address, param=len(data_bytes))
        self.uart.write(data_bytes)
        return self._wait_for_ack(timeout_ms=150)

    def _io_read(self, port):
        self._send_packet(CMD_IN, port)
        if self._wait_for_ack():
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < 10:
                if self.uart.any():
                    return self.uart.read(1)[0]
        return None

    def _io_write(self, port, data):
        self._send_packet(CMD_OUT, port, param=data)
        return self._wait_for_ack()

    def _step_clock(self):
        self._send_packet(CMD_STEP)
        return self._wait_for_ack()

    def _bus_snapshot(self):
        self._send_packet(CMD_SNAPSHOT)
        data = bytearray()
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 50:
            if self.uart.any():
                data.extend(self.uart.read(self.uart.any()))
                t0 = time.ticks_ms()
        return data if data else None

    # ==========================================
    # DISPATCH HANDLERS
    # ==========================================
    def _do_help(self, args):
        return (
            "PIC Subsystem Commands:\n"
            "  pic read <addr>          - Read memory byte (Hex)\n"
            "  pic write <addr> <data>  - Write memory byte (Hex)\n"
            "  pic in <port>            - Read IO port (Hex)\n"
            "  pic out <port> <data>    - Write IO port (Hex)\n"
            "  pic ldir <addr> <hex>    - Write block of data\n"
            "  pic snapshot             - Capture full bus state\n"
            "  pic ghost <1|0>          - Enable/Disable bus driving\n"
            "  pic step                 - Single-step the clock"
        )

    def _do_ghost(self, args):
        if len(args) == 2:
            enable = args[1] == "1"
            if self._set_ghost_mode(enable):
                return f"OK GHOST {'ENABLE' if enable else 'DISABLE'}"
            return "ERR PIC_TIMEOUT"
        return "ERR SYNTAX_PIC_GHOST_1|0"

    def _do_read(self, args):
        if len(args) == 2:
            try:
                addr = int(args[1], 16)
                val = self._mem_read(addr)
                if val is not None:
                    return f"OK {val:02X}"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ADDRESS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_READ_<HEX_ADDR>"

    def _do_write(self, args):
        if len(args) == 3:
            try:
                addr = int(args[1], 16)
                data = int(args[2], 16)
                if self._mem_write(addr, data):
                    return "OK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ARGS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_WRITE_<HEX_ADDR>_<HEX_DATA>"

    def _do_ldir(self, args):
        if len(args) == 3:
            try:
                addr = int(args[1], 16)
                data_hex = args[2]
                if len(data_hex) % 2 != 0:
                    return "ERR LDIR_DATA_MUST_BE_EVEN_LENGTH"
                data_bytes = bytes.fromhex(data_hex)
                if len(data_bytes) > 255:
                    return "ERR LDIR_MAX_255_BYTES"
                if self._mem_ldir(addr, data_bytes):
                    return "OK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ARGS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_LDIR_<HEX_ADDR>_<HEX_DATA_STRING>"

    def _do_in(self, args):
        if len(args) == 2:
            try:
                port = int(args[1], 16)
                val = self._io_read(port)
                if val is not None:
                    return f"OK {val:02X}"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR PORT_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_IN_<HEX_PORT>"

    def _do_out(self, args):
        if len(args) == 3:
            try:
                port = int(args[1], 16)
                data = int(args[2], 16)
                if self._io_write(port, data):
                    return "OK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ARGS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_OUT_<HEX_PORT>_<HEX_DATA>"

    def _do_step(self, args):
        if self._step_clock():
            return "OK"
        return "ERR PIC_TIMEOUT"

    def _do_snapshot(self, args):
        data = self._bus_snapshot()
        if data is not None:
            hex_str = "".join([f"{b:02X}" for b in data])
            return f"OK {hex_str}"
        return "ERR PIC_TIMEOUT"

    # ==========================================
    # PUBLIC API
    # ==========================================
    def handle_command(self, args):
        """Parses and executes a command destined for the PIC subsystem."""
        if not args:
            return "ERR MISSING_PIC_COMMAND"

        cmd = args[0].upper()
        if cmd in self.dispatcher:
            return self.dispatcher[cmd](args)

        return f"ERR UNKNOWN_PIC_COMMAND_{cmd}"