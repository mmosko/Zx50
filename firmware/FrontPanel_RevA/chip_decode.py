import font

# NOTE: IORQ_N and WR_N are wired directly to the PICO so it can handle
# the Z80 port writes to its configuration register.

class U5Decode:
    """
    Decodes the Z80 Status Latch (U5).
    Uses NEGATIVE LOGIC (literal hardware pin states):
    - False (0) = Signal is LOW / Asserted
    - True  (1) = Signal is HIGH / Inactive

    This matches the current-sinking 74HC595 LED driver logic,
    allowing these values to be passed directly to the LEDs.
    """
    def __init__(self, rd_n: bool, busrq_n: bool, mreq_n: bool, busak_n: bool,
                 m1_n: bool, wait_n: bool, nmi_n: bool, halt_n: bool):
        self.rd_n = rd_n
        self.busrq_n = busrq_n
        self.mreq_n = mreq_n
        self.busak_n = busak_n
        self.m1_n = m1_n
        self.wait_n = wait_n
        self.nmi_n = nmi_n
        self.halt_n = halt_n

    @classmethod
    def decode(cls, value):
        # Physical alignment: 1D = RD_N (Bit 0) ... 8D = HALT_N (Bit 7)
        return cls(
            rd_n=bool(value & 0b0000_0001),
            busrq_n=bool(value & 0b0000_0010),
            mreq_n=bool(value & 0b0000_0100),
            busak_n=bool(value & 0b0000_1000),
            m1_n=bool(value & 0b0001_0000),
            wait_n=bool(value & 0b0010_0000),
            nmi_n=bool(value & 0b0100_0000),
            halt_n=bool(value & 0b1000_0000),
        )

    def __str__(self):
        """
        String to display on LCD.
        Upper case = HIGH (Inactive), Lower case = LOW (Asserted).
        Output: RQMA1WNH
        """
        c0 = "R" if self.rd_n else "r"
        c1 = "Q" if self.busrq_n else "q"
        c2 = "M" if self.mreq_n else "m"
        c3 = "A" if self.busak_n else "a"
        c4 = "1" if self.m1_n else "i"  # 'i' used for active M1
        c5 = "W" if self.wait_n else "w"
        c6 = "N" if self.nmi_n else "n"
        c7 = "H" if self.halt_n else "h"
        return f"{c0}{c1}{c2}{c3}{c4}{c5}{c6}{c7}"


class U6Decode:
    """
    Decodes the Shadow Bus Status Latch (U6).
    Uses NEGATIVE LOGIC (literal hardware pin states):
    - False (0) = Signal is LOW / Asserted
    - True  (1) = Signal is HIGH / Inactive
    """
    def __init__(self, int_n: bool, sh_stb_n: bool, sh_inc_n: bool, sh_en_n: bool,
                 sh_rw: bool, sh_done_n: bool, sh_busy_n: bool):
        self.int_n = int_n
        self.sh_stb_n = sh_stb_n
        self.sh_inc_n = sh_inc_n
        self.sh_en_n = sh_en_n
        self.sh_rw = sh_rw  # Positive logic: True (1) = Read, False (0) = Write
        self.sh_done_n = sh_done_n
        self.sh_busy_n = sh_busy_n

    @classmethod
    def decode(cls, value):
        # Physical alignment: 1D (Bit 0) is tied to GND.
        # All signals are shifted left by 1 bit!
        return cls(
            int_n=bool(value & 0b0000_0010),  # Bit 1
            sh_stb_n=bool(value & 0b0000_0100),  # Bit 2
            sh_inc_n=bool(value & 0b0000_1000),  # Bit 3
            sh_en_n=bool(value & 0b0001_0000),  # Bit 4
            sh_rw=bool(value & 0b0010_0000),  # Bit 5
            sh_done_n=bool(value & 0b0100_0000),  # Bit 6
            sh_busy_n=bool(value & 0b1000_0000),  # Bit 7
        )

    def __str__(self):
        """
        String to display on LCD:
        An upper case character means HIGH (or true or not asserted).
        A lower case character means LOW (or asserted or false).
        The read/write bit is always lower case and either a "r" or "w".

        The output is always 8 characters:
        _TSIE[rw]DB
        """
        c0 = " "
        c1 = "T" if self.int_n else "t"
        c2 = "S" if self.sh_stb_n else "s"
        c3 = "I" if self.sh_inc_n else "i"
        c4 = "E" if self.sh_en_n else "e"
        c5 = "r" if self.sh_rw else "w"
        c6 = "D" if self.sh_done_n else "d"
        c7 = "B" if self.sh_busy_n else "b"
        return f"{c0}{c1}{c2}{c3}{c4}{c5}{c6}{c7}"

    def to_glyphs(self):
        """
        Converts the Shadow Bus status into the two 5x7 HCMS glyph characters.
        """
        quad_char = 0
        if not self.sh_en_n:   quad_char |= 1
        if not self.sh_busy_n: quad_char |= 2
        if self.sh_rw:         quad_char |= 4
        if not self.sh_done_n: quad_char |= 8

        glyph_map = {
            0: ord(' '),
            1: font.GLYPH_QUAD_UL,
            2: font.GLYPH_QUAD_UR,
            3: font.GLYPH_QUAD_UL_UR,
            4: font.GLYPH_QUAD_LL,
            5: font.GLYPH_QUAD_UL_LL,
            6: font.GLYPH_QUAD_LL_UR,
            7: font.GLYPH_QUAD_UL_LL_UR,
            8: font.GLYPH_QUAD_LR,
            9: font.GLYPH_QUAD_UL_LR,
            10: font.GLYPH_QUAD_UR_LR,
            11: font.GLYPH_QUAD_UL_UR_LR,
            12: font.GLYPH_QUAD_LL_LR,
            13: font.GLYPH_QUAD_UL_LL_LR,
            14: font.GLYPH_QUAD_LL_UR_LR,
            15: font.GLYPH_QUAD_ALL
        }
        char1 = glyph_map.get(quad_char, ord('?'))

        half_char = 0
        if not self.sh_stb_n: half_char |= font.GLYPH_UPPER_BLOCK
        if not self.sh_inc_n: half_char |= font.GLYPH_LOWER_BLOCK

        # If both are inactive, half_char is 0x00.
        # This safely maps to a blank space in your font.py!
        char2 = half_char

        return chr(char1) + chr(char2)


