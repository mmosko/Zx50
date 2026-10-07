from enum import IntEnum


class Reg(IntEnum):
    """
    Register enumeration.

    All low-word registers have bit-0 as "0" and all high-word registers have bit-1 as "1".
    This means for 64-bit operations, we have `W=1` and we pass the low-register index.  The ALU
    function can then read the low register and then read the high register with an "OR 0b0001".
    """

    # 32-bit General & Math Registers
    AL = 0b0000
    AH = 0b0001
    EA = 2
    EB = 3
    IMM = 4
    C = 5

    BL = 0b0110
    BH = 0b0111
    DL = 0b1000
    DH = 0b1001
    FL = 0b1010
    FH = 0b1011

    # Used as a flag to writeback that there is no writeback result register
    NONE = 0b1111

    # Control, Status, and Pointers
    UPC = 14
    STATUS = 16
    SP = 17
    OSP = 18

    INSTR = 20
    EXEC_READY = 21
    EXEC_WB = 22
    EXEC_DONE = 23

    # This is stored in the control block, not the register file
    RET = 24
    RET_SET = 25

    # Stored in the Memory block
    STATUS_SHADOW = 26

    # These are virtual registers only used in Assembly MicroInstructions.  These names are used
    # only by the assembler
    AX = 30
    BX = 31
    DX = 32
    FX = 33

    def is_lo_half(self) -> bool:
        return self in [Reg.AL, Reg.BL, Reg.DL, Reg.FL]

