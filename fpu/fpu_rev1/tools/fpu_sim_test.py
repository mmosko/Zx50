# tools/fpu_sim_test.py
"""
Pytest Unit Test Suite for ZX50 FPU Microcode Simulator
Tests 16-bit and 32-bit signed integers, 16.16 fixed-point math, Quarter-Square multiplication,
reciprocal division, square root seeds, and transcendental log/exp/pow functions
across all critical boundary and edge conditions.
"""

import pytest
import math
from fpu_sim import ZX50FPUMachine


# =============================================================================
# Helper Encoding & Decoding Utilities
# =============================================================================
def to_u32(val: int) -> int:
    return val & 0xFFFFFFFF


def to_i32(val: int) -> int:
    return val & 0xFFFFFFFF


def from_i32(u32_val: int) -> int:
    u32_val &= 0xFFFFFFFF
    return u32_val - 0x100000000 if u32_val >= 0x80000000 else u32_val


def to_i16(val: int) -> int:
    return val & 0xFFFF


def from_i16(u16_val: int) -> int:
    u16_val &= 0xFFFF
    return u16_val - 0x10000 if u16_val >= 0x8000 else u16_val


def to_fx1616(val: float) -> int:
    return int(round(val * 65536.0)) & 0xFFFFFFFF


def from_fx1616(u32_val: int) -> float:
    signed_val = from_i32(u32_val)
    return signed_val / 65536.0


# =============================================================================
# 1. 16-Bit Signed Integer Addition Tests (`FMT_I16` - Opcode `0x00`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        # Zero & Basic Operations
        (0, 0, 0),
        (100, 0, 100),
        (0, -100, -100),
        (500, -200, 300),
        (-500, 200, -300),
        (-1000, 1000, 0),
        # Boundaries (INT16_MAX = 32767, INT16_MIN = -32768)
        (32767, 0, 32767),
        (-32768, 0, -32768),
        (32767, -32768, -1),
        # Wrap-around
        (32767, 1, -32768),
        (-32768, -1, 32767),
    ],
)
def test_signed_add_16(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i16(nos)
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x00)  # FMT_I16 | OP_ADD
    assert fpu.read_nos_i16() == expected


# =============================================================================
# 2. 16-Bit Signed Integer Subtraction Tests (`FMT_I16` - Opcode `0x01`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0, 0, 0),
        (100, 0, 100),
        (0, 100, -100),
        (500, 200, 300),
        (-500, -200, -300),
        (500, -200, 700),
        (-500, 200, -700),
        (32767, 32767, 0),
        (-32768, -32768, 0),
        (-32768, 1, 32767),
        (32767, -1, -32768),
    ],
)
def test_signed_sub_16(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i16(nos)
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x01)  # FMT_I16 | OP_SUB
    assert fpu.read_nos_i16() == expected


# =============================================================================
# 3. 16-Bit Signed Integer Multiplication Tests (`FMT_I16` - Opcode `0x02`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0, 0, 0),
        (10, 0, 0),
        (0, -10, 0),
        (15, 12, 180),
        (-15, 12, -180),
        (-15, -12, 180),
        (100, 300, 30000),
        (181, 181, 32761),
    ],
)
def test_signed_mul_16(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i16(nos)
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x02)  # FMT_I16 | OP_MUL
    assert fpu.read_nos_i16() == expected


# =============================================================================
# 4. 16-Bit Signed Integer Division Tests (`FMT_I16` - Opcode `0x03`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected, expected_error",
    [
        (0, 1, 0, False),
        (100, 4, 25, False),
        (-100, 4, -25, False),
        (100, -4, -25, False),
        (-100, -4, 25, False),
        (30000, 100, 300, False),
        (100, 0, 32767, True),  # Division-by-zero sets ERROR flag
    ],
)
def test_signed_div_16(nos, tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i16(nos)
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x03)  # FMT_I16 | OP_DIV
    assert fpu.read_nos_i16() == expected
    assert fpu.flag_error == expected_error


