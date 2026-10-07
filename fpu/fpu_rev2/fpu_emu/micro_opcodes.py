"""Micro-operation codes and MicroInstruction dataclass for the micro-sequencer."""

from enum import Enum
from typing import Union


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
    PACK = 0b001_000
    UNPACK = 0b001_001
    MUL = 0b001_010
    DIV = 0b001_011
    MULU = 0b001_110
    DIVU = 0b001_111
    # ====================
    # LOGIC (prefix 0b010)
    AND = 0b010_000
    OR = 0b010_001
    XOR = 0b010_010
    FABS = 0b010_011
    FCHS = 0b010_100
    NOT = 0b010_101
    # ====================
    # SHIFTER (prefix 0b110)
    LSL = 0b110_000
    LSR = 0b110_001
    LZC = 0b110_110
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
    SSAV = 0b101_110
    SRES = 0b101_111
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

    @property
    def block_id(self) -> int:
        """Extracts upper 3-bit block ID (bits [5:3]) for AND-wall routing."""
        return (self.value >> 3) & 0x07

    @property
    def sub_op(self) -> int:
        """Extracts lower 3-bit sub-operation ID (bits [2:0])."""
        return self.value & 0x07

    @classmethod
    def parse(cls, arg: Union[str, int, "MicroOp"]) -> "MicroOp":
        """
        Parses a MicroOp from an enum instance, integer value, or string.

        Supports:
          - MicroOp.ADD
          - 0b000000 or 0
          - "ADD" or "add"
          - "0b000000", "0x00", "0"
        """
        if isinstance(arg, cls):
            return arg

        if isinstance(arg, int):
            try:
                return cls(arg)
            except ValueError:
                raise ValueError(f"Invalid 6-bit MicroOp integer value: {arg} (0x{arg:02X})")

        if isinstance(arg, str):
            clean_str = arg.strip()

            # 1. Try matching by Enum name (case-insensitive)
            try:
                return cls[clean_str.upper()]
            except KeyError:
                pass

            # 2. Try parsing numeric string (int base 0 auto-detects 0b..., 0x..., or decimal)
            try:
                val = int(clean_str, 0)
                return cls(val)
            except ValueError:
                pass

        raise ValueError(f"Cannot parse '{arg}' as a valid {cls.__name__}")