"""
Zx50 Bus Probe Rev B - Hardware Mappings (Updated for RevB)
Keyed by Physical J1 Pin Number for Adjacency Sweeping.
"""

# Maps Physical J1 Edge Connector Pin -> Logical Signal -> Multiplexer -> Mux Channel
BACKPLANE_PINS = {
    # Z80 Address Bus (Zig-Zag Routed)
    5: {"signal": "A0", "mux": "U4", "channel": 7},
    7: {"signal": "A1", "mux": "U4", "channel": 0},
    9: {"signal": "A2", "mux": "U4", "channel": 6},
    11: {"signal": "A3", "mux": "U4", "channel": 1},
    13: {"signal": "A4", "mux": "U4", "channel": 5},
    15: {"signal": "A5", "mux": "U4", "channel": 2},
    17: {"signal": "A6", "mux": "U4", "channel": 4},
    19: {"signal": "A7", "mux": "U4", "channel": 3},
    21: {"signal": "A8", "mux": "U5", "channel": 7},
    23: {"signal": "A9", "mux": "U5", "channel": 0},
    25: {"signal": "A10", "mux": "U5", "channel": 6},
    27: {"signal": "A11", "mux": "U5", "channel": 1},
    29: {"signal": "A12", "mux": "U5", "channel": 5},
    31: {"signal": "A13", "mux": "U5", "channel": 2},
    33: {"signal": "A14", "mux": "U5", "channel": 4},
    35: {"signal": "A15", "mux": "U5", "channel": 3},

    # Z80 Data Bus (Zig-Zag Routed)
    6: {"signal": "D0", "mux": "U3", "channel": 7},
    8: {"signal": "D1", "mux": "U3", "channel": 0},
    10: {"signal": "D2", "mux": "U3", "channel": 6},
    12: {"signal": "D3", "mux": "U3", "channel": 1},
    14: {"signal": "D4", "mux": "U3", "channel": 5},
    16: {"signal": "D5", "mux": "U3", "channel": 2},
    18: {"signal": "D6", "mux": "U3", "channel": 4},
    20: {"signal": "D7", "mux": "U3", "channel": 3},

    # SD Bus (Zig-Zag Routed)
    47: {"signal": "SD0", "mux": "U10", "channel": 7},
    49: {"signal": "SD1", "mux": "U10", "channel": 0},
    51: {"signal": "SD2", "mux": "U10", "channel": 6},
    53: {"signal": "SD3", "mux": "U10", "channel": 1},
    55: {"signal": "SD4", "mux": "U10", "channel": 5},
    57: {"signal": "SD5", "mux": "U10", "channel": 2},
    59: {"signal": "SD6", "mux": "U10", "channel": 4},
    61: {"signal": "SD7", "mux": "U10", "channel": 3},

    # GPIO Bus 0 (U11) - Note: Routing pattern differs here
    63: {"signal": "G0", "mux": "U11", "channel": 0},
    65: {"signal": "G1", "mux": "U11", "channel": 7},
    66: {"signal": "G2", "mux": "U11", "channel": 1},
    67: {"signal": "G3", "mux": "U11", "channel": 6},
    68: {"signal": "G4", "mux": "U11", "channel": 2},
    69: {"signal": "G5", "mux": "U11", "channel": 5},
    70: {"signal": "G6", "mux": "U11", "channel": 3},
    71: {"signal": "G7", "mux": "U11", "channel": 4},

    # GPIO Bus 1 (U12)
    72: {"signal": "G8", "mux": "U12", "channel": 0},
    73: {"signal": "G9", "mux": "U12", "channel": 7},
    74: {"signal": "G10", "mux": "U12", "channel": 1},
    75: {"signal": "G11", "mux": "U12", "channel": 6},
    76: {"signal": "G12", "mux": "U12", "channel": 2},
    77: {"signal": "G13", "mux": "U12", "channel": 5},
    78: {"signal": "G14", "mux": "U12", "channel": 3},
    79: {"signal": "G15", "mux": "U12", "channel": 4},

    # Control Group 1 (Zig-Zag Routed)
    22: {"signal": "~RD~", "mux": "U2", "channel": 7},
    24: {"signal": "~WR~", "mux": "U2", "channel": 0},
    26: {"signal": "~MREQ~", "mux": "U2", "channel": 6},
    28: {"signal": "~IORQ~", "mux": "U2", "channel": 1},
    30: {"signal": "~M1~", "mux": "U2", "channel": 5},
    32: {"signal": "~RFSH~", "mux": "U2", "channel": 2},
    34: {"signal": "~WAIT~", "mux": "U2", "channel": 4},
    36: {"signal": "~NMI~", "mux": "U2", "channel": 3},

    # Control Group 2 (U8) - Fully Custom Mapped
    39: {"signal": "~RESET~", "mux": "U8", "channel": 0},
    56: {"signal": "~SH_DONE~", "mux": "U8", "channel": 1},
    60: {"signal": "~BUSRQ~", "mux": "U8", "channel": 2},
    64: {"signal": "~INT~", "mux": "U8", "channel": 3},
    62: {"signal": "~BUSAK~", "mux": "U8", "channel": 4},
    58: {"signal": "~SH_BUSY~", "mux": "U8", "channel": 5},
    40: {"signal": "~HALT~", "mux": "U8", "channel": 6},
    # Note: U8 Channel 7 is unconnected in the netlist

    # Control Group 3 (U9) - Fully Custom Mapped
    37: {"signal": "IEI", "mux": "U9", "channel": 0},
    38: {"signal": "IEO", "mux": "U9", "channel": 1},
    50: {"signal": "~SH_INC~", "mux": "U9", "channel": 2},
    54: {"signal": "SH_RW", "mux": "U9", "channel": 3},
    52: {"signal": "~SH_EN~", "mux": "U9", "channel": 4},
    48: {"signal": "~SH_STB~", "mux": "U9", "channel": 5},
    42: {"signal": "CLK", "mux": "U9", "channel": 6},
    44: {"signal": "MCLK", "mux": "U9", "channel": 7},
}

# U14 (74HC154) Decoder Addresses mapping to Mux *OE pins
MUX_ADDR: dict[str, int] = {
    "U3": 0b0000,  # SEL0
    "U2": 0b0001,  # SEL1
    "U12": 0b0010,  # SEL2  (Corrected from U9)
    "U11": 0b0011,  # SEL3  (Corrected from U8)
    "U4": 0b0100,  # SEL4
    "U5": 0b0101,  # SEL5
    "U10": 0b0110,  # SEL6
    "U8": 0b0111,  # SEL7  (Corrected from U11)
    "U9": 0b1000,  # SEL8  (Corrected from U12)
    "GHOST": 0b1111  # Keeps all *OE lines high (Disabled)
}

LOCAL_GPIO_MAP: dict[str, int] = {
    "CHIP0": 2,
    "CHIP1": 3,
    "CHIP2": 4,
    "CHIP3": 5,
    "PORT0": 6,
    "PORT1": 7,
    "PORT2": 8
}

REMOTE_GPIO_MAP: dict[str, int] = {
    "CHIP0": 9,
    "CHIP1": 10,
    "CHIP2": 11,
    "CHIP3": 12,
    "PORT0": 13,
    "PORT1": 14,
    "PORT2": 15
}