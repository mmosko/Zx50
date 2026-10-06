"""Hardware model of a 32-bit Priority Encoder / Bit Length Detector."""

from dataclasses import dataclass
from fpu_emu.fpga_resource import fpga_resource


@dataclass(frozen=True)
class PriorityEncoderResult:
    """Result of 32-bit priority encoding."""

    valid: bool  # True if at least one bit is 1 (non-zero)
    bit_pos: int  # 0 to 31 if valid (5-bit position of MSB), 0 if input is 0
    bit_len: int  # 1 to 32 if valid, 0 if input is 0


@fpga_resource(
    approach="32-bit hierarchical priority encoder (8x 4-bit slices + 8:3 priority tree)",
    luts=28,
    ffs=0,
    delay_ns=2.2,
    cycles=1,
    shared_unit="priority_encoder32",
)
class PriorityEncoder32:
    """Hardware model of a 32-bit Priority Encoder / Bit Length Detector.

    Models an 8-slice tree of 4-bit priority encoders combined via an 8-to-3
    priority resolution network. Determines the index (0..31) of the most
    significant '1' bit in hardware without calling software built-in functions.
    """

    @staticmethod
    def _encode_nibble(nibble: int) -> tuple[bool, int]:
        """4-bit priority encoder slice (LUT4).

        Given 4 bits [b3, b2, b1, b0], returns (valid, pos) where pos is 1..4.
        """
        assert 0 <= nibble <= 0xF
        if nibble & 0b1000:
            return True, 4
        if nibble & 0b0100:
            return True, 3
        if nibble & 0b0010:
            return True, 2
        if nibble & 0b0001:
            return True, 1
        return False, 0

    @classmethod
    def encode(cls, val: int) -> PriorityEncoderResult:
        """Determines the bit position (0..31), bit length (1..32) and non-zero status of a 32-bit word."""
        val &= 0xFFFFFFFF
        if val == 0:
            return PriorityEncoderResult(valid=False, bit_pos=0, bit_len=0)

        # 8 nibble slices from MSB (group 7) down to LSB (group 0)
        for group in range(7, -1, -1):
            nibble = (val >> (group * 4)) & 0xF
            valid, pos = cls._encode_nibble(nibble)
            if valid:
                bit_pos = (group * 4) + (pos - 1)
                bit_len = bit_pos + 1
                return PriorityEncoderResult(valid=True, bit_pos=bit_pos, bit_len=bit_len)

        return PriorityEncoderResult(valid=False, bit_pos=0, bit_len=0)