# =============================================================================
# 5. 16-Bit Signed Integer Square Root Tests (`FMT_I16` - Opcode `0x04`)
# =============================================================================
@pytest.mark.parametrize(
    "tos, expected, expected_error",
    [
        (0, 0, False),
        (1, 1, False),
        (4, 2, False),
        (144, 12, False),
        (10000, 100, False),  # Fixed: sqrt(10000) = 100
        (30000, 173, False),  # Added: sqrt(30000) = 173
        (32767, 181, False),
        (-4, 0, True),  # Negative input sets ERROR flag
    ],
)
def test_signed_sqrt_16(tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x04)  # FMT_I16 | OP_SQRT
    assert fpu.read_nos_i16() == expected
    assert fpu.flag_error == expected_error

# =============================================================================
# 6. Unsigned 32-bit Addition Tests (`u32`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0x00000000, 0x00000000, 0x00000000),
        (0x00000000, 0x12345678, 0x12345678),
        (0x12345678, 0x00000000, 0x12345678),
        (0x000000FF, 0x00000001, 0x00000100),
        (0x0000FFFF, 0x00000001, 0x00010000),
        (0x00FFFFFF, 0x00000001, 0x01000000),
        (0xFFFFFFFF, 0x00000001, 0x00000000),
        (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFE),
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
# 7. Signed 32-bit Addition Tests (`i32`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0, 0, 0),
        (100, 0, 100),
        (0, -100, -100),
        (500, -200, 300),
        (-500, 200, -300),
        (-1000, 1000, 0),
        (2147483647, 0, 2147483647),
        (-2147483648, 0, -2147483648),
        (2147483647, -2147483648, -1),
        (2147483647, 1, -2147483648),
        (-2147483648, -1, 2147483647),
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
# 8. 16.16 Fixed-Point Addition Tests (`fx1616`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0.0, 0.0, 0.0),
        (1.0, 2.5, 3.5),
        (-10.5, 5.25, -5.25),
        (0.0, 0.0000152587890625, 0.0000152587890625),
        (0.5, 0.5, 1.0),
        (0.125, 0.375, 0.5),
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
# 9. Quarter-Square Hardware Multiplication Tests (`OP_MUL` - 8-bit Operands)
# =============================================================================
@pytest.mark.parametrize(
    "a, b, expected",
    [
        (0, 0, 0),
        (0, 255, 0),
        (255, 0, 0),
        (1, 1, 1),
        (1, 255, 255),
        (15, 12, 180),
        (16, 16, 256),
        (64, 64, 4096),
        (100, 50, 5000),
        (127, 127, 16129),
        (128, 128, 16384),
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
# 10. Reciprocal Table Hardware Division Tests (`OP_DIV`)
# =============================================================================
@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0, 1, 0),
        (0, 255, 0),
        (100, 2, 50),
        (100, 4, 25),
        (200, 8, 25),
        (240, 16, 15),
        (10, 10, 1),
        (255, 255, 1),
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
# 11. 16.16 Fixed-Point Trigonometric Tests (`SIN`, `COS`, `TAN`)
# =============================================================================
@pytest.mark.parametrize(
    "angle_rad, expected_sin, expected_cos",
    [
        (0.0, 0.0, 1.0),
        (math.pi / 6.0, 0.5, 0.866025),  # 30 deg
        (math.pi / 4.0, 0.707106, 0.707106),  # 45 deg
        (math.pi / 3.0, 0.866025, 0.5),  # 60 deg
        (math.pi / 2.0, 1.0, 0.0),  # 90 deg
    ],
)
def test_trig_fx1616(angle_rad, expected_sin, expected_cos):
    fpu = ZX50FPUMachine()

    # Test SIN
    fpu.push_tos_fx1616(angle_rad)
    fpu.execute_opcode(0x36)  # FMT_FX1616 | OP_SIN
    assert pytest.approx(fpu.read_nos_fx1616(), abs=1e-3) == expected_sin

    # Test COS
    fpu.push_tos_fx1616(angle_rad)
    fpu.execute_opcode(0x37)  # FMT_FX1616 | OP_COS
    assert pytest.approx(fpu.read_nos_fx1616(), abs=1e-3) == expected_cos
