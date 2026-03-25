from machine import Pin, SPI

# ==========================================
# SHARED 8-BIT Z80 BUS (Multiplexed)
# ==========================================
# GP0-GP7 act as the shared read bus for U1, U3, and U4
PICO_BUS = [Pin(i, Pin.IN, Pin.PULL_DOWN) for i in range(8)]

# ==========================================
# TRANSCEIVER CONTROLS (Active Low)
# ==========================================
OE_U1_ADDR_L = Pin(8, Pin.OUT, value=1)  # Reads A0-A7 (Port Address / C Reg)
OE_U3_ADDR_H = Pin(9, Pin.OUT, value=1)  # Reads A8-A15 (OTIR Counter / B Reg)
OE_U4_DATA   = Pin(10, Pin.OUT, value=1) # Reads D0-D7 (Data Bus)

# ==========================================
# Z80 CONTROL SIGNALS & INTERRUPTS
# ==========================================
Z80_IORQ = Pin(11, Pin.IN, Pin.PULL_UP)  # Priority Interrupt
Z80_WR   = Pin(12, Pin.IN, Pin.PULL_UP)  # Priority Interrupt
DISP_EN  = Pin(26, Pin.IN, Pin.PULL_UP)  # Faceplate update enable

# ==========================================
# FRONT PANEL UI & SPI
# ==========================================
SW_RUN  = Pin(21, Pin.IN, Pin.PULL_UP)
SW_STEP = Pin(22, Pin.IN, Pin.PULL_UP)

LCD_CS  = Pin(16, Pin.OUT, value=1)
LCD_RS  = Pin(17, Pin.OUT, value=0)
LED_CE  = Pin(20, Pin.OUT, value=0)

SPI_BUS = SPI(0, baudrate=10_000_000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))

# Helper to quickly read the shared 8-bit GPIO bus
def read_shared_bus():
    # Reads GP0-GP7 simultaneously using the Pico's underlying port register
    # 0xFF masks just the bottom 8 bits
    return machine.mem32[0xd0000004] & 0xFF