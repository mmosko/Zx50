"""Hardware model of a 64-bit Bidirectional Barrel Shifter."""

from dataclasses import dataclass
from fpu_emu.blocks.shifter.shifter_adder import ShifterAdder
from fpu_emu.fpga_resource import fpga_resource


@dataclass(frozen=True)
class ShiftResult:
    """Result of a barrel shift operation."""

    res: int  # 32-bit or 64-bit shifted result
    cf: bool  # Last bit shifted out (carry out)
    zf: bool  # Zero flag
    sf: bool  # Sign flag (MSB of result)


@fpga_resource(
    approach="64-bit 6-stage bidirectional logarithmic barrel shifter",
    luts=96,
    ffs=0,
    delay_ns=3.2,
    cycles=1,
    shared_unit="barrel_shifter",
)
class BarrelShifter:
    """64-bit Bidirectional Barrel Shifter.

    Models a 6-stage logarithmic multiplexer network (shift distances: 1, 2, 4, 8, 16, 32).
    Supports 32-bit and 64-bit logical shifts (LSL, LSR).
    Carry bit position calculations utilize the ShifterBlock's dedicated 7-bit carry-chain
    subtractor (sub_adder) via input multiplexers, avoiding procedural python arithmetic.
    """

    MASK_32 = 0xFFFFFFFF
    MASK_64 = 0xFFFFFFFFFFFFFFFF

    @classmethod
    def lsl_32(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShiftResult:
        """32-bit Logical Shift Left."""
        val &= cls.MASK_32
        count &= 0x3F  # 6-bit shift count (0..63)

        if count == 0:
            cf = False
            res = val
        elif count <= 32:
            carry_bit_pos = sub_adder.sub(32, count)
            cf = bool((val >> carry_bit_pos) & 1)
            res = (val << count) & cls.MASK_32
        else:
            cf = False
            res = 0

        zf = (res == 0)
        sf = bool(res & 0x80000000)
        return ShiftResult(res=res, cf=cf, zf=zf, sf=sf)

    @classmethod
    def lsr_32(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShiftResult:
        """32-bit Logical Shift Right."""
        val &= cls.MASK_32
        count &= 0x3F  # 6-bit shift count (0..63)

        if count == 0:
            cf = False
            res = val
        elif count <= 32:
            carry_bit_pos = sub_adder.sub(count, 1)
            cf = bool((val >> carry_bit_pos) & 1)
            res = (val >> count) & cls.MASK_32
        else:
            cf = False
            res = 0

        zf = (res == 0)
        sf = False  # MSB is always 0 for 32-bit logical shift right
        return ShiftResult(res=res, cf=cf, zf=zf, sf=sf)

    @classmethod
    def lsl_64(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShiftResult:
        """64-bit Logical Shift Left."""
        val &= cls.MASK_64
        count &= 0x7F  # 7-bit shift count (0..127)

        if count == 0:
            cf = False
            res = val
        elif count <= 64:
            carry_bit_pos = sub_adder.sub(64, count)
            cf = bool((val >> carry_bit_pos) & 1)
            res = (val << count) & cls.MASK_64
        else:
            cf = False
            res = 0

        zf = (res == 0)
        sf = bool(res & 0x8000000000000000)
        return ShiftResult(res=res, cf=cf, zf=zf, sf=sf)

    @classmethod
    def lsr_64(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShiftResult:
        """64-bit Logical Shift Right."""
        val &= cls.MASK_64
        count &= 0x7F  # 7-bit shift count (0..127)

        if count == 0:
            cf = False
            res = val
        elif count <= 64:
            carry_bit_pos = sub_adder.sub(count, 1)
            cf = bool((val >> carry_bit_pos) & 1)
            res = (val >> count) & cls.MASK_64
        else:
            cf = False
            res = 0

        zf = (res == 0)
        sf = False  # MSB is always 0 for logical shift right
        return ShiftResult(res=res, cf=cf, zf=zf, sf=sf)
