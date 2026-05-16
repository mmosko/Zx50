import ubinascii

import pins
import time
import z80_io
import lcd
import leds
from zx50_card import read_bus

FIRMWARE_VERSION = "v2.0"


class PanelState:
    """Enumeration of the Front Panel's operating states."""
    DISABLED = 0
    RUNNING = 1
    STEPPING = 2


def process_fifo():
    if not z80_io.fifo: return
    command = z80_io.fifo.popleft()
    if command == 0x01:
        lcd.clear()
        message = bytearray()
        while z80_io.fifo: message.append(z80_io.fifo.popleft())
        lines = message.decode('ascii', 'ignore').split('\n')
        for i, line in enumerate(lines):
            if i < 4: lcd.print_line(i, line)


def update_passive_displays():
    # --- 0. Read entire bus state in one shot ---
    status = read_bus()

    # --- 1. Update Discrete LEDs (74HC595) ---
    leds.set_discrete_leds(status)

    # --- 2. Update HCMS Dot Matrix (12 Characters) ---
    hcms_text = status.get_hcms_text()
    leds.write_hcms_text(hcms_text)

    # Encode the string to bytes, hexlify it, and decode the hex bytes back to a string
    hex_str = ubinascii.hexlify(hcms_text.encode('utf-8')).decode('utf-8')
    print(f"[DEBUG] hcms_text: {hcms_text} (0x{hex_str})")

    # --- 3. Update LCD Debug Lines (20 Characters max) ---
    lcd.print_line(2, status.get_lcd_line_2())
    lcd.print_line(3, status.get_lcd_line_3())


def main():
    lcd.init()
    leds.initialize_display()
    leds.set_discrete_led_off()
    lcd.print_line(0, "Zx50 Front Panel")
    lcd.print_line(1, f"Firmware {FIRMWARE_VERSION}")
    lcd.print_line(3, "  ...  warmup  ... ")
    # need to have the RED leds first
    leds.write_hcms_text("89AB01234567")
    time.sleep(4)
    lcd.print_line(3, "")

    # State Machine Variables
    current_state = None
    step_pressed_previously = False
    last_passive_update = time.ticks_ms()
    passive_update_interval = 100

    while True:
        # High-speed IO tasks must always run regardless of UI state
        process_fifo()

        # =====================================================================
        # STATE MACHINE LOGIC
        # See README.md Section 3: "Switch-Based Display Logic" for rules.
        # =====================================================================

        # 1. Read Raw Switch Inputs (Active Low = 0 is ON)
        disp_enabled = (pins.DISP_EN.value() == 0)
        run_switch_active = (pins.SW_RUN.value() == 0)
        step_switch_pressed = (pins.SW_STEP.value() == 0)

        # 2. Determine Edge Cases (Rising/Falling edges)
        step_just_pressed = step_switch_pressed and not step_pressed_previously
        step_pressed_previously = step_switch_pressed

        # 3. Determine Next State
        if not disp_enabled:
            next_state = PanelState.DISABLED
        elif run_switch_active:
            next_state = PanelState.RUNNING
        else:
            next_state = PanelState.STEPPING

        # 4. Handle State Transitions
        state_changed = (next_state != current_state)
        current_state = next_state

        should_update = False

        # 5. Execute State Behaviors
        if current_state == PanelState.DISABLED:
            # DISP_EN is high. Master kill-switch.
            if state_changed:
                # Wipe the displays exactly once upon entering this state
                leds.set_discrete_led_off()
                leds.write_hcms_text(" " * 12)
                lcd.print_line(2, " " * 20)
                lcd.print_line(3, " " * 20)

        elif current_state == PanelState.RUNNING:
            # Update continuously at the defined interval
            if time.ticks_diff(time.ticks_ms(), last_passive_update) >= passive_update_interval:
                should_update = True
                last_passive_update = time.ticks_ms()

        elif current_state == PanelState.STEPPING:
            # Update exactly once upon entering Step Mode, OR when the STEP button is clicked
            if state_changed or step_just_pressed:
                should_update = True

        # 6. Apply UI Updates
        if should_update:
            update_passive_displays()

        # Yield to prevent hard-locking the Pico core
        time.sleep_ms(10)


if __name__ == '__main__':
    main()