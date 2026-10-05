"""Radix-4 Modified Booth Multiplier primitive (alu_booth_mul).

Pure 32-bit Radix-4 Modified Booth multiplication datapath.
Retires 2 bits per cycle over 16 clock cycles, producing a 64-bit product.
Supports both signed (two's complement) and unsigned modes.
"""

from dataclasses import dataclass
from fpu_emu.fpga_resource import fpga_resource


@dataclass
class BoothMulResult:
    """Result of a 32-bit Radix-4 Booth multiplication."""

    res: bytearray  # 8 bytes little-endian (bytes 0..3: low 32 bits, bytes 4..7: high 32 bits)
    cf: bool  # Always False
    zf: bool  # True if entire 64-bit product is zero
    sf: bool  # True if MSB of 64-bit product (bit 63) is 1
    vf: bool  # True if product overflows 32-bit representation


@fpga_resource(
    approach="Radix-4 Booth Multiplier with CCU2C carry-chains, internal {P, Q} FFs, and RES_BUS MUX",
    luts=77,
    slices_ccu2c=17,
    ffs=75,
    delay_ns=4.7,
    cycles=16,
    shared_unit="alu_booth_mul",
)
class BoothMulCore:
    """Radix-4 Modified Booth Multiplier hardware core."""

    @staticmethod
    def booth_mul_core(a: bytes, b: bytes, signed: bool = True) -> BoothMulResult:
        """Pure 32-bit Radix-4 Booth multiplication core.

        Retires 2 bits per step over 16 iterations.
        Takes 32-bit multiplier Q from HA_MUX and 32-bit multiplicand M from HB_MUX.

        :param a: 4-byte little-endian multiplier Q (typically from HA_MUX)
        :param b: 4-byte little-endian multiplicand M (typically from HB_MUX)
        :param signed: True for signed two's-complement multiplication, False for unsigned
        :return: BoothMulResult with 8-byte product and status flags (cf, zf, sf, vf)
        """
        if len(a) != 4 or len(b) != 4:
            raise ValueError(f"Operands must be 4 bytes each, got len(a)={len(a)}, len(b)={len(b)}")

        q_raw = int.from_bytes(a, byteorder="little", signed=False)
        m_raw = int.from_bytes(b, byteorder="little", signed=False)

        m_val = int.from_bytes(b, byteorder="little", signed=True) if signed else m_raw
        q = q_raw
        p = 0
        q_prev = 0

        # 16 Radix-4 Booth iterations (retires 2 bits per iteration)
        for _ in range(16):
            window = ((q & 0x03) << 1) | q_prev
            match window:
                case 1 | 2:
                    p += m_val
                case 3:
                    p += (m_val << 1)
                case 4:
                    p -= (m_val << 1)
                case 5 | 6:
                    p -= m_val
                case _:
                    pass  # Window 0 (000) or 7 (111): +0

            q_prev = (q >> 1) & 1

            # Combined arithmetic right shift of {P, Q} by 2 bits
            q = ((p & 0x03) << 30) | (q >> 2)
            p >>= 2

        # Unsigned mode post-correction:
        # If Q[31] was 1, cancels out the negative weight (-2^31) introduced by Booth recoding
        if not signed and (q_raw & 0x80000000):
            p += m_val

        low_word = q & 0xFFFFFFFF
        high_word = p & 0xFFFFFFFF

        low_bytes = low_word.to_bytes(4, byteorder="little", signed=False)
        high_bytes = high_word.to_bytes(4, byteorder="little", signed=False)
        product_bytes = bytearray(low_bytes + high_bytes)

        # Flag evaluation
        cf = False
        zf = product_bytes == b"\x00" * 8
        sf = bool(high_bytes[3] & 0x80)

        if signed:
            # Overflow if high word is not the sign extension of low word
            sign_ext = 0xFFFFFFFF if (low_word & 0x80000000) else 0x00000000
            vf = high_word != sign_ext
        else:
            # Unsigned overflow if high word is non-zero
            vf = high_word != 0

        return BoothMulResult(
            res=product_bytes,
            cf=cf,
            zf=zf,
            sf=sf,
            vf=vf,
        )
