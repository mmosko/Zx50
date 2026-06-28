# z80_lcd_test.py

# Test writing to the Front Panel's LCD via OTIR

import time
from z80_async_bus import do_cmd


def run(pic, bus_mgr, output):
    """
    Blasts a text payload to the Raspberry Pi Pico Front Panel controller.
    """
    # 0x0050 -> Upper address is 0x00 (B-Reg = 0), Lower is 0x50 (Port = 0x50)
    PICO_PORT = 0x0050

    output(">> Taking control of bus...")
    bus_mgr.ghost_all()
    do_cmd(pic, ["GHOST", "0"], output, raise_on_error=True)

    # We must use AUTO clock so the Pico sees valid, continuous T-States
    do_cmd(pic, ["CLK", "SYNC"], output, raise_on_error=True)

    # The \n character will move the text to the next line on the LCD
    message = "Zx50 Front Panel\nZ80 CPU Alive!\n\nHello World."
    output(f">> Sending payload to LCD...")

    # 1. Send the 0x01 Command Byte (Clear LCD & Start Text)
    do_cmd(pic, ["OUT", f"{PICO_PORT:04X}", "01"], output=None, raise_on_error=True)

    # 2. Blast the ASCII characters as fast as Python and USB allow
    for char in message:
        val = ord(char)
        do_cmd(pic, ["OUT", f"{PICO_PORT:04X}", f"{val:02X}"], output=None, raise_on_error=True, timeout=1000000)

    output(">> Transfer complete. Releasing bus...")
    do_cmd(pic, ["CLK", "OFF"])
    do_cmd(pic, ["GHOST", "1"])

    return "PASS"