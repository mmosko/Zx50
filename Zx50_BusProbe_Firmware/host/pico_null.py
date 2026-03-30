import serial
import time

from pin_connection import PicoConnection


class PicoNull(PicoConnection):
    """No pico control, manually set"""

    def __init__(self):
        pass

    def connect(self) -> None:
        pass

    def _wait_for_prompt(self, timeout_override: float = None) -> str:
        return "OK"

    def disconnect(self) -> None:
        pass

    def send_cmd(self, cmd: str) -> str:
        # Just call everything CLK
        return "OK x x CLK"
