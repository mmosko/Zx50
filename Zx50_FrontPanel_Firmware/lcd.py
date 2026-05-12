import pins
import time
import machine

# This LCD driver is for the EA DIP205G-4NLED, which has a very unusual
# LSB-first serial interface. Standard MicroPython SPI is MSB-first.
# To make this work, all outgoing bytes must have their bits reversed
# before being sent to the hardware SPI driver.

# Pre-computed lookup table to instantly reverse the bits of any byte (0-255).
# This is significantly faster than reversing bits in a Python loop.
BIT_REVERSE_TABLE = bytearray(
    sum(1 << (7 - i) for i in range(8) if (b >> i) & 1) for b in range(256)
)

def _send(is_data, byte_val):
    """
    Sends a command or data byte to the LCD using the required 3-byte frame format.
    """
    # Ensure the SPI bus is configured for the LCD before sending data
    pins.setup_spi_for_lcd()

    pins.LCD_CS.value(0)

    # Frame Format: [Start Byte], [Lower Nibble], [Upper Nibble]
    start_byte = 0x5F if is_data else 0x1F
    lower_nibble = byte_val & 0x0F
    upper_nibble = (byte_val >> 4) & 0x0F

    # Reverse the bits of all three bytes before transmission
    buf = bytearray([
        BIT_REVERSE_TABLE[start_byte],
        BIT_REVERSE_TABLE[lower_nibble],
        BIT_REVERSE_TABLE[upper_nibble]
    ])

    pins.SPI_BUS.write(buf)
    pins.LCD_CS.value(1)

    # The display requires specific delays, especially for commands.
    if not is_data and 0 < byte_val < 4:
        time.sleep_ms(3) # e.g., 'Clear Display' takes longer
    else:
        time.sleep_us(50)


def init():
    """
    Initializes the LCD with the specific command sequence required by the
    EA display controller. This sequence was determined through trial and error.
    """
    # The Front Panel card does not have the RST pin connected.
    # A power-on delay is sufficient.
    time.sleep_ms(50)

    commands = [
        0x34,  # Function Set: 8-bit, enable extended instruction set (RE=1)
        0x09,  # Extended Function Set: Enable 4-line mode
        0x30,  # Function Set: 8-bit, disable extended instruction set (RE=0)
        0x0C,  # Display Control: Display ON, Cursor OFF, Blink OFF
        0x06,  # Entry Mode Set: Cursor auto-increments, no display shift
        0x01,  # Clear Display
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
    # DDRAM addresses for the start of each line
    line_offsets = [0x00, 0x20, 0x40, 0x60]
    if not (0 <= line_num <= 3):
        return

    # Set the DDRAM address command
    _send(False, 0x80 | line_offsets[line_num])

    # Pad text to 20 chars to clear the rest of the line, and send it
    padded_text = f"{text:<20}"
    for char in padded_text[:20]:
        _send(True, ord(char))
