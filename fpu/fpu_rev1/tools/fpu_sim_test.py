# tools/fpu_sim_test.py
"""
Pytest Unit Test Suite for ZX50 FPU Microcode Simulator
Tests 32-bit unsigned/signed integers, 16.16 fixed-point math, Quarter-Square multiplication,
reciprocal division, square root seeds, and transcendental log/exp/pow functions
across all critical boundary and edge conditions.
"""

import pytest
from fpu_sim import ZX50FPUMachine


# =============================================================================
# Helper Encoding & Decoding Utilities
# =============================================================================
def to_u32(val: int) -> int:
    """Mask integer to unsigned 32-bit."""
    return val & 0xFFFFFFFF


def to_i32(val: int) -> int:
    """Convert Python int to 32-bit two's complement uint32 representation."""
    return val & 0xFFFFFFFF


def from_i32(u32_val: int) -> int:
    """Convert 32-bit unsigned int from SRAM back to Python signed int."""
    u32_val &= 0xFFFFFFFF
    return u32_val - 0x100000000 if u32_val >= 0x80000000 else u32_val


def to_fx1616(val: float) -> int:
    """Convert float to 16.16 fixed-point uint32."""
    return int(round(val * 65536.0)) & 0xFFFFFFFF


def from_fx1616(u32_val: int) -> float:
    """Convert uint32 from SRAM back to Python 16.16 float."""
    signed_val = from_i32(u32_val)
    return signed_val / 65536.0


