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
CMD_BOOT = 0x14
CMD_STATUS = 0x15

# Async Response Codes
SYNC_OK = 0x5A
SYNC_NACK = 0x5B
RESP_QUEUED = 0x5C
RESP_PENDING = 0x5D
RESP_DONE = 0x5E
RESP_IDLE = 0x5F


class PIC18Link:
    def __init__(self, uart_id=0, tx_gpio=0, rx_gpio=1, baudrate=1000000):
        # Initialize the hardware UART at 1 Mbps
        self.uart = machine.UART(uart_id, baudrate=baudrate,
                                 tx=machine.Pin(tx_gpio), rx=machine.Pin(rx_gpio))
        self.uart.init(bits=8, parity=None, stop=1, timeout=10)

        # Depth-1 Queue Tracking
        # Will hold None, "READ", "WRITE", "IN", or "OUT"
        self.pending_cmd_type = None

        # Dictionary Dispatcher
        self.dispatcher = {
            "GHOST": self._do_ghost,
            "READ": self._do_read,
            "WRITE": self._do_write,
            "IN": self._do_in,
            "OUT": self._do_out,
            "STEP": self._do_step,
            "STATUS": self._do_status,
            "SNAPSHOT": self._do_snapshot,
            "CLK_START": self._do_clk_start,
            "CLK_STOP": self._do_clk_stop,
            "BOOT": self._do_boot,
            "HELP": self._do_help,
            "?": self._do_help
        }

    # ==========================================
    # PRIVATE PRIMITIVES
    # ==========================================
    def _send_packet(self, opcode, address=0x0000, param=0x00):
        addr_h = (address >> 8) & 0xFF
        addr_l = address & 0xFF

        # Flush the input buffer to prevent reading stale data
        while self.uart.any():
            self.uart.read()

        packet = bytearray([SYNC_OK, opcode, addr_h, addr_l, param])
        self.uart.write(packet)

    def _submit_command(self, opcode, address=0x0000, param=0x00, timeout_ms=50):
        """Sends a command and waits for an immediate acknowledgment (SYNC_OK or RESP_QUEUED)."""
        self._send_packet(opcode, address, param)

        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.uart.any():
                resp = self.uart.read(1)[0]
                if resp == SYNC_NACK:
                    return "NACK"
                if resp in (SYNC_OK, RESP_QUEUED):
                    return resp
        return "TIMEOUT"

    def _poll_action(self, opcode, param=0, timeout_ms=100):
        """Used for STEP and STATUS. Waits for the state of the queue and grabs data if DONE."""
        self._send_packet(opcode, param=param)

        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.uart.any():
                resp = self.uart.read(1)[0]

                if resp == RESP_IDLE:
                    return "OK IDLE"

                elif resp == RESP_PENDING:
                    return "OK PENDING"

                elif resp == RESP_DONE:
                    # If the command that just finished was a read, the data byte is right behind it
                    if self.pending_cmd_type in ["READ", "IN"]:
                        t1 = time.ticks_ms()
                        while time.ticks_diff(time.ticks_ms(), t1) < 10:  # 10ms window for the data byte
                            if self.uart.any():
                                data = self.uart.read(1)[0]
                                self.pending_cmd_type = None  # Clear the tracking slot
                                return f"OK DONE {data:02X}"

                        self.pending_cmd_type = None  # Clear it even if we failed, so we don't lock up
                        return "ERR PIC_TIMEOUT_DATA_BYTE_MISSING"

                    else:
                        # Write commands are done, no data to fetch
                        self.pending_cmd_type = None
                        return "OK DONE"

                elif resp == SYNC_NACK:
                    return "ERR PIC_NACK"

        return "ERR PIC_TIMEOUT"

    # ==========================================
    # DISPATCH HANDLERS
    # ==========================================
    def _do_help(self, args):
        return (
            "PIC Subsystem Commands:\n"
            "  pic read <addr>          - Queue memory read (Hex)\n"
            "  pic write <addr> <data>  - Queue memory write (Hex)\n"
            "  pic in <port>            - Queue IO read (Hex)\n"
            "  pic out <port> <data>    - Queue IO write (Hex)\n"
            "  pic status               - Check status of queued command\n"
            "  pic step [count]         - Step the clock and check status\n"
            "  pic snapshot             - Capture full bus state\n"
            "  pic ghost <1|0>          - Enable/Disable bus driving\n"
            "  pic clk_start            - Start 1kHz background clock\n"
            "  pic clk_stop             - Stop background clock\n"
            "  pic boot                 - Perform Z80/CPLD Boot Sequence\n"
            "  pic clear                - Clear the local state machine\n"
        )

    def _do_read(self, args):
        if self.pending_cmd_type is not None: return "ERR BUSY_FINISH_PENDING_CMD_FIRST"
        if len(args) == 2:
            try:
                addr = int(args[1], 16)
                res = self._submit_command(CMD_LD, addr)
                if res == RESP_QUEUED:
                    self.pending_cmd_type = "READ"
                    return "OK QUEUED"
                if res == "NACK": return "ERR PIC_NACK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ADDRESS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_READ_<HEX_ADDR>"

    def _do_write(self, args):
        if self.pending_cmd_type is not None: return "ERR BUSY_FINISH_PENDING_CMD_FIRST"
        if len(args) == 3:
            try:
                addr = int(args[1], 16)
                data = int(args[2], 16)
                res = self._submit_command(CMD_STORE, addr, data)
                if res == RESP_QUEUED:
                    self.pending_cmd_type = "WRITE"
                    return "OK QUEUED"
                if res == "NACK": return "ERR PIC_NACK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ARGS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_WRITE_<HEX_ADDR>_<HEX_DATA>"

    def _do_in(self, args):
        if self.pending_cmd_type is not None: return "ERR BUSY_FINISH_PENDING_CMD_FIRST"
        if len(args) == 2:
            try:
                port = int(args[1], 16)
                res = self._submit_command(CMD_IN, port)
                if res == RESP_QUEUED:
                    self.pending_cmd_type = "IN"
                    return "OK QUEUED"
                if res == "NACK": return "ERR PIC_NACK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR PORT_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_IN_<HEX_PORT>"

    def _do_out(self, args):
        if self.pending_cmd_type is not None: return "ERR BUSY_FINISH_PENDING_CMD_FIRST"
        if len(args) == 3:
            try:
                port = int(args[1], 16)
                data = int(args[2], 16)
                res = self._submit_command(CMD_OUT, port, data)
                if res == RESP_QUEUED:
                    self.pending_cmd_type = "OUT"
                    return "OK QUEUED"
                if res == "NACK": return "ERR PIC_NACK"
                return "ERR PIC_TIMEOUT"
            except ValueError:
                return "ERR ARGS_MUST_BE_HEX"
        return "ERR SYNTAX_PIC_OUT_<HEX_PORT>_<HEX_DATA>"

    def _do_status(self, args):
        return self._poll_action(CMD_STATUS)

    def _do_step(self, args):
        count = 1
        if len(args) == 2:
            try:
                count = int(args[1])
            except ValueError:
                return "ERR COUNT_MUST_BE_INT"

        # Scale the timeout based on how many steps we requested
        return self._poll_action(CMD_STEP, param=count, timeout_ms=100 + (count * 2))

    # --- Immediate / Sync Commands ---

    def _do_ghost(self, args):
        if len(args) == 2:
            enable = args[1] == "1"
            param = 1 if enable else 0
            res = self._submit_command(CMD_GHOST, param=param)
            if res == SYNC_OK: return f"OK GHOST {'ENABLE' if enable else 'DISABLE'}"
            if res == "NACK": return "ERR PIC_NACK"
            return "ERR PIC_TIMEOUT"
        return "ERR SYNTAX_PIC_GHOST_1|0"

    def _do_clk_start(self, args):
        res = self._submit_command(CMD_CLK_AUTO_START)
        if res == SYNC_OK: return "OK"
        if res == "NACK": return "ERR PIC_NACK"
        return "ERR PIC_TIMEOUT"

    def _do_clk_stop(self, args):
        res = self._submit_command(CMD_CLK_AUTO_STOP)
        if res == SYNC_OK: return "OK"
        if res == "NACK": return "ERR PIC_NACK"
        return "ERR PIC_TIMEOUT"

    def _do_boot(self, args):
        res = self._submit_command(CMD_BOOT, timeout_ms=200)  # Give boot extra time
        if res == SYNC_OK: return "OK"
        if res == "NACK": return "ERR PIC_NACK"
        return "ERR PIC_TIMEOUT"

    def _do_snapshot(self, args):
        # Snapshot behaves differently as it dumps a raw stream of bytes
        self._send_packet(CMD_SNAPSHOT)
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 50:
            if self.uart.any():
                resp = self.uart.read(1)[0]
                if resp == SYNC_OK:
                    data = bytearray()
                    t1 = time.ticks_ms()
                    while time.ticks_diff(time.ticks_ms(), t1) < 50:
                        if self.uart.any():
                            data.extend(self.uart.read(self.uart.any()))
                            t1 = time.ticks_ms()
                    hex_str = "".join([f"{b:02X}" for b in data])
                    return f"OK {hex_str}"
                elif resp == SYNC_NACK:
                    return "ERR PIC_NACK"
        return "ERR PIC_TIMEOUT"

    def _do_clear(self, args):
        """Clears the Pico's local queue tracking in case of desync or PIC reboot."""
        self.pending_cmd_type = None

        # Optionally flush the UART RX buffer to clear any garbage
        # that accumulated while the PIC was restarting
        while self.uart.any():
            self.uart.read()

        return "OK LOCAL_STATE_RESET"

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