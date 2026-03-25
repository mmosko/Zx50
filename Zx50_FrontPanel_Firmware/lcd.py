import pins
import time


def send_lcd_byte(data, is_command=True):
    """
    Sends a byte to the EA DIP205 over SPI.
    """
    pins.LCD_RS.value(0 if is_command else 1)

    pins.LCD_CS.value(0)  # Select LCD
    pins.SPI_BUS.write(bytearray([data]))
    pins.LCD_CS.value(1)  # Deselect LCD

    time.sleep_us(50)  # Give LCD time to process


def init_lcd():
    """
    Standard HD44780-style initialization sequence for the EA DIP205.
    """
    time.sleep_ms(50)  # Wait for power to stabilize
    send_lcd_byte(0x38)  # Function set: 8-bit, 2-line, 5x7
    send_lcd_byte(0x0C)  # Display ON, Cursor OFF
    send_lcd_byte(0x01)  # Clear Display
    time.sleep_ms(2)