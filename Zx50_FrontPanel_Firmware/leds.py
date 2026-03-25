import pins


def update_discrete_leds(led_byte):
    """
    Shifts 8 bits to the 74HC595 and latches them to the outputs.
    """
    # 595 just listens to MOSI and SCLK. We push data, then pulse the latch.
    pins.SPI_BUS.write(bytearray([led_byte]))

    # Pulse RCLK (LED_CE) to latch data to the output pins
    pins.LED_CE.value(1)
    pins.LED_CE.value(0)


def init_hcms_displays():
    """
    Initialize the cascaded HCMS-3973 and HCMS-3962 displays.
    Requires sending the control words to wake them up and set brightness.
    """
    # Note: HCMS uses standard SPI but lacks a traditional CS pin in this wiring.
    # Data flows continuously through the cascade.
    pass


def write_hcms_text(text):
    """
    Convert ASCII text to 5x7 font columns and shift to the HCMS cascade.
    """
    pass