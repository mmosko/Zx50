"""32-bit Radix-2 Non-Restoring Divider hardware core (alu_div_core).

Pure 32-bit Radix-2 Non-Restoring division datapath.
Retires 1 quotient bit per cycle over 32 clock cycles, producing a 32-bit quotient
and 32-bit remainder.
Supports both signed (two's complement truncated division) and unsigned modes.
"""

from dataclasses import dataclass
from fpu_emu.fpga_resource import fpga_resource

MASK_32 = 0xFFFFFFFF
SIGN_32 = 0x80000000
MIN_INT32 = -0x80000000


@dataclass
class DivResult:
    """Result of a 32-bit integer division."""

    quotient: bytearray  # 4 bytes little-endian
    remainder: bytearray  # 4 bytes little-endian
    cf: bool  # False
    zf: bool  # True if quotient is zero
    sf: bool  # True if MSB of quotient is 1
    vf: bool  # True on divide-by-zero or signed overflow (0x80000000 / -1)
    err: bool  # True on divide-by-zero


@fpga_resource(
    approach="32-bit Radix-2 Non-Restoring Divider with CCU2C carry-chains, internal {R, Q} FFs, and quotient/remainder latch",
    luts=75,
    slices_ccu2c=17,
    ffs=72,
    delay_ns=4.8,
    cycles=32,
    shared_unit="alu_div_core",
)
class DivCore:
    """32-bit Radix-2 Non-Restoring Divider hardware core."""

    @staticmethod
    def _non_restoring_div(n: int, d: int) -> tuple[int, int]:
        """Core 32-bit unsigned Radix-2 non-restoring division algorithm.

        :param n: 32-bit unsigned dividend
        :param d: 32-bit unsigned divisor (d != 0)
        :return: (quotient, remainder) both 32-bit unsigned integers
        """
        r = 0
        q = n
        for _ in range(32):
            bit = (q >> 31) & 1
            r = (r << 1) | bit
            q = (q << 1) & MASK_32
            if r >= 0:
                r -= d
            else:
                r += d

            if r >= 0:
                q |= 1

        if r < 0:
            r += d

        return q & MASK_32, r & MASK_32

    @staticmethod
    def div_core(a: bytes, b: bytes, signed: bool = True) -> DivResult:
        """Pure 32-bit division core.

        Takes 32-bit dividend from HA_MUX and 32-bit divisor from HB_MUX.
        Produces 32-bit quotient and 32-bit remainder.

        :param a: 4-byte little-endian dividend (from HA_MUX)
        :param b: 4-byte little-endian divisor (from HB_MUX)
        :param signed: True for signed two's-complement division, False for unsigned
        :return: DivResult with quotient, remainder, and status flags
        """
        if len(a) != 4 or len(b) != 4:
            raise ValueError(
                f"Operands must be 4 bytes each, got len(a)={len(a)}, len(b)={len(b)}"
            )

        d_raw = int.from_bytes(b, byteorder="little", signed=False)

        # 1. Divide-by-zero check
        if d_raw == 0:
            return DivResult(
                quotient=bytearray(4),
                remainder=bytearray(4),
                cf=False,
                zf=False,
                sf=False,
                vf=True,
                err=True,
            )

        if signed:
            n_signed = int.from_bytes(a, byteorder="little", signed=True)
            d_signed = int.from_bytes(b, byteorder="little", signed=True)

            # 2. Signed overflow check: 0x80000000 / -1 -> overflow
            if n_signed == MIN_INT32 and d_signed == -1:
                q_val = SIGN_32
                r_val = 0
                q_bytes = bytearray(q_val.to_bytes(4, byteorder="little", signed=False))
                r_bytes = bytearray(r_val.to_bytes(4, byteorder="little", signed=False))
                return DivResult(
                    quotient=q_bytes,
                    remainder=r_bytes,
                    cf=False,
                    zf=False,
                    sf=True,
                    vf=True,
                    err=False,
                )

            neg_q = (n_signed < 0) ^ (d_signed < 0)
            neg_r = n_signed < 0  # Truncated division: remainder sign matches dividend

            n_mag = abs(n_signed)
            d_mag = abs(d_signed)

            q_mag, r_mag = DivCore._non_restoring_div(n_mag, d_mag)

            q_int = (-q_mag & MASK_32) if neg_q else q_mag
            r_int = (-r_mag & MASK_32) if neg_r else r_mag

        else:
            n_raw = int.from_bytes(a, byteorder="little", signed=False)
            q_int, r_int = DivCore._non_restoring_div(n_raw, d_raw)

        q_bytes = bytearray(q_int.to_bytes(4, byteorder="little", signed=False))
        r_bytes = bytearray(r_int.to_bytes(4, byteorder="little", signed=False))

        zf = q_int == 0
        sf = bool(q_int & SIGN_32)
        vf = False
        err = False

        return DivResult(
            quotient=q_bytes,
            remainder=r_bytes,
            cf=False,
            zf=zf,
            sf=sf,
            vf=vf,
            err=err,
        )
