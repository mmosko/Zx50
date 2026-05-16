import pins
import time
import machine

# This LCD driver is for the EA DIP205G-4NLED, which has a very unusual
# LSB-first serial interface. Standard MicroPython SPI is MSB-first.
# To make this work, all outgoing bytes must have their bits reversed
# before being sent to the hardware SPI driver.
# The display is a 5x8 dot matrix of 4 lines of 20 characters

# Pre-computed lookup table to instantly reverse the bits of any byte (0-255).
BIT_REVERSE_TABLE = bytearray(
    sum(1 << (7 - i) for i in range(8) if (b >> i) & 1) for b in range(256)
)

def _send(is_data, byte_val):
    """
    Sends a command or data byte to the LCD using the required 3-byte frame format.
    """
    pins.setup_spi_for_lcd()
    pins.LCD_CS.value(0)

    start_byte = 0x5F if is_data else 0x1F
    lower_nibble = byte_val & 0x0F
    upper_nibble = (byte_val >> 4) & 0x0F

    buf = bytearray([
        BIT_REVERSE_TABLE[start_byte],
        BIT_REVERSE_TABLE[lower_nibble],
        BIT_REVERSE_TABLE[upper_nibble]
    ])

    pins.SPI_BUS.write(buf)
    pins.LCD_CS.value(1)

    # Increased delay to help stabilize display and prevent character corruption.
    if not is_data and 0 < byte_val < 4:
        time.sleep_ms(3)
    else:
        time.sleep_us(100) # Increased from 50us


def init():
    """
    Initializes the LCD with the specific command sequence required by the
    EA display controller.
    """
    time.sleep_ms(50)
    commands = [
        0x34, 0x09, 0x30, 0x0C, 0x06, 0x01
    ]
    for cmd in commands:
        _send(False, cmd)


def clear():
    """Clears the entire LCD screen and returns the cursor to home."""
    _send(False, 0x01)


def print_line(line_num, text):
    """
    Prints a string to a specific line (0-3) on the 4x20 display.
    """
    line_offsets = [0x00, 0x20, 0x40, 0x60]
    if not (0 <= line_num <= 3):
        return

    _send(False, 0x80 | line_offsets[line_num])

    padded_text = f"{text:<20}"
    for char in padded_text[:20]:
        _send(True, ord(char))
