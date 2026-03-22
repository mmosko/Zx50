import machine
import time

# Hardware configuration
CS_PIN = 17
RST_PIN = 20
SCK_PIN = 18
MOSI_PIN = 19

# Initialize pins and SPI bus on import
lcd_cs = machine.Pin(CS_PIN, machine.Pin.OUT)
lcd_rst = machine.Pin(RST_PIN, machine.Pin.OUT)

# SPI0 at 1MHz (Safe speed for EA DIP205 controller)
spi = machine.SPI(0, baudrate=1000000, sck=machine.Pin(SCK_PIN), mosi=machine.Pin(MOSI_PIN))
lcd_cs.value(1)

def _send(is_data, byte_val):
    """Internal function: Sends a 3-byte SPI frame to the RW1073 controller."""
    lcd_cs.value(0)
    # 0xFA for Data (RS=1), 0xF8 for Command (RS=0)
    start_byte = 0xFA if is_data else 0xF8
    # Format: Start Byte, High Nibble, Low Nibble
    spi.write(bytearray([start_byte, byte_val & 0xF0, (byte_val << 4) & 0xF0]))
    lcd_cs.value(1)
    time.sleep_us(50)

def init():
    """Hardware reset and software initialization for the EA DIP205."""
    # 1. Hard Hardware Reset
    lcd_rst.value(0)
    time.sleep_ms(50)
    lcd_rst.value(1)
    time.sleep_ms(50)
    
    # 2. Standard HD44780 Initialization sequence
    commands = [
        0x38, # Function set: 8-bit, 2+ lines
        0x0C, # Display ON, Cursor OFF
        0x06, # Entry mode: Increment
        0x01  # Clear Display
    ]
    for cmd in commands:
        _send(False, cmd)
        time.sleep_ms(2) # Wait >1.5ms for Clear command to execute

def print_line(line_num, text):
    """Prints a string to a specific line (0-3), padding it to clear old text."""
    # Standard DDRAM starting addresses for 4x20 character LCDs
    line_offsets = [0x00, 0x40, 0x14, 0x54]
    if line_num < 0 or line_num > 3: 
        return
    
    # Move cursor to the start of the specified line
    _send(False, 0x80 | line_offsets[line_num])
    
    # Pad string to exactly 20 chars to overwrite old text cleanly
    padded_text = f"{text:<20}"
    for char in padded_text[:20]:
        _send(True, ord(char))

def update(state, detail1="", detail2=""):
    """Public helper to cleanly update the 4-line UI."""
    print_line(0, "Zx50 Bus Probe Rev A")
    print_line(1, f"State: {state}")
    print_line(2, detail1)
    print_line(3, detail2)
    