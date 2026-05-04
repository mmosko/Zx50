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
CMD_CLK_AUTO_START = 0x12
CMD_CLK_AUTO_STOP = 0x13

SYNC_BYTE = 0x5A
SYNC_NACK = 0x5B


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
            "CLK_START": self._do_clk_start,
            "CLK_STOP": self._do_clk_stop,
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

    def _wait_for_ack_and_data(self, timeout_ms=100, expect_data=False):
        """
        Waits for the PIC's deferred ACK, and optionally the payload byte.
        Returns: True (ACK only), Int (Data Payload), "NACK", or False (Timeout)
        """
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.uart.any():
                resp = self.uart.read(1)[0]

                if resp == SYNC_NACK:
                    return "NACK"

                if resp == SYNC_BYTE:
                    # ACK Received! If this is a WRITE or IO command, we are done.
                    if not expect_data:
                        return True

                    # If this is a READ command, the data byte is right behind it!
                    # Give it a tiny 2ms window to finish arriving at 115200 baud.
                    t1 = time.ticks_ms()
                    while time.ticks_diff(time.ticks_ms(), t1) < 5:
                        if self.uart.any():
                            return self.uart.read(1)[0]
                    return "TIMEOUT"  # Got ACK, but the data payload never arrived!

        return False  # Absolute timeout waiting for ACK

    # ==========================================
    # PRIVATE Z80 COMMANDS
    # ==========================================
    def _mem_read(self, address):
        self._send_packet(CMD_LD, address)
        # We expect a data byte attached to the ACK
        res = self._wait_for_ack_and_data(expect_data=True)
        return "TIMEOUT" if res is False else res

    def _io_read(self, port):
        self._send_packet(CMD_IN, port)
        # We expect a data byte attached to the ACK
        res = self._wait_for_ack_and_data(expect_data=True)
        return "TIMEOUT" if res is False else res

    def _mem_write(self, address, data):
        self._send_packet(CMD_STORE, address, param=data)
        # Write only expects an ACK
        return self._wait_for_ack_and_data(expect_data=False)

    def _io_write(self, port, data):
        self._send_packet(CMD_OUT, port, param=data)
        # Write only expects an ACK
        return self._wait_for_ack_and_data(expect_data=False)

    def _set_ghost_mode(self, enable):
        param = 1 if enable else 0
        self._send_packet(CMD_GHOST, param=param)
        # Ghost mode still sends an immediate ACK, so this works perfectly
        return self._wait_for_ack_and_data(expect_data=False)

    def _mem_ldir(self, address, data_bytes):
        self._send_packet(CMD_LDIR, address, param=len(data_bytes))
        self.uart.write(data_bytes)
        return self._wait_for_ack_and_data(expect_data=False)

    def _step_clock(self, count):
        self._send_packet(CMD_STEP, param=count)
        # Scale timeout based on count since the PIC blocks during stepping
        return self._wait_for_ack_and_data(timeout_ms=100 + (count * 2), expect_data=False)

    # def _bus_snapshot(self):
    #     self._send_packet(CMD_SNAPSHOT)
    #     res = self._wait_for_ack()
    #     if res is True:
    #         data = bytearray()
    #         t0 = time.ticks_ms()
    #         while time.ticks_diff(time.ticks_ms(), t0) < 50:
    #             if self.uart.any():
    #                 data.extend(self.uart.read(self.uart.any()))
    #                 t0 = time.ticks_ms()
    #         return data if data else "TIMEOUT"
    #     return res

    def _start_clock(self):
        self._send_packet(CMD_CLK_AUTO_START)
        return self._wait_for_ack_and_data(expect_data=False)

    def _stop_clock(self):
        self._send_packet(CMD_CLK_AUTO_STOP)
        return self._wait_for_ack_and_data(expect_data=False)

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
            "  pic step [count]         - Single-step the clock (Decimal)\n"
            "  pic clk_start            - Start 1kHz background clock\n"
            "  pic clk_stop             - Stop background clock"
        )

    def _do_ghost(self, args):
        if len(args) == 2:
            enable = args[1] == "1"
            res = self._set_ghost_mode(enable)
            if res is True: return f"OK GHOST {'ENABLE' if enable else 'DISABLE'}"
            if res == "NACK": return "ERR PIC_NACK"
            return "ERR PIC_TIMEOUT"
        return "ERR SYNTAX_PIC_GHOST_1|0"

    def _do_read(self, args):
        if len(args) == 2:
            try:
                addr = int(args[1], 16)
                res = self._mem_read(addr)
                if isinstance(res, int): return f"OK {res:02X}"
                if res == "NACK": return "ERR PIC_NACK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ADDRESS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_READ_<HEX_ADDR>"

    def _do_write(self, args):
        if len(args) == 3:
            try:
                addr = int(args[1], 16)
                data = int(args[2], 16)
                res = self._mem_write(addr, data)
                if res is True: return "OK"
                if res == "NACK": return "ERR PIC_NACK"
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
                res = self._mem_ldir(addr, data_bytes)
                if res is True: return "OK"
                if res == "NACK": return "ERR PIC_NACK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ARGS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_LDIR_<HEX_ADDR>_<HEX_DATA_STRING>"

    def _do_in(self, args):
        if len(args) == 2:
            try:
                port = int(args[1], 16)
                res = self._io_read(port)
                if isinstance(res, int): return f"OK {res:02X}"
                if res == "NACK": return "ERR PIC_NACK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR PORT_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_IN_<HEX_PORT>"

    def _do_out(self, args):
        if len(args) == 3:
            try:
                port = int(args[1], 16)
                data = int(args[2], 16)
                res = self._io_write(port, data)
                if res is True: return "OK"
                if res == "NACK": return "ERR PIC_NACK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ARGS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_OUT_<HEX_PORT>_<HEX_DATA>"

    def _do_step(self, args):
        count = 1
        if len(args) == 2:
            try:
                count = int(args[1])
            except ValueError:
                return "ERR COUNT_MUST_BE_INT"

        res = self._step_clock(count)
        if res is True: return "OK"
        if res == "NACK": return "ERR PIC_NACK"
        return "ERR PIC_TIMEOUT"

    def _do_snapshot(self, args):
        res = self._bus_snapshot()
        if isinstance(res, bytearray):
            hex_str = "".join([f"{b:02X}" for b in res])
            return f"OK {hex_str}"
        if res == "NACK": return "ERR PIC_NACK"
        return "ERR PIC_TIMEOUT"

    def _do_clk_start(self, args):
        res = self._start_clock()
        if res is True: return "OK"
        if res == "NACK": return "ERR PIC_NACK"
        return "ERR PIC_TIMEOUT"

    def _do_clk_stop(self, args):
        res = self._stop_clock()
        if res is True: return "OK"
        if res == "NACK": return "ERR PIC_NACK"
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
