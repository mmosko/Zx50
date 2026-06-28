import machine
import time

# ==========================================
# STRING CONSTANTS FOR CLI & SCRIPTS
# ==========================================
# Success Responses
RES_OK = "OK"
RES_OK_QUEUED = "OK QUEUED"
RES_OK_PENDING = "OK PENDING"
RES_OK_DONE = "OK DONE"  # Note: Data byte will be appended, e.g., "OK DONE 42"
RES_OK_IDLE = "OK IDLE"

# Error Responses
ERR_NACK = "ERR PIC_NACK"
ERR_TIMEOUT = "ERR PIC_TIMEOUT"
ERR_TIMEOUT_DATA = "ERR PIC_TIMEOUT_DATA_BYTE_MISSING"
ERR_BUSY = "ERR BUSY_FINISH_PENDING_CMD_FIRST"
ERR_ADDR_HEX = "ERR ADDRESS_MUST_BE_HEX"
ERR_ARGS_HEX = "ERR ARGS_MUST_BE_HEX"
ERR_PORT_HEX = "ERR PORT_MUST_BE_HEX"
ERR_COUNT_INT = "ERR COUNT_MUST_BE_INT"
ERR_MISSING_CMD = "ERR MISSING_PIC_COMMAND"
ERR_UNKNOWN_CMD = "ERR UNKNOWN_PIC_COMMAND"

# ==========================================
# PIC18F27Q43 Opcodes
# These are the serial protocol bytes
# ==========================================
CMD_LD = 0x01
CMD_STORE = 0x02
CMD_IN = 0x03
CMD_OUT = 0x04
CMD_LDIR = 0x05
CMD_SNAPSHOT = 0x07
CMD_GHOST = 0x08
CMD_STEP = 0x11
CMD_BOOT = 0x14
CMD_STATUS = 0x15

# Simplified Clock Commands
CMD_CLK_AUTO = 0x20
CMD_CLK_SYNC = 0x21
CMD_CLK_OFF = 0x22

