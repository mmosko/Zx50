# z80_sio_test.py
import time
from z80_async_bus import do_cmd


def run(pic, bus_mgr, output):
    """
    Executes a basic initialization and transmit test for the Z80 SIO on the Zx50 Serial Card.

    Equivalent commands:

        # Setup CTC
        pic out 0080 47
        pic out 0080 30

        # Setup SIO
        pic out 0086 18
        pic out 0086 04
        pic out 0086 44
        pic out 0086 01
        pic out 0086 00
        pic out 0086 03
        pic out 0086 C1
        pic out 0086 05
        pic out 0086 EA

        # Transmit a 'U'
        # you are looking for an "OK DONE 04" or "OK DONE 44" from the IN
        pic in 0086
        pic out 0084 55
    """
    CTC_BASE = 0x80
    SIO_BASE = 0x84

    # CTC Channels
    CTC_CH0 = CTC_BASE + 0
    
    # SIO Channels
    SIO_CH_A_DATA = SIO_BASE + 0
    SIO_CH_A_CTRL = SIO_BASE + 2

    output(">> Z80 Script: Initializing Zx50 Serial Card Test...")

    # Ensure safe starting state
    bus_mgr.ghost_all()
    do_cmd(pic, ["GHOST", "0"], output, raise_on_error=True)
    do_cmd(pic, ["CLK", "SYNC"], output, raise_on_error=True)

    # 1. Initialize CTC Channel 0 (Drives SIO Channel A clock)
    output(">> Configuring CTC Channel 0 for 153.6 kHz (9600 baud * 16)...")

    # Control byte: Int disabled, COUNTER mode, TC follows, Reset, Control
    # Bit 7=0, Bit 6=1 (Counter), Bit 5=0, Bit 4=0, Bit 3=0, Bit 2=1, Bit 1=1, Bit 0=1 -> 0x47
    # do_cmd(pic, ["OUT", f"{CTC_CH0:04X}", "47"], output, raise_on_error=True)

    # Time constant: 48 (0x30 in Hex)
    # The CTC counts the 7.3728 MHz crystal on the TRG0 pin.
    # 7,372,800 Hz / 48 = 153,600 Hz (153.6 kHz)
    # do_cmd(pic, ["OUT", f"{CTC_CH0:04X}", "30"], output, raise_on_error=True)

    # Hack to use the 1 KHz "clk sync" for about a 3 baud connection
    do_cmd(pic, ["OUT", f"{CTC_CH0:04X}", "07"], output, raise_on_error=True)
    do_cmd(pic, ["OUT", f"{CTC_CH0:04X}", "01"], output, raise_on_error=True)

    # 2. Initialize SIO Channel A
    output(">> Configuring SIO Channel A...")
    
    # Reset Channel A (Write to WR0)
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "18"], output, raise_on_error=True)
    
    # WR4: 16x clock, 1 stop bit, no parity
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "04"], output, raise_on_error=True)
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "44"], output, raise_on_error=True)
    
    # WR1: No interrupts
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "01"], output, raise_on_error=True)
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "00"], output, raise_on_error=True)
    
    # WR3: Rx enable, 8 bits/char
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "03"], output, raise_on_error=True)
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "C1"], output, raise_on_error=True)
    
    # WR5: Tx enable, 8 bits/char, DTR, RTS
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "05"], output, raise_on_error=True)
    do_cmd(pic, ["OUT", f"{SIO_CH_A_CTRL:04X}", "EA"], output, raise_on_error=True)

    # 3. Transmit Test Message
    # message = "Hello SIO!\r\n"
    message = "U" * 10000
    output(f">> Transmitting message: {message.strip()}")

    for char in message:
        # Poll SIO RR0 to wait for TX buffer empty (bit 2 = 1)
        # Note: In a real environment, you'd loop until bit 2 is high.
        # Here we can just read it and then write, or poll.
        timeout = 100
        while timeout > 0:
            resp = do_cmd(pic, ["IN", f"{SIO_CH_A_CTRL:04X}"], output=output, raise_on_error=True)
            if resp.startswith("OK"):
                rr0 = int(resp.split()[1], 16)
                if rr0 & 0x04:  # Tx Buffer Empty bit
                    break
            timeout -= 1
            time.sleep(0.01)

        if timeout == 0:
            output(">> ERROR: SIO TX Buffer never became empty!")
            break

        # Write character to SIO Data port
        val = ord(char)
        do_cmd(pic, ["OUT", f"{SIO_CH_A_DATA:04X}", f"{val:02X}"], output=None, raise_on_error=True)

    output(">> Transmit complete. Waiting 1 second...")
    time.sleep(1.0)

    # Shutdown sequence
    do_cmd(pic, ["CLK", "OFF"])
    do_cmd(pic, ["GHOST", "1"])

    output(">> Test Script Completed!")
    return "PASS"
