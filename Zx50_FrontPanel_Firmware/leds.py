import pins
import time
import font

# ==========================================
# HCMS Dot-Matrix Display Constants
# ==========================================
CW_SLEEP_MODE_OFF = 0b0001_0000
CW_SLEEP_MODE_ON  = 0b0000_0000
CW_BRIGHTNESS_100 = 0b1111_0000
CW_BRIGHTNESS_05  = 0b0000_0000

def update_discrete_leds(led_byte):
    """
    Shifts 8 bits to the 74HC595 shift register to update the discrete LEDs.
    """
    pins.setup_spi_for_hcms_and_leds()
    pins.SPI_BUS.write(bytearray([led_byte]))
    pins.LED_CE.value(1)
    pins.LED_CE.value(0)

def _write_hcms_word(word, is_control=True):
    """Internal helper to send a control or data word to the HCMS cascade."""
    pins.setup_spi_for_hcms_and_leds()
    pins.HCMS_RS.value(0 if is_control else 1)
    pins.HCMS_CE.value(0)
    pins.SPI_BUS.write(bytearray([word]))
    pins.HCMS_CE.value(1)
    time.sleep_us(50)

def init_hcms_displays():
    """
    Initializes the cascaded HCMS-39xx displays.
    """
    _write_hcms_word(CW_SLEEP_MODE_OFF, is_control=True)
    _write_hcms_word(CW_SLEEP_MODE_OFF, is_control=True)
    _write_hcms_word(CW_BRIGHTNESS_100, is_control=True)
    _write_hcms_word(CW_BRIGHTNESS_100, is_control=True)
    write_hcms_text(" " * 12) # Clear display

def write_hcms_text(text):
    """
    Renders a string of characters on the 12-character cascaded HCMS displays.
    The string is right-aligned and padded with spaces.
    """
    padded_text = f"{text:>12}"
    for char in padded_text:
        char_code = ord(char)
        if char_code not in font.FONT_MAP:
            char_code = ord('?') # Default to '?' if char not in font

        # The font data is a tuple of 5 bytes (columns)
        for column_data in font.FONT_MAP[char_code]:
            _write_hcms_word(column_data, is_control=False)
