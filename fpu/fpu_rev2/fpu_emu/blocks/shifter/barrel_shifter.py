"""Hardware model of a 64-bit Bidirectional Barrel Shifter."""

from dataclasses import dataclass
from fpu_emu.blocks.shifter.shifter_adder import ShifterAdder
from fpu_emu.blocks.shifter.shifter_result import ShifterResult
from fpu_emu.fpga_resource import fpga_resource


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
    Supports 32-bit and 64-bit logical and arithmetic shifts (LSL, LSR, ASL, ASR).
    Carry bit position and overflow bounds calculations utilize the ShifterBlock's dedicated
    7-bit carry-chain units (sub_adder, cmp_adder) via input multiplexers, avoiding
    procedural python arithmetic.
    """

    MASK_32 = 0xFFFFFFFF
    MASK_64 = 0xFFFFFFFFFFFFFFFF

    @classmethod
    def lsl_32(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShifterResult:
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
        return ShifterResult(res=res, cf=cf, zf=zf, sf=sf)

    @classmethod
    def lsr_32(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShifterResult:
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
        return ShifterResult(res=res, cf=cf, zf=zf, sf=sf)

    @classmethod
    def lsl_64(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShifterResult:
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
        return ShifterResult(res=res, cf=cf, zf=zf, sf=sf)

    @classmethod
    def lsr_64(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShifterResult:
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
        return ShifterResult(res=res, cf=cf, zf=zf, sf=sf)

    @classmethod
    def asl_32(cls, val: int, count: int, sub_adder: ShifterAdder, cmp_adder: ShifterAdder) -> ShifterResult:
        """32-bit Arithmetic Shift Left."""
        val &= cls.MASK_32
        count &= 0x3F  # 6-bit shift count (0..63)
        sign = (val >> 31) & 1

        if count == 0:
            cf = False
            vf = False
            res = val
        elif count <= 32:
            carry_bit_pos = sub_adder.sub(32, count)
            cf = bool((val >> carry_bit_pos) & 1)
            res = (val << count) & cls.MASK_32
            # V flag: 1 if sign bit changed at any point during the shift
            if count < 32:
                shift_diff = cmp_adder.sub(31, count)
                norm_val = (~val & cls.MASK_32) if sign else val
                vf = bool((norm_val >> shift_diff) != 0)
            else:
                vf = (val != 0)
        else:
            cf = False
            res = 0
            vf = (val != 0)

        zf = (res == 0)
        sf = bool(res & 0x80000000)
        return ShifterResult(res=res, cf=cf, zf=zf, sf=sf, vf=vf)

    @classmethod
    def asr_32(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShifterResult:
        """32-bit Arithmetic Shift Right.

        Hardware barrel shifter fills upper vacated multiplexer bits with the operand's sign bit directly.
        Uses sub_adder once to compute (count - 1) for carry bit capture.
        """
        val &= cls.MASK_32
        count &= 0x3F  # 6-bit shift count (0..63)
        sign_bit = bool(val & 0x80000000)

        if count == 0:
            cf = False
            res = val
        elif count <= 32:
            carry_bit_pos = sub_adder.sub(count, 1)
            cf = bool((val >> carry_bit_pos) & 1)
            # Arithmetic right shift with sign fill (hardware mux upper-fill)
            signed_val = val if val < 0x80000000 else val - 0x100000000
            res = (signed_val >> count) & cls.MASK_32
        else:
            cf = sign_bit
            res = cls.MASK_32 if sign_bit else 0

        zf = (res == 0)
        sf = bool(res & 0x80000000)
        return ShifterResult(res=res, cf=cf, zf=zf, sf=sf, vf=False)

    @classmethod
    def asl_64(cls, val: int, count: int, sub_adder: ShifterAdder, cmp_adder: ShifterAdder) -> ShifterResult:
        """64-bit Arithmetic Shift Left."""
        val &= cls.MASK_64
        count &= 0x7F  # 7-bit shift count (0..127)
        sign = (val >> 63) & 1

        if count == 0:
            cf = False
            vf = False
            res = val
        elif count <= 64:
            carry_bit_pos = sub_adder.sub(64, count)
            cf = bool((val >> carry_bit_pos) & 1)
            res = (val << count) & cls.MASK_64
            # V flag: 1 if sign bit changed at any point during the shift
            if count < 64:
                shift_diff = cmp_adder.sub(63, count)
                norm_val = (~val & cls.MASK_64) if sign else val
                vf = bool((norm_val >> shift_diff) != 0)
            else:
                vf = (val != 0)
        else:
            cf = False
            res = 0
            vf = (val != 0)

        zf = (res == 0)
        sf = bool(res & 0x8000000000000000)
        return ShifterResult(res=res, cf=cf, zf=zf, sf=sf, vf=vf)

    @classmethod
    def asr_64(cls, val: int, count: int, sub_adder: ShifterAdder) -> ShifterResult:
        """64-bit Arithmetic Shift Right.

        Hardware barrel shifter fills upper vacated multiplexer bits with the operand's sign bit directly.
        Uses sub_adder once to compute (count - 1) for carry bit capture.
        """
        val &= cls.MASK_64
        count &= 0x7F  # 7-bit shift count (0..127)
        sign_bit = bool(val & 0x8000000000000000)

        if count == 0:
            cf = False
            res = val
        elif count <= 64:
            carry_bit_pos = sub_adder.sub(count, 1)
            cf = bool((val >> carry_bit_pos) & 1)
            # Arithmetic right shift with sign fill (hardware mux upper-fill)
            signed_val = val if val < 0x8000000000000000 else val - 0x10000000000000000
            res = (signed_val >> count) & cls.MASK_64
        else:
            cf = sign_bit
            res = cls.MASK_64 if sign_bit else 0

        zf = (res == 0)
        sf = bool(res & 0x8000000000000000)
        return ShifterResult(res=res, cf=cf, zf=zf, sf=sf, vf=False)
