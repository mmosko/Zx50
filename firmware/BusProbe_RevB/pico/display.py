import machine
import time

# Hardware configuration
CS_PIN = 17
RST_PIN = 20
SCK_PIN = 18
MOSI_PIN = 19

# Initialize pins
lcd_cs = machine.Pin(CS_PIN, machine.Pin.OUT)
lcd_rst = machine.Pin(RST_PIN, machine.Pin.OUT)

# Active LOW Chip Select, idle HIGH
lcd_cs.value(1)

# SPI0 at 500kHz. Polarity 1, Phase 1 (Clock idles high, samples on rising edge)
spi = machine.SPI(0, baudrate=500000, sck=machine.Pin(SCK_PIN), mosi=machine.Pin(MOSI_PIN), polarity=1, phase=1)

# Pre-computed lookup table to instantly reverse the bits of any byte (0-255)
# This perfectly emulates LSB-first transmission over an MSB-first hardware SPI!
BIT_REVERSE = bytearray(
    sum(1 << (7 - i) for i in range(8) if (b >> i) & 1) for b in range(256)
)


def _send(is_data, byte_val):
    """Sends a 3-byte SPI frame, exactly matching the C code structure."""
    lcd_cs.value(0)

    # 1. Start Byte: 0x5F for Data, 0x1F for Command
    start_byte = 0x5F if is_data else 0x1F

    # 2. Lower Nibble MUST go first
    lower_nibble = byte_val & 0x0F

    # 3. Upper Nibble MUST go second
    upper_nibble = (byte_val >> 4) & 0x0F

    # Reverse all bits before sending to trick the MSB-first hardware
    buf = bytearray([
        BIT_REVERSE[start_byte],
        BIT_REVERSE[lower_nibble],
        BIT_REVERSE[upper_nibble]
    ])

    spi.write(buf)
    lcd_cs.value(1)

    # Delay logic ported exactly from C code
    if not is_data and 0 < byte_val < 4:
        time.sleep_ms(3)
    else:
        time.sleep_us(50)


def init():
    """Hardware reset and initialization sequence."""
    lcd_rst.value(0)
    time.sleep_ms(2)
    lcd_rst.value(1)
    time.sleep_ms(50)

    commands = [
        0x34,  # Function Set: 8-bit, RE=1
        0x09,  # ext. Function Set: 4 line mode
        0x30,  # Function Set: 8-bit, RE=0
        0x0C,  # Display ON, Cursor OFF (No more blinking block!)
        0x06,  # Entry Mode Set: Cursor Auto-Increment
        0x01  # Clear Display
    ]
    for cmd in commands:
        _send(False, cmd)


def print_line(line_num, text):
    """Prints a string to a specific line (0-3)."""
    line_offsets = [0x00, 0x20, 0x40, 0x60]
    if line_num < 0 or line_num > 3:
        return

    _send(False, 0x80 | line_offsets[line_num])

    padded_text = f"{text:<20}"
    for char in padded_text[:20]:
        _send(True, ord(char))


def update(state, detail1="", detail2=""):
    print_line(0, "Zx50 Bus Probe Rev A")
    print_line(1, f"State: {state}")
    print_line(2, detail1)
    print_line(3, detail2)