"""Unit tests for the PriorityEncoder32 hardware module."""

from fpu_emu.blocks.shifter.priority_encoder import PriorityEncoder32


def test_priority_encoder_zero():
    res = PriorityEncoder32.encode(0)
    assert not res.valid
    assert res.bit_pos == 0
    assert res.bit_len == 0


def test_priority_encoder_all_powers_of_two():
    """Every single bit from bit 0 to bit 31 must produce bit_pos == i and bit_len == i + 1."""
    for i in range(32):
        val = 1 << i
        res = PriorityEncoder32.encode(val)
        assert res.valid
        assert res.bit_pos == i, f"Failed bit_pos for bit {i}: expected {i}, got {res.bit_pos}"
        assert res.bit_len == i + 1, f"Failed bit_len for bit {i}: expected {i + 1}, got {res.bit_len}"


def test_priority_encoder_with_lower_bits_set():
    """MSB must determine the bit position and length regardless of lower bits."""
    for i in range(32):
        lower_mask = (1 << i) - 1
        val = (1 << i) | (0x55555555 & lower_mask)
        res = PriorityEncoder32.encode(val)
        assert res.valid
        assert res.bit_pos == i
        assert res.bit_len == i + 1


def test_priority_encoder_all_ones():
    res = PriorityEncoder32.encode(0xFFFFFFFF)
    assert res.valid
    assert res.bit_pos == 31
    assert res.bit_len == 32


def test_priority_encoder_nibble_boundaries():
    # Bit 3 (group 0 MSB) -> pos 3, len 4
    enc = PriorityEncoder32.encode(0x00000008)
    assert enc.bit_pos == 3 and enc.bit_len == 4
    # Bit 4 (group 1 LSB) -> pos 4, len 5
    enc = PriorityEncoder32.encode(0x00000010)
    assert enc.bit_pos == 4 and enc.bit_len == 5
    # Bit 7 (group 1 MSB) -> pos 7, len 8
    enc = PriorityEncoder32.encode(0x00000080)
    assert enc.bit_pos == 7 and enc.bit_len == 8
    # Bit 8 (group 2 LSB) -> pos 8, len 9
    enc = PriorityEncoder32.encode(0x00000100)
    assert enc.bit_pos == 8 and enc.bit_len == 9
