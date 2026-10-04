"""Physical and logical register file implementation for Zx50 FPU.

Enforces physical bus routing via HA_BUS and HB_BUS, single-tick multiplexer
timing rules, and clock-enabled writeback via RES_BUS. Direct access to math
and compound registers is strictly forbidden during execution.
"""

from enum import Enum

from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register


class HardwareTimingConflictError(Exception):
    """Raised when hardware timing rules are violated in a single clock cycle."""

    pass


class HardwareBusError(Exception):
    """Raised when an illegal bus access occurs."""

    pass


class HardwareAccessViolationError(Exception):
    """Raised when direct register access is attempted on bus-gated registers."""

    pass




class StatusFlag(Enum):
    """Status register flag bit allocations (SystemDesign.md Section 2.1)."""

    DIFF_SIGN = 0  # Bit 0: Effective subtraction / operand signs differ
    ERR = 1  # Bit 1: Error flag (Division by zero, domain errors, stack traps)
    UNDERFLOW = 2  # Bit 2: Stack or floating-point underflow
    OVERFLOW = 3  # Bit 3: Stack, integer, or floating-point overflow
    CARRY = 4  # Bit 4: Arithmetic carry or borrow
    SIGN = 5  # Bit 5: Sign flag (1 = Negative)
    ZERO = 6  # Bit 6: Zero flag (1 = Result is zero)
    BUSY = 7  # Bit 7: Hardware execution busy flag


class Registers:
    """Register file holding all physical FPU registers and enforcing bus architecture."""

    def __init__(self, clock: Clock):
        # 32-bit registers (Little-Endian: byte 0 = LSB, byte 3 = MSB)
        self.al = Register(name=Reg.AL, size_in_bits=32, clock=clock)
        self.ah = Register(name=Reg.AH, size_in_bits=32, clock=clock)
        self.bl = Register(name=Reg.BL, size_in_bits=32, clock=clock)
        self.bh = Register(name=Reg.BH, size_in_bits=32, clock=clock)
        self.dl = Register(name=Reg.DL, size_in_bits=32, clock=clock)
        self.dh = Register(name=Reg.DH, size_in_bits=32, clock=clock)
        self.fl = Register(name=Reg.FL, size_in_bits=32, clock=clock)
        self.fh = Register(name=Reg.FH, size_in_bits=32, clock=clock)

        # 12-bit Exponent registers (stored in 2 bytes, Little-Endian)
        self.ea = Register(name=Reg.EA, size_in_bits=12, clock=clock)
        self.eb = Register(name=Reg.EB, size_in_bits=12, clock=clock)

        # 6-bit Loop/Shift counter (stored in 1 byte)
        self.c = Register(name=Reg.C, size_in_bits=6, clock=clock)

        # Control and Pointer registers
        self.status = Register(name=Reg.STATUS, size_in_bits=8, clock=clock)
        self.sp = Register(name=Reg.SP, size_in_bits=8, clock=clock)
        self.osp =Register(name=Reg.OSP, size_in_bits=8, clock=clock)
        self.upc = Register(name=Reg.UPC, size_in_bits=10, clock=clock)

        # The instruction registers (read from u_code memory)
        self.instr = Register(name=Reg.INSTR, size_in_bits=18, clock=clock)
        self.imm = Register(name=Reg.IMM, size_in_bits=10, clock=clock)

        # The dispatcher - functional block handshakes
        self.exec_ready = Register(name=Reg.EXEC_READY, size_in_bits=1, clock=clock)
        self.exec_wb = Register(name=Reg.EXEC_WB, size_in_bits=1, clock=clock)
        self.exec_done = Register(name=Reg.EXEC_DONE, size_in_bits=1, clock=clock)
