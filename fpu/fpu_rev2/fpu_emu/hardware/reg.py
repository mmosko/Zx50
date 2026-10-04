from enum import Enum


class Reg(Enum):
    """Register enumeration."""

    # 32-bit General & Math Registers
    AL = 0
    AH = 1
    EA = 2
    EB = 3
    IMM = 4
    C = 5

    BL = 6
    BH = 7
    DL = 8
    DH = 9
    FL = 10
    FH = 11

    # Control, Status, and Pointers
    STATUS = 15
    SP = 16
    OSP = 17
    UPC = 18

    INSTR = 20,
    EXEC_READY = 21
    EXEC_WB = 22,
    EXEC_DONE = 23,

    # These are virtual registers only used in Assembly MicroInstructions.  The functional block needs to
    # resolve them down to the actual registers used in the HA and HB and RES muxes
    AX = 30,
    BX = 31,
    DX = 32,
    FX = 33,