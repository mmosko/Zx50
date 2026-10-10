from enum import IntEnum


class Reg(IntEnum):
    """
    Register enumeration.

    All low-word registers have bit-0 as "0" and all high-word registers have bit-1 as "1".
    This means for 64-bit operations, we have `W=1` and we pass the low-register index.  The ALU
    function can then read the low register and then read the high register with an "OR 0b0001".
    """

    # 32-bit General & Math Registers (4-bit encoding 0..15)
    AL = 0b0000   # 0
    AH = 0b0001   # 1
    BL = 0b0010   # 2
    BH = 0b0011   # 3
    CL = 0b0100   # 4
    CH = 0b0101   # 5
    DL = 0b0110   # 6
    DH = 0b0111   # 7
    FL = 0b1000   # 8
    FH = 0b1001   # 9
    EA = 0b1010   # 10
    EB = 0b1011   # 11
    C = 0b1100    # 12
    IMM = 0b1101  # 13
    UPC = 0b1110  # 14
    NONE = 0b1111 # 15

    # Control, Status, and Pointers
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
    CX = 32
    DX = 33
    FX = 34

    def is_lo_half(self) -> bool:
        return self in [Reg.AL, Reg.BL, Reg.CL, Reg.DL, Reg.FL]

