import rp2
from machine import Pin
import pins
import collections

# Define the specific I/O port address the Pico responds to
PICO_PORT_ADDRESS = 0x50

# Create a FIFO buffer to hold data from the Z80
# Maxlen ensures it doesn't grow indefinitely if the display can't keep up
fifo = collections.deque((), 256)


class IOWrite:
    def __init__(self, addr_l, addr_h, data):
        self.port = addr_l  # The Z80 Port (A0-A7)
        self.b_reg = addr_h  # The B Register / Page Table Tag (A8-A15)
        self.data = data  # The Payload (D0-D7)

    def __str__(self):
        return f"Port: 0x{self.port:02X} | Data: 0x{self.data:02X} | B-Reg: 0x{self.b_reg:02X}"


@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_HIGH,
    set_init=rp2.PIO.OUT_HIGH,
    out_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH),
    in_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopush=False
)
def z80_io_snooper():
    wrap_target()

    # === 1. THE TRIGGER ===
    label("wait_wr")
    wait(1, gpio, 28).side(1)  # Wait for WR to go HIGH (Idle bus), LE_N is HIGH (Transparent)
    wait(0, gpio, 28)  # Wait for WR to drop LOW
    jmp(pin, "wait_wr")  # If IORQ (jmp_pin) is HIGH, it's a Memory Write. Ignore and loop.

    # === 2. THE TRAP ===
    nop().side(0)  # IORQ and WR are LOW! Drop LE_N to 0 to freeze all 74LVC573 latches.

    # === 3. GRAB PORT ADDRESS (A0-A7) ===
    # We need GPIO 13 (A_L) LOW and GPIO 12 (A_H) HIGH -> Bitmask 0b01 (1)
    set(x, 1)
    mov(osr, x)
    out(pins, 2)
    in_(pins, 8)  # Shift A0-A7 into the ISR

    # === 4. GRAB DATA (D0-D7) ===
    # Turn off Address OEs -> Bitmask 0b11 (3)
    set(x, 3)
    mov(osr, x)
    out(pins, 2)

    set(pins, 0)  # Drop GPIO 8 (DATA_OE) LOW
    in_(pins, 8)  # Shift D0-D7 into the ISR
    set(pins, 1)  # Raise GPIO 8 HIGH

    # === 5. GRAB B-REG / PAGE TABLE (A8-A15) ===
    # We need GPIO 13 (A_L) HIGH and GPIO 12 (A_H) LOW -> Bitmask 0b10 (2)
    set(x, 2)
    mov(osr, x)
    out(pins, 2)
    in_(pins, 8)  # Shift A8-A15 into the ISR

    # === 6. THE RELEASE ===
    set(x, 3)  # Turn all Address OEs back to HIGH
    mov(osr, x)
    out(pins, 2)
    push(noblock).side(1)  # Push packed 24-bit word to the RX FIFO, Raise LE_N to unlatch bus
    wrap()


# Initialize State Machine
sm = rp2.StateMachine(
    0,
    z80_io_snooper,
    freq=125_000_000,  # Run at full Pico speed
    in_base=pins.PICO_BUS_PINS[0],
    jmp_pin=pins.Z80_IORQ,
    sideset_base=pins.LE_N,
    set_base=pins.OE_U4_DATA,
    out_base=pins.OE_U3_ADDR_H  # Base 12 covers GPIO 12 and 13 perfectly
)
sm.active(1)


def poll():
    """
    Drains the hardware PIO FIFO, unpacks the words,
    and pushes the unified IOWrite objects into the Python deque.
    """
    while sm.rx_fifo():
        word = sm.get()

        # Unpack the 24-bit word
        addr_l = (word >> 16) & 0xFF
        data = (word >> 8) & 0xFF
        addr_h = word & 0xFF

        # Push EVERYTHING to the queue as an object
        fifo.append(IOWrite(addr_l, addr_h, data))