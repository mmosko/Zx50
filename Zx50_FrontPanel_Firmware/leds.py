import pins
import time
import font
from bus_status import BusStatus

# ==========================================
# HCMS Dot-Matrix Control Word 0 (D7 = 0)
# D6 = Sleep Mode (0=Sleep, 1=Awake)
# D5 = Peak Current (0=100%, 1=73%)
# D3-D0 = Brightness (0000=Min, 1111=100%)
# ==========================================
# 0b0100_1110 = Register 0, AWAKE, 100% Peak Current, 80% Brightness
# RED Display: Let's dim it down. 50% Peak Current, 80% PWM Brightness
CW0_RED_CONFIG   = 0b0101_1110  # D5=1 (50%), D3-D0=1110 (80%)

# GREEN Display: Let's max it out. 73% Peak Current, 100% PWM Brightness
CW0_GREEN_CONFIG = 0b0100_1111  # D5=0 (73%), D3-D0=1111 (100%)

CW1_NORMAL_MODE = 0b1000_0000

RS_BIT_CONTROL = 1
RS_BIT_DATA = 0

def set_discrete_leds(bus_status: BusStatus, extra_n: bool = True):
    """
    Constructs the shift register byte based on the physical PCB bodge.
    Active-low hardware logic perfectly matches the current-sinking LEDs.
    (True = High/LED OFF, False = Low/LED ON)
    """
    led_byte = 0

    # Pack the bits into their respective shift register positions
    led_byte |= (extra_n & 1) << 0  # QA
    led_byte |= (bus_status.u5_decode.m1_n & 1) << 1  # QB
    led_byte |= (bus_status.u5_decode.wait_n & 1) << 2  # QC
    led_byte |= (bus_status.u6_decode.int_n & 1) << 3  # QD
    led_byte |= (bus_status.u5_decode.nmi_n & 1) << 4  # QE
    led_byte |= (bus_status.u5_decode.halt_n & 1) << 5  # QF
    led_byte |= (bus_status.u5_decode.busrq_n & 1) << 6  # QG
    led_byte |= (bus_status.u5_decode.busak_n & 1) << 7  # QH

    _write_discrete_led_byte(led_byte)


def set_discrete_led_off():
    _write_discrete_led_byte(0xFF)


def _write_discrete_led_byte(led_byte):
    """
    Shifts 8 bits to the 74HC595 shift register to update the discrete LEDs.
    """
    pins.setup_spi_for_hcms_and_leds()
    pins.LED_CE.value(0)
    pins.SPI_BUS.write(bytearray([led_byte]))
    pins.LED_CE.value(1)


def initialize_display():
    pins.setup_spi_for_hcms_and_leds()
    time.sleep_us(50)

    # Boot up: We have 12 characters total (One 8-char display + One 4-char display).
    # An 8-char display contains 2 ICs. A 4-char display contains 1 IC.
    # Therefore, the Control Register chain is exactly 3 bytes long.

    pins.HCMS_RS.value(RS_BIT_CONTROL)
    pins.HCMS_CE.value(0)

    # Blast the wake-up command down the intact cascade to all 3 ICs
    pins.SPI_BUS.write(bytes([
        CW1_NORMAL_MODE, CW1_NORMAL_MODE, CW1_NORMAL_MODE,
        CW0_RED_CONFIG,  # IC 3 (Red Display)
        CW0_GREEN_CONFIG,  # IC 2 (Green Display Right Half)
        CW0_GREEN_CONFIG  # IC 1 (Green Display Left Half)
    ]))

    pins.HCMS_CE.value(1)
    time.sleep_us(50)


def write_hcms_text(text):
    """
    Renders a string of characters on the cascaded HCMS displays.
    """
    pins.setup_spi_for_hcms_and_leds()

    # Buffer the entire payload into a single bytearray
    payload = bytearray()

    # 1. Iterate FORWARD through the text
    for char in text:
        char_code = ord(char)
        if char_code not in font.FONT_MAP:
            char_code = ord('?')

        # 2. Iterate FORWARD through the columns to fix mirroring
        for column_data in font.FONT_MAP[char_code]:
            payload.append(column_data)

    pins.HCMS_RS.value(RS_BIT_DATA)  # RS=0 for DATA Register (using your constant)
    pins.HCMS_CE.value(0)  # Start the shift
    pins.SPI_BUS.write(payload)  # Blast all 60 bytes down the unbroken cascade
    pins.HCMS_CE.value(1)  # Latch the data to the displays