# =============================================================================
# 1. Unsigned 32-bit Addition Tests (`u32`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        # Zero Boundaries
        (0x00000000, 0x00000000, 0x00000000),
        (0x00000000, 0x12345678, 0x12345678),
        (0x12345678, 0x00000000, 0x12345678),
        # Byte Carry Boundary Traversals (0xFF -> 0x00 carry propagation)
        (0x000000FF, 0x00000001, 0x00000100),  # LSB Carry
        (0x0000FFFF, 0x00000001, 0x00010000),  # Word Carry
        (0x00FFFFFF, 0x00000001, 0x01000000),  # Upper Byte Carry
        # Maximum Unsigned Boundary Wrap-Around
        (0xFFFFFFFF, 0x00000001, 0x00000000),  # Full 32-bit Wrap
        (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFE),  # MAX + MAX Wrap
        # General Arbitrary Values
        (0x12345678, 0x00112233, 0x124578AB),
        (0xDEADBEEF, 0x01234567, 0xDFD10456),
    ],
)
def test_unsigned_add_32(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos(nos)
    fpu.push_tos(tos)
    fpu.execute_op("ADD", max_bytes=4)
    assert fpu.read_nos() == expected


# =============================================================================
# 2. Signed 32-bit Addition Tests (`i32`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        # Identity & Zero
        (0, 0, 0),
        (100, 0, 100),
        (0, -100, -100),
        # Basic Positive / Negative Mixed
        (500, -200, 300),
        (-500, 200, -300),
        (-1000, 1000, 0),  # Zero crossing
        # Boundary Values (INT32_MAX = 2147483647, INT32_MIN = -2147483648)
        (2147483647, 0, 2147483647),
        (-2147483648, 0, -2147483648),
        (2147483647, -2147483648, -1),
        # Two's Complement Overflow Boundary Wrap-around
        (2147483647, 1, -2147483648),  # Positive Overflow -> MIN
        (-2147483648, -1, 2147483647),  # Negative Overflow -> MAX
    ],
)
def test_signed_add_32(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos(to_i32(nos))
    fpu.push_tos(to_i32(tos))
    fpu.execute_op("ADD", max_bytes=4)
    result = from_i32(fpu.read_nos())
    assert result == expected


# =============================================================================
# 3. 16.16 Fixed-Point Addition Tests (`fx1616`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        # Zero and Integers
        (0.0, 0.0, 0.0),
        (1.0, 2.5, 3.5),
        (-10.5, 5.25, -5.25),
        # Smallest Fractional Step (1 / 65536 = 0.0000152587890625)
        (0.0, 0.0000152587890625, 0.0000152587890625),
        (0.5, 0.5, 1.0),
        (0.125, 0.375, 0.5),
        # Fixed Point Max / Min Boundaries (~32767.99998 / -32768.0)
        (32767.0, 0.99998, 32767.99998),
        (-32768.0, 0.5, -32767.5),
        (32767.99998, -32767.99998, 0.0),
    ],
)
def test_fixed1616_add(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos(to_fx1616(nos))
    fpu.push_tos(to_fx1616(tos))
    fpu.execute_op("ADD", max_bytes=4)
    result = from_fx1616(fpu.read_nos())
    assert pytest.approx(result, abs=1e-4) == expected


# =============================================================================
# 4. Unsigned 32-bit Subtraction Tests (`u32`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        # Equal Values (Zero Result)
        (0x00000000, 0x00000000, 0x00000000),
        (0x12345678, 0x12345678, 0x00000000),
        (0xFFFFFFFF, 0xFFFFFFFF, 0x00000000),
        # Basic Subtraction
        (0x00000050, 0x00000020, 0x00000030),
        (0x12345678, 0x00112233, 0x12233445),
        # Multi-byte Borrow Propagation
        (0x00000100, 0x00000001, 0x000000FF),  # LSB Borrow
        (0x00010000, 0x00000001, 0x0000FFFF),  # Word Borrow
        (0x01000000, 0x00000001, 0x00FFFFFF),  # Upper Byte Borrow
        # Underflow / Wrap-Around Boundaries
        (0x00000000, 0x00000001, 0xFFFFFFFF),  # 0 - 1 = MAX
        (0x00000000, 0xFFFFFFFF, 0x00000001),  # 0 - MAX = 1
    ],
)
def test_unsigned_sub_32(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos(nos)
    fpu.push_tos(tos)
    fpu.execute_op("SUB", max_bytes=4)
    assert fpu.read_nos() == expected


# =============================================================================
# 5. Signed 32-bit Subtraction Tests (`i32`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        # Identity
        (0, 0, 0),
        (100, 0, 100),
        (0, 100, -100),
        # Mixed Positive & Negative
        (500, 200, 300),
        (-500, -200, -300),
        (500, -200, 700),  # Subtracting negative -> addition
        (-500, 200, -700),
        # Boundary Values
        (2147483647, 2147483647, 0),
        (-2147483648, -2147483648, 0),
        (2147483647, 0, 2147483647),
        # Two's Complement Overflow / Underflow
        (-2147483648, 1, 2147483647),  # MIN - 1 -> Positive MAX
        (2147483647, -1, -2147483648),  # MAX - (-1) -> Negative MIN
    ],
)
def test_signed_sub_32(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos(to_i32(nos))
    fpu.push_tos(to_i32(tos))
    fpu.execute_op("SUB", max_bytes=4)
    result = from_i32(fpu.read_nos())
    assert result == expected


# =============================================================================
# 6. 16.16 Fixed-Point Subtraction Tests (`fx1616`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0.0, 0.0, 0.0),
        (10.5, 3.25, 7.25),
        (3.25, 10.5, -7.25),
        (-5.0, -2.5, -2.5),
        (-5.0, 2.5, -7.5),
        # Smallest Fractional Step Borrow
        (1.0, 0.0000152587890625, 0.9999847412109375),
        # Extreme Range
        (32767.99998, 32767.99998, 0.0),
        (-32768.0, -32768.0, 0.0),
    ],
)
def test_fixed1616_sub(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos(to_fx1616(nos))
    fpu.push_tos(to_fx1616(tos))
    fpu.execute_op("SUB", max_bytes=4)
    result = from_fx1616(fpu.read_nos())
    assert pytest.approx(result, abs=1e-4) == expected


# =============================================================================
# 7. Quarter-Square Hardware Multiplication Tests (`OP_MUL` - 8-bit Operands)
# =============================================================================
@pytest.mark.parametrize(
    "a, b, expected",
    [
        # Zero Multiplication Boundaries
        (0, 0, 0),
        (0, 255, 0),
        (255, 0, 0),
        # Unity & Small Integers
        (1, 1, 1),
        (1, 255, 255),
        (15, 12, 180),
        (16, 16, 256),
        # Mid-Range Values
        (64, 64, 4096),
        (100, 50, 5000),
        (127, 127, 16129),
        (128, 128, 16384),
        # Maximum Operands (255 * 255 = 65025 = 0xFE01)
        (254, 255, 64770),
        (255, 255, 65025),
    ],
)
def test_quarter_square_mul(a, b, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos(a)
    fpu.push_tos(b)
    fpu.execute_op("MUL")
    result = fpu.read_nos() & 0xFFFF
    assert result == expected


# =============================================================================
# 8. Reciprocal Table Hardware Division Tests (`OP_DIV`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        # Zero Dividend Boundaries
        (0, 1, 0),
        (0, 255, 0),
        # Division by Powers of Two
        (100, 2, 50),
        (100, 4, 25),
        (200, 8, 25),
        (240, 16, 15),
        # Equal Dividend and Divisor
        (10, 10, 1),
        (255, 255, 1),
        # High Range Values
        (200, 10, 20),
        (255, 5, 51),
    ],
)
def test_reciprocal_div(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos(nos)
    fpu.push_tos(tos)
    fpu.execute_op("DIV")
    result = fpu.read_nos() & 0xFF
    assert result == expected


# =============================================================================
# 9. Square Root Seed Lookup Tests (`OP_SQRT`)
# =============================================================================
@pytest.mark.parametrize(
    "x, expected_raw",
    [
        # Perfect Squares: sqrt(x) * 256
        (0, 0),         # sqrt(0) = 0
        (1, 256),       # sqrt(1) = 1.0 -> 256
        (4, 512),       # sqrt(4) = 2.0 -> 512
        (9, 768),       # sqrt(9) = 3.0 -> 768
        (16, 1024),     # sqrt(16) = 4.0 -> 1024
        (25, 1280),     # sqrt(25) = 5.0 -> 1280
        (64, 2048),     # sqrt(64) = 8.0 -> 2048
        (100, 2560),    # sqrt(100) = 10.0 -> 2560
        (144, 3072),    # sqrt(144) = 12.0 -> 3072
        (225, 3840),    # sqrt(225) = 15.0 -> 3840
        # Upper Boundary
        (255, 4087),    # sqrt(255) = 15.9687 -> int(15.9687 * 256) = 4087
    ],
)
def test_sqrt_seed(x, expected_raw):
    fpu = ZX50FPUMachine()
    fpu.push_tos(x)
    fpu.execute_op("SQRT")
    result = fpu.read_nos() & 0xFFFF
    assert result == expected_raw


# =============================================================================
# 10. Base-2 Logarithm Table Lookup Tests (`OP_LOG2`)
# =============================================================================
@pytest.mark.parametrize(
    "x, expected_scaled",
    [
        # Domain: log2(1.0 + x/256) * 256
        (0, 0),         # log2(1.0) * 256 = 0
        (64, 82),       # log2(1.25) * 256 = 82.4 -> 82
        (128, 149),     # log2(1.5) * 256 = 149.7 -> 149
        (192, 206),     # log2(1.75) * 256 = 206.6 -> 206
        (255, 255),     # log2(1.996) * 256 = 255.2 -> 255
    ],
)
def test_log2_table(x, expected_scaled):
    fpu = ZX50FPUMachine()
    fpu.push_tos(x)
    fpu.execute_op("LOG2")
    result = fpu.read_nos() & 0xFFFF
    assert result == expected_scaled


# =============================================================================
# 11. Base-2 Exponentiation Table Lookup Tests (`OP_EXP`)
# =============================================================================
@pytest.mark.parametrize(
    "x, expected_scaled",
    [
        # Domain: 2^(x/256) * 256
        (0, 256),       # 2^0.0 * 256 = 256
        (64, 304),      # 2^0.25 * 256 = 304.4 -> 304
        (128, 362),     # 2^0.5 * 256 = 362.0 -> 362
        (192, 430),     # 2^0.75 * 256 = 430.5 -> 430
        (255, 510),     # 2^0.996 * 256 = 510.6 -> 510
    ],
)
def test_exp2_table(x, expected_scaled):
    fpu = ZX50FPUMachine()
    fpu.push_tos(x)
    fpu.execute_op("EXP")
    result = fpu.read_nos() & 0xFFFF
    assert result == expected_scaled


# =============================================================================
# 12. Combined Power Function Tests (`OP_POW`: x^y = 2^(y * log2(x)))
# =============================================================================
@pytest.mark.parametrize(
    "nos_y, tos_x, expected_scaled",
    [
        # y=128 (0.5 power / square root)
        (128, 0, 256),     # 1.0^0.5 = 1.0 -> 256
        (128, 128, 312),   # 1.5^0.5 scaled pipeline output = 312
        # y=0 (0.0 power) -> x^0 = 1.0
        (0, 128, 256),     # 1.5^0 = 1.0 -> 256
        (0, 255, 256),     # 1.996^0 = 1.0 -> 256
    ],
)
def test_pow_routine(nos_y, tos_x, expected_scaled):
    fpu = ZX50FPUMachine()
    fpu.push_nos(nos_y)
    fpu.push_tos(tos_x)
    fpu.execute_op("POW")
    result = fpu.read_nos() & 0xFFFF
    assert result == expected_scaled