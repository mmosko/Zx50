from machine import Pin, SPI
import time

# 1. Hardware Pin Definitions
cs_pin = Pin(17, Pin.OUT)  # Chip Enable (CE)
sck_pin = Pin(18, Pin.OUT)  # Serial Clock (SCK)
tx_pin = Pin(19, Pin.OUT)  # Data In (DATA)
rs_pin = Pin(14, Pin.OUT)  # Register Select (RS)

# 2. Configure SPI (HCMS requires Mode 1 or 0, usually MSB first, < 5 MHz)
spi = SPI(0, baudrate=1000000, polarity=0, phase=0, sck=sck_pin, mosi=tx_pin)


fontA = [
  0b01110,
  0b10001,
  0b10001,
  0b11111,
  0b10001,
  0b10001,
  0b10001
]

def send_to_display(is_command, data_bytes: bytearray):
    """
    Sends data to the HCMS-39XX.
    is_command = True for config, False for character data
    """
    rs_pin.value(0 if is_command else 1)

    cs_pin.value(0)  # Select display
    spi.write(data_bytes)
    cs_pin.value(1)  # Deselect display to latch data

def init_display():
    # Example Initialization Command Sequence (Check datasheet for your exact model)
    # Mode Register: Brightness, Peak Current, Sleep Mode
    # 0x00 is usually the address for the control word

    #   SPI.transfer(B11001100);
    #   SPI.transfer(B11001100);
    #   SPI.transfer(B11001100);
    #   SPI.transfer(B11001100);
    #   SPI.transfer(B11001100);

    send_to_display(is_command=True, data_bytes=bytearray([
        0b01001110,
        0b10000001]
    ))  # e.g., set brightness/display normal



def display_string(text):
    # Convert string characters to their ASCII font values
    # (HCMS-39XX has a built-in 128-character ASCII generator)
    bytes_to_send = bytearray([ord(c) for c in text])
    send_to_display(is_command=False, data_bytes=bytes_to_send)


# 3. Main Program Loop
init_display()
while True:
    display_string("HELLO")
    time.sleep(1)
    display_string("PICO ")
    time.sleep(1)
