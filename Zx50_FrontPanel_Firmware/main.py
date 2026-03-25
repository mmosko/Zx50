import pins
import time
import z80_io


def main():
    last_update = time.ticks_ms()
    update_interval = 100  # 100ms = 10Hz update rate

    while True:
        # Check if it's time for our 10Hz passive screen update
        if time.ticks_diff(time.ticks_ms(), last_update) >= update_interval:
            last_update = time.ticks_ms()

            # Only update the passive display if DISP_EN is active
            if pins.DISP_EN.value() == 0:
                # 1. Read current Address Bus
                pins.OE_U1_ADDR_L.value(0)
                addr_l = pins.read_shared_bus()
                pins.OE_U1_ADDR_L.value(1)

                pins.OE_U3_ADDR_H.value(0)
                addr_h = pins.read_shared_bus()
                pins.OE_U3_ADDR_H.value(1)

                # 2. Read current Data Bus
                pins.OE_U4_DATA.value(0)
                data_val = pins.read_shared_bus()
                pins.OE_U4_DATA.value(1)

                # 3. Format and send to HCMS displays
                # leds.update_front_panel(addr_h, addr_l, data_val)

        # Handle switch state changes...
        # ...


if __name__ == '__main__':
    main()