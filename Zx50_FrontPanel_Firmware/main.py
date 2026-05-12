import pins
import time
import z80_io
import lcd
import leds
import font

FIRMWARE_VERSION = "v0.7"

# Bit masks for the Z80 status byte read from latch U5.
STATUS_RD_N    = 0b0000_0001
STATUS_BUSRQ_N = 0b0000_0010
STATUS_MREQ_N  = 0b0000_0100
STATUS_BUSAK_N = 0b0000_1000
STATUS_M1_N    = 0b0001_0000
STATUS_WAIT_N  = 0b0010_0000
STATUS_NMI_N   = 0b0100_0000
STATUS_HALT_N  = 0b1000_0000

# Bit masks for the Shadow bus status byte read from U6
SHADOW_INT_N   = 0b0000_0001
SHADOW_SSTB_N  = 0b0000_0010
SHADOW_SINC_N  = 0b0000_0100
SHADOW_SH_EN_N = 0b0000_1000
SHADOW_SRW     = 0b0001_0000
SHADOW_SDONE_N = 0b0010_0000
SHADOW_SBUSY_N = 0b0100_0000

def get_z80_status_chars(status_byte, wr_val, iorq_val):
    """
    Returns a two-character string representing the Z80's current bus activity.
    """
    is_rd = not (status_byte & STATUS_RD_N)
    is_mreq = not (status_byte & STATUS_MREQ_N)
    is_halt = not (status_byte & STATUS_HALT_N)
    is_wr = not wr_val
    is_iorq = not iorq_val

    if is_halt: return "HL"
    if is_rd and is_mreq: return "RM"
    if is_wr and is_mreq: return "WM"
    if is_rd and is_iorq: return "RI"
    if is_wr and is_iorq: return "WI"
    return "  "

def get_shadow_status_glyphs(shadow_byte):
    """ Returns a 2-char string of glyphs for the Shadow bus status. """
    quad_char = 0
    if not (shadow_byte & SHADOW_SH_EN_N): quad_char |= 1
    if not (shadow_byte & SHADOW_SBUSY_N): quad_char |= 2
    if (shadow_byte & SHADOW_SRW): quad_char |= 4
    if not (shadow_byte & SHADOW_SDONE_N): quad_char |= 8
    
    glyph_map = {0:ord(' '), 1:0x04, 2:0x05, 3:0x08, 4:0x06, 5:0x09, 6:0x0C, 7:0x0E, 
                 8:0x07, 9:0x0A, 10:0x0B, 11:0x10, 12:0x0D, 13:0x0F, 14:0x11, 15:0x12}
    char1 = glyph_map.get(quad_char, ord('?'))

    half_char = 0
    if not (shadow_byte & SHADOW_SSTB_N): half_char = font.GLYPH_UPPER_BLOCK
    if not (shadow_byte & SHADOW_SINC_N): half_char |= font.GLYPH_LOWER_BLOCK
    char2 = half_char

    return chr(char1) + chr(char2)

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
    pins.OE_U1_ADDR_L.value(0); addr_l = pins.read_shared_bus(); pins.OE_U1_ADDR_L.value(1)
    pins.OE_U3_ADDR_H.value(0); addr_h = pins.read_shared_bus(); pins.OE_U3_ADDR_H.value(1)
    pins.OE_U4_DATA.value(0); data_val = pins.read_shared_bus(); pins.OE_U4_DATA.value(1)
    pins.OE_U5_STATUS.value(0); status_val = pins.read_shared_bus(); pins.OE_U5_STATUS.value(1)
    pins.OE_U6_SHADOW.value(0); shadow_val = pins.read_shared_bus(); pins.OE_U6_SHADOW.value(1)
    
    wr_val = pins.Z80_WR.value()
    iorq_val = pins.Z80_IORQ.value()

    z80_status_chars = get_z80_status_chars(status_val, wr_val, iorq_val)
    addr_str = f"{addr_h:02X}{addr_l:02X}"
    data_str = f"{data_val:02X}"
    u1_text = f"{data_str} {z80_status_chars} {addr_str}"
    
    shadow_status_glyphs = get_shadow_status_glyphs(shadow_val)
    u2_text = f"{shadow_status_glyphs} {data_val:02X}"

    leds.write_hcms_text(u1_text + u2_text)
    leds.update_discrete_leds(status_val)

def main():
    lcd.init()
    leds.init_hcms_displays()
    lcd.print_line(0, "Zx50 Front Panel")
    lcd.print_line(1, f"Firmware {FIRMWARE_VERSION}")
    time.sleep(2)
    lcd.clear()

    last_passive_update = time.ticks_ms()
    passive_update_interval = 100
    
    # --- Switch state tracking ---
    # Use positive logic: True if the system is in the "Run" state.
    # The switch is active-low, so run_mode is True when the pin is 0.
    run_mode = (pins.SW_RUN.value() == 0)
    prev_run_mode = run_mode
    
    step_pressed_previously = (pins.SW_STEP.value() == 0)

    while True:
        # Always process Z80->Pico communication
        process_fifo()

        # Master switch for the passive display. If disabled, do nothing.
        if pins.DISP_EN.value() == 1:
            time.sleep_ms(10)
            continue

        # --- Read current switch states ---
        prev_run_mode = run_mode
        run_mode = (pins.SW_RUN.value() == 0)
        
        step_is_pressed = (pins.SW_STEP.value() == 0)
        step_was_just_pressed = step_is_pressed and not step_pressed_previously
        step_pressed_previously = step_is_pressed

        # --- Determine if a display update is needed ---
        should_update = False
        if run_mode:
            # In RUN mode, update based on the timer
            if time.ticks_diff(time.ticks_ms(), last_passive_update) >= passive_update_interval:
                should_update = True
                last_passive_update = time.ticks_ms()
        else:
            # In STEP mode, update only on state changes
            # 1. Did we just switch from Run to Step mode?
            if not run_mode and prev_run_mode:
                should_update = True
            # 2. Was the STEP button just pressed?
            if step_was_just_pressed:
                should_update = True
        
        if should_update:
            update_passive_displays()

        time.sleep_ms(10) # Main loop delay

if __name__ == '__main__':
    main()