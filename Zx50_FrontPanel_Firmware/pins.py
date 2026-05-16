from machine import Pin, SPI
import machine

# ==========================================
# SHARED 8-BIT Z80 BUS (Multiplexed)
# ==========================================
PICO_BUS_PINS = [Pin(i, Pin.IN, Pin.PULL_DOWN) for i in range(8)]

def read_shared_bus():
    return machine.mem32[0xd0000004] & 0xFF

# ==========================================
# BUS LATCH CONTROLS (Active Low)
# ==========================================
OE_U1_ADDR_L = Pin(13, Pin.OUT, value=1)
OE_U3_ADDR_H = Pin(12, Pin.OUT, value=1)
OE_U4_DATA   = Pin(8, Pin.OUT, value=1)
OE_U5_STATUS = Pin(10, Pin.OUT, value=1)
OE_U6_SHADOW = Pin(9, Pin.OUT, value=1)
OE_U7_SHADOW_DATA = Pin(11, Pin.OUT, value=1)
LE_N = Pin(15, Pin.OUT, value=1)

# ==========================================
# Z80 CONTROL SIGNALS & INTERRUPTS
# ==========================================
Z80_IORQ = Pin(27, Pin.IN, Pin.PULL_UP)
Z80_WR   = Pin(28, Pin.IN, Pin.PULL_UP)
DISP_EN  = Pin(26, Pin.IN, Pin.PULL_UP)

# ==========================================
# FRONT PANEL UI & SPI DEVICES
# ==========================================
# Switches
SW_RUN  = Pin(21, Pin.IN, Pin.PULL_UP)
SW_STEP = Pin(22, Pin.IN, Pin.PULL_UP)

# SPI Bus
# The bus is shared by devices with different SPI mode requirements.
# We initialize it here, but the mode will be changed dynamically.
# Per the Pico datasheet, for SPI(0), SCK must be on GP18 and MOSI on GP19.
SPI_BUS = SPI(0, sck=Pin(18), mosi=Pin(19))

def setup_spi_for_lcd():
    """Configures the SPI bus for the quirky EA DIP205G-4NLED display."""
    SPI_BUS.init(baudrate=500_000, polarity=1, phase=1)

def setup_spi_for_hcms_and_leds():
    """Configures the SPI bus for the standard HCMS displays and 74HC595."""
    SPI_BUS.init(baudrate=1_000_000, polarity=0, phase=0)

# SPI Device Control Pins
LCD_CS  = Pin(16, Pin.OUT, value=1)      # Chip Select for character LCD (Active Low) - on GP16
HCMS_CE = Pin(17, Pin.OUT, value=1)      # Chip Enable for HCMS displays (Active Low) - on GP17
HCMS_RS = Pin(14, Pin.OUT, value=0)      # Register Select for HCMS (0=Control, 1=Data)
LED_CE  = Pin(20, Pin.OUT, value=0)      # Latch Enable for 74HC595 LED driver (Pulse high)