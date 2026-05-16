from chip_decode import U5Decode, U6Decode


class BusStatus:
    def __init__(self, wr_n: bool, iorq_n: bool, u5_decode: U5Decode, u6_decode: U6Decode,
                 addr_l: int, addr_h: int, data_val: int, shadow_data_val: int):
        """Combines all status and bus values into one class. Uses negative logic for flags."""
        self.wr_n = wr_n
        self.iorq_n = iorq_n
        self.u5_decode = u5_decode
        self.u6_decode = u6_decode
        self.addr_l = addr_l
        self.addr_h = addr_h
        self.data_val = data_val
        self.shadow_data_val = shadow_data_val

    def get_z80_status_chars(self):
        """Returns a 2-char output for the front panel Z80 Status"""

        # In negative logic, 'False' means the signal is asserted (LOW).
        # We invert them here into local booleans for clean, readable condition checks.
        is_rd = not self.u5_decode.rd_n
        is_mreq = not self.u5_decode.mreq_n
        is_wr = not self.wr_n
        is_iorq = not self.iorq_n

        if not self.u5_decode.halt_n: return "HL"
        if is_rd and is_mreq: return "RM"
        if is_wr and is_mreq: return "WM"
        if is_rd and is_iorq: return "RI"
        if is_wr and is_iorq: return "WI"

        return "  "

    def __str__(self):
        """Returns a status string for the LCD display"""
        return f"A:{self.addr_h:02X}{self.addr_l:02X} D:{self.data_val:02X}"

    def get_hcms_text(self):
        """
        Returns the formatted 12-character string for the HCMS displays.
        Because the cascade flows Green -> Red, the Red characters must be sent FIRST.
        """
        # Red Display (4 chars at the end of the pipeline): ST_DD
        red_str = f"{self.u6_decode.to_glyphs()}{self.shadow_data_val:02X}"

        # Green Display (8 chars at the start of the pipeline): AAAA_ST_DD
        green_str = f"{self.addr_h:02X}{self.addr_l:02X}{self.get_z80_status_chars()}{self.data_val:02X}"

        return red_str + green_str

    def get_lcd_line_2(self):
        """Returns the formatted 19-character debug string for LCD Line 2."""
        # Matches the AAAA_ST_DD format of the green LEDs
        return f"Z:{str(self.u5_decode)} {self.addr_h:02X}{self.addr_l:02X}{self.get_z80_status_chars()}{self.data_val:02X}"

    def get_lcd_line_3(self):
        """Returns the formatted debug string for LCD Line 3."""
        # Matches the ST_DD format of the red LEDs (minus the unprintable glyphs)
        return f"S:{str(self.u6_decode)}       {self.shadow_data_val:02X}"
