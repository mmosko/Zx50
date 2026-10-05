"""Micro-operation codes and MicroInstruction dataclass for the micro-sequencer."""

from enum import Enum


class MicroOp(Enum):
    """Micro-sequencer primitive operations."""

    # ====================
    # ADDER (prefix 0b000, 0b001)
    ADD = 0b000_000
    ADC = 0b000_001
    SUB = 0b000_010
    SBB = 0b000_011
    CMP = 0b000_100
    EXP_ADD = 0b000_101
    EXP_SUB = 0b000_110
    MOD = 0b000_111
    PACK = 0b001_000
    UNPACK = 0b001_001
    MUL = 0b001_010
    DIV = 0b001_011
    MULU = 0b001_110
    # ====================
    # LOGIC (prefix 0b010)
    AND = 0b010_000
    OR = 0b010_001
    XOR = 0b010_010
    ABS = 0b010_011
    CHS = 0b010_100
    NOT = 0b010_101
    # ====================
    # SHIFTER (prefix 0b110)
    LSL = 0b110_000
    LSR = 0b110_001
    ASL = 0b110_010
    ASR = 0b110_011
    RRC = 0b001_100
    RLC = 0b001_101
    LZC = 0b100_111
    # ====================
    # MEMORY (prefix 0b100, 0b101)
    PUSH = 0b100_000
    POP = 0b100_001
    LDC = 0b100_010
    LDI = 0b100_011
    LD = 0b100_100
    STO = 0b100_101
    MOV = 0b100_110
    SWAP = 0b100_111
    LDU = 0b101_000
    STU = 0b101_001
    # ====================
    # CONTROL (prefix 0b011)
    JMP = 0b011_000
    JNZ = 0b011_001
    JZ = 0b011_010
    DJNZ = 0b011_011
    CALL = 0b011_100
    RET = 0b011_101
    NOP = 0b011_110
    HALT = 0b011_111

