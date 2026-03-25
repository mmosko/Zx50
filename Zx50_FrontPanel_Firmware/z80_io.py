import pins
import time

# Define the specific I/O port address the Pico responds to
PICO_PORT_ADDRESS = 0x50


def handle_z80_write_irq(pin):
    """
    Triggered on the FALLING edge of ~WR (assuming ~IORQ is already low).
    """
    # 1. Quick sanity check: Is IORQ actually low?
    if pins.Z80_IORQ.value() != 0:
        return

    # 2. Latch and read the Lower Address (U1) to see if this is for us
    pins.OE_U1_ADDR_L.value(0)
    port_addr = pins.read_shared_bus()
    pins.OE_U1_ADDR_L.value(1)

    if port_addr != PICO_PORT_ADDRESS:
        return  # Not our port, ignore it

    # 3. Enter High-Speed OTIR Transfer Loop
    # We stay in this loop as long as the Z80 is bursting data
    while True:
        # Read the Data Bus (U4)
        pins.OE_U4_DATA.value(0)
        data_byte = pins.read_shared_bus()
        pins.OE_U4_DATA.value(1)

        # TODO: Push data_byte to an internal FIFO buffer for the LCD/Displays
        # buffer.append(data_byte)

        # Read the Upper Address (U3) to check the OTIR B-Register counter
        pins.OE_U3_ADDR_H.value(0)
        b_reg_counter = pins.read_shared_bus()
        pins.OE_U3_ADDR_H.value(1)

        # If the counter hits 0, the OTIR instruction is finished
        if b_reg_counter == 0:
            break

        # Wait for the Z80 to cycle the next ~WR pulse before looping
        # (Timeout prevents infinite hang if CPU resets)
        timeout = 1000
        while pins.Z80_WR.value() == 1 and timeout > 0:
            timeout -= 1
        if timeout == 0:
            break


# Attach the hardware interrupt to the ~WR pin
pins.Z80_WR.irq(trigger=pins.Pin.IRQ_FALLING, handler=handle_z80_write_irq)