"""Microcode ROM mapping UserOpcode to micro-instruction sequences."""

from typing import List

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.ucode import fpu_symbols, fpu_ucode
from fpu_emu.user_opcodes import UserOpcode


class MicroCode:
    """Microcode ROM lookup table."""

    # 1024 words (EBR 4-7) for runtime microcode execution store
    HARD_MAX_MICRO_INSTRUCTIONS: int = 1024
    SOFT_MAX_MICRO_INSTRUCTIONS: int = 1024
    MAX_MICRO_INSTRUCTIONS: int = HARD_MAX_MICRO_INSTRUCTIONS

    @classmethod
    def get_address(cls, opcode: UserOpcode) -> int:
        """Returns the start UPC address for an opcode in the microcode ROM."""
        sym = f"USER_{opcode.name}"
        if sym in fpu_symbols:
            return fpu_symbols[sym]
        return 0

    @classmethod
    @fpga_resource(
        approach="Cascaded Single-Port SysMEM EBR (EBR 4-7, 1024x32) for runtime microcode execution store",
        luts=0,
        ffs=0,
        ebr=4,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_microcode_rom",
    )
    def get(cls, opcode: UserOpcode) -> List[MicroInstruction]:
        """
        Verifies that the opcode is implemented, then returns the whole ROM contents
        :param opcode:
        :return:
        """
        sym = f"USER_{opcode.name}"
        if sym in fpu_symbols:
            return fpu_ucode
        raise NotImplementedError(f"Microcode for opcode {opcode} not implemented")

    @classmethod
    def total_instructions(cls) -> int:
        """Returns the total number of micro-instructions across all defined opcodes."""
        return len(fpu_ucode)

    @classmethod
    def remaining_capacity(cls) -> int:
        """Returns the remaining micro-instruction slots available in the 512-word EBR store."""
        return cls.MAX_MICRO_INSTRUCTIONS - cls.total_instructions()

    @classmethod
    def validate_budget(cls) -> None:
        """Validates that total micro-instructions do not exceed the 512 EBR limit."""
        total = cls.total_instructions()
        if total > cls.MAX_MICRO_INSTRUCTIONS:
            raise ValueError(
                f"Total microcode instructions ({total}) exceeds EBR capacity limit of {cls.MAX_MICRO_INSTRUCTIONS}"
            )


# Enforce budget compliance at module import time
MicroCode.validate_budget()