# Async Response Codes
RESP_ASYNC_DONE = 0x59  # Gratuitous async completion push
SYNC_OK = 0x5A
SYNC_NACK = 0x5B
RESP_QUEUED = 0x5C
RESP_PENDING = 0x5D
RESP_DONE = 0x5E  # Polled completion
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
            "CLK": self._do_clk,
            "BOOT": self._do_boot,
            "CLEAR": self._do_clear,
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
                    return ERR_NACK
                if resp in (SYNC_OK, RESP_QUEUED):
                    return resp
        return ERR_TIMEOUT

    def _fetch_payload(self):
        """Helper to extract the data byte if the completed command was a READ/IN."""
        if self.pending_cmd_type in ["READ", "IN"]:
            t1 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t1) < 10:  # 10ms window for the data byte
                if self.uart.any():
                    data = self.uart.read(1)[0]
                    self.pending_cmd_type = None  # Clear the tracking slot
                    return f"{RES_OK_DONE} {data:02X}"

            self.pending_cmd_type = None  # Clear it even if we failed to prevent lockup
            return ERR_TIMEOUT_DATA
        else:
            # Write commands are done, no data to fetch
            self.pending_cmd_type = None
            return RES_OK_DONE

    def _poll_action(self, opcode, param=0, timeout_ms=100):
        """Used for STEP and STATUS. Checks for gratuitous completion, then polls if needed."""

        # 1. Catch gratuitous async byte BEFORE sending a new poll command to avoid a race condition
        while self.uart.any():
            resp = self.uart.read(1)[0]
            if resp == RESP_ASYNC_DONE:
                return self._fetch_payload()

        # 2. If nothing is in the buffer, actively ask the PIC
        self._send_packet(opcode, param=param)

        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.uart.any():
                resp = self.uart.read(1)[0]

                if resp == RESP_IDLE:
                    return RES_OK_IDLE

                elif resp == RESP_PENDING:
                    return RES_OK_PENDING

                elif resp in (RESP_DONE, RESP_ASYNC_DONE):
                    return self._fetch_payload()

                elif resp == SYNC_NACK:
                    return ERR_NACK

        return ERR_TIMEOUT

    # ==========================================
    # PUBLIC ASYNC HANDLER
    # ==========================================
    def wait_for_completion(self, timeout_ms=1000):
        """Passively blocks for RESP_ASYNC_DONE, falling back to a STATUS poll if needed."""
        t0 = time.ticks_ms()

        # Phase 1: Passive Listening
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.uart.any():
                resp = self.uart.read(1)[0]
                if resp in (RESP_ASYNC_DONE, RESP_DONE):
                    return self._fetch_payload()
                elif resp == RESP_IDLE:
                    self.pending_cmd_type = None
                    return RES_OK_IDLE

            # Brief yield to prevent pegging the Pico CPU
            time.sleep(0.001)

            # Phase 2: Active Fallback (The PIC missed the push or we timed out waiting passively)
        return self._poll_action(CMD_STATUS)

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
            "  pic clk auto             - Start PWM free-run clock\n"
            "  pic clk sync             - Start synchronized lock-step clock\n"
            "  pic clk off              - Turn off clock generation\n"
            "  pic boot                 - Perform Z80/CPLD Boot Sequence\n"
            "  pic clear                - Clear the local state machine\n"
        )

    def _do_read(self, args):
        if self.pending_cmd_type is not None:
            return ERR_BUSY
        if len(args) == 2:
            try:
                addr = int(args[1], 16)
                res = self._submit_command(CMD_LD, addr)
                if res == RESP_QUEUED:
                    self.pending_cmd_type = "READ"
                    return RES_OK_QUEUED
                if res == "NACK":
                    return ERR_NACK
                return ERR_TIMEOUT
            except ValueError:
                return ERR_ADDR_HEX
        return ERR_ADDR_HEX

    def _do_write(self, args):
        if self.pending_cmd_type is not None:
            return ERR_BUSY

        if len(args) == 3:
            try:
                addr = int(args[1], 16)
                data = int(args[2], 16)
                res = self._submit_command(CMD_STORE, addr, data)
                if res == RESP_QUEUED:
                    self.pending_cmd_type = "WRITE"
                    return RES_OK_QUEUED
                if res == "NACK":
                    return ERR_NACK
                return ERR_TIMEOUT
            except ValueError:
                return ERR_ARGS_HEX
        return ERR_ARGS_HEX

    def _do_in(self, args):
        if self.pending_cmd_type is not None:
            return ERR_BUSY
        if len(args) == 2:
            try:
                port = int(args[1], 16)
                res = self._submit_command(CMD_IN, port)
                if res == RESP_QUEUED:
                    self.pending_cmd_type = "IN"
                    return RES_OK_QUEUED
                if res == "NACK":
                    return ERR_NACK
                return ERR_TIMEOUT
            except ValueError:
                return ERR_PORT_HEX
        return ERR_ARGS_HEX

    def _do_out(self, args):
        if self.pending_cmd_type is not None:
            return ERR_BUSY
        if len(args) == 3:
            try:
                port = int(args[1], 16)
                data = int(args[2], 16)
                res = self._submit_command(CMD_OUT, port, data)
                if res == RESP_QUEUED:
                    self.pending_cmd_type = "OUT"
                    return RES_OK_QUEUED
                if res == "NACK":
                    return ERR_NACK
                return ERR_TIMEOUT
            except ValueError:
                return ERR_ARGS_HEX
        return ERR_ARGS_HEX

    def _do_status(self, args):
        return self._poll_action(CMD_STATUS)

    def _do_step(self, args):
        count = 1
        if len(args) == 2:
            try:
                count = int(args[1])
            except ValueError:
                return ERR_COUNT_INT

        # Scale the timeout based on how many steps we requested
        return self._poll_action(CMD_STEP, param=count, timeout_ms=100 + (count * 2))

    # --- Immediate / Sync Commands ---

    def _do_ghost(self, args):
        if len(args) == 2:
            enable = args[1] == "1"
            param = 1 if enable else 0
            res = self._submit_command(CMD_GHOST, param=param)
            if res == SYNC_OK:
                return f"{RES_OK} GHOST {'ENABLE' if enable else 'DISABLE'}"
            if res == "NACK":
                return ERR_NACK
            return ERR_TIMEOUT
        return ERR_MISSING_CMD

    def _do_clk(self, args):
        if len(args) == 2:
            subcmd = args[1].upper()
            if subcmd == "AUTO":
                res = self._submit_command(CMD_CLK_AUTO)
            elif subcmd == "SYNC":
                res = self._submit_command(CMD_CLK_SYNC)
            elif subcmd == "OFF":
                res = self._submit_command(CMD_CLK_OFF)
            else:
                return ERR_UNKNOWN_CMD

            if res == SYNC_OK:
                return RES_OK
            if res == "NACK":
                return ERR_NACK
            return ERR_TIMEOUT

        return ERR_MISSING_CMD

    def _do_boot(self, args):
        res = self._submit_command(CMD_BOOT, timeout_ms=200)  # Give boot extra time
        if res == SYNC_OK:
            return RES_OK
        if res == "NACK":
            return ERR_NACK
        return ERR_TIMEOUT

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
                    return f"{RES_OK} {hex_str}"
                elif resp == SYNC_NACK:
                    return ERR_NACK
        return ERR_TIMEOUT

    def _do_clear(self, args):
        """Clears the Pico's local queue tracking in case of desync or PIC reboot."""
        self.pending_cmd_type = None

        # Optionally flush the UART RX buffer to clear any garbage
        # that accumulated while the PIC was restarting
        while self.uart.any():
            self.uart.read()

        return f"{RES_OK} LOCAL_STATE_RESET"

    # ==========================================
    # PUBLIC API
    # ==========================================
    def handle_command(self, args):
        """Parses and executes a command destined for the PIC subsystem."""
        if not args:
            return ERR_MISSING_CMD

        cmd = args[0].upper()
        if cmd in self.dispatcher:
            return self.dispatcher[cmd](args)

        return f"{ERR_UNKNOWN_CMD} {cmd}"
