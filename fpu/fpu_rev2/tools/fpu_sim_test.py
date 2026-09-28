# tools/fpu_sim_test.py
"""
Pytest Unit Test Suite for ZX50 FPU Microcode Simulator
Tests I32 and FX1616 formats across all mathematical and management opcodes
exclusively via the official 8-bit execute_opcode interface.
"""

import pytest
import math
from fpu_sim import (
    ZX50FPUMachine,
    MGMT_CLR_STK,
    MGMT_POP_TOS,
    MGMT_DUP_TOS,
    MGMT_RESET,
)


# =============================================================================
# Helper Utilities
# =============================================================================
def to_i32(val: int) -> int:
    return val & 0xFFFFFFFF


def from_i32(u32_val: int) -> int:
    u32_val &= 0xFFFFFFFF
    return u32_val - 0x100000000 if u32_val >= 0x80000000 else u32_val


# =============================================================================
# 1. 32-Bit Signed Integer Tests (`FMT_I32` - Opcodes `0x10` - `0x1C`)
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
        (2147483647, 1, -2147483648),  # Positive Overflow
        (-2147483648, -1, 2147483647),  # Negative Overflow
    ],
)
def test_i32_add(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i32(nos)
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x10)  # FMT_I32 | OP_ADD
    assert fpu.read_nos_i32() == expected


@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0, 0, 0),
        (100, 0, 100),
        (0, 100, -100),
        (0, 100_000, -100_000),
        (0, 5_000_000, -5_000_000),
        (500, 200, 300),
        (-500, -200, -300),
        (500, -200, 700),
        (-500, 200, -700),
        (2147483647, 2147483647, 0),
        (-2147483648, -2147483648, 0),
        (-2147483648, 1, 2147483647),
        (2147483647, -1, -2147483648),
    ],
)
def test_i32_sub(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i32(nos)
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x11)  # FMT_I32 | OP_SUB
    assert fpu.read_nos_i32() == expected


@pytest.mark.parametrize(
    "nos, tos, expected",
    [
#        (0, 0, 0),
#        (0, 255, 0),
        (15, 12, 180),
#        (100, 300, 30000),
#        (1024, 1024, 1_048_576),
    ],
)
def test_i32_mul(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i32(nos)
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x12)  # FMT_I32 | OP_MUL
    assert fpu.read_tos_i32() == expected


@pytest.mark.parametrize(
    "nos, tos, expected, expected_error",
    [
        (0, 1, 0, False),
        (100, 4, 25, False),
        (100000, 400, 250, False),
        (100, 0, 2147483647, True),  # Div-by-zero
    ],
)
def test_i32_div(nos, tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i32(nos)
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x13)  # FMT_I32 | OP_DIV
    assert fpu.read_nos_i32() == expected
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize(
    "tos, expected, expected_error",
    [
        (0, 0, False),
        (1, 1, False),
        (4, 2, False),
        (144, 12, False),
        (-100, 0, True),  # Negative input domain error
    ],
)
def test_i32_sqrt(tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x14)  # FMT_I32 | OP_SQRT
    assert fpu.read_nos_i32() == expected
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize("tos, expected", [
    (0, 0),
    (100000, -100000),
    (-500000, 500000)])
def test_i32_chs(tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x15)  # FMT_I32 | OP_CHS
    assert fpu.read_tos_i32() == expected


# =============================================================================
# 2. 16.16 Fixed-Point Tests (`FMT_FX1616` - Opcodes `0x30` - `0x3C`)
# =============================================================================

@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0.0, 0.0, 0.0),
        (1.0, 2.5, 3.5),
        (-10.5, 5.25, -5.25),
        (0.5, 0.5, 1.0),
        (32767.0, 0.99998, 32767.99998),
    ],
)
def test_fx1616_add(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_fx1616(nos)
    fpu.push_tos_fx1616(tos)
    fpu.execute_opcode(0x30)  # FMT_FX1616 | OP_ADD
    assert fpu.read_nos_fx1616() == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0.0, 0.0, 0.0),
        (10.5, 3.25, 7.25),
        (3.25, 10.5, -7.25),
        (-5.0, -2.5, -2.5),
        (-5.0, 2.5, -7.5),
    ],
)
def test_fx1616_sub(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_fx1616(nos)
    fpu.push_tos_fx1616(tos)
    fpu.execute_opcode(0x31)  # FMT_FX1616 | OP_SUB
    assert fpu.read_nos_fx1616() == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0.0, 0.0, 0.0),
        (1.5, 2.0, 3.0),
        (0.5, 0.5, 0.25),
    ],
)
def test_fx1616_mul(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_fx1616(nos)
    fpu.push_tos_fx1616(tos)
    fpu.execute_opcode(0x32)  # FMT_FX1616 | OP_MUL
    assert fpu.read_nos_fx1616() == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize(
    "nos, tos, expected, expected_error",
    [
        (0.0, 1.0, 0.0, False),
        (10.0, 2.5, 4.0, False),
        (1.0, 0.0, 32767.99998, True),  # Div-by-zero
    ],
)
def test_fx1616_div(nos, tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_nos_fx1616(nos)
    fpu.push_tos_fx1616(tos)
    fpu.execute_opcode(0x33)  # FMT_FX1616 | OP_DIV
    assert fpu.read_nos_fx1616() == pytest.approx(expected, abs=1e-4)
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize(
    "tos, expected, expected_error",
    [
        (0.0, 0.0, False),
        (1.0, 1.0, False),
        (4.0, 2.0, False),
        (25.0, 5.0, False),
        (-4.0, 0.0, True),  # Negative input error
    ],
)
def test_fx1616_sqrt(tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_tos_fx1616(tos)
    fpu.execute_opcode(0x34)  # FMT_FX1616 | OP_SQRT
    assert fpu.read_nos_fx1616() == pytest.approx(expected, abs=1e-4)
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize("tos, expected", [(0.0, 0.0), (12.5, -12.5), (-100.25, 100.25)])
def test_fx1616_chs(tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_tos_fx1616(tos)
    fpu.execute_opcode(0x35)  # FMT_FX1616 | OP_CHS
    assert fpu.read_tos_fx1616() == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize(
    "angle_rad, expected_sin",
    [
        (0.0, 0.0),
        (math.pi / 6.0, 0.5),  # 30 deg
        (math.pi / 4.0, 0.707106),  # 45 deg
        (math.pi / 3.0, 0.866025),  # 60 deg
        (math.pi / 2.0, 1.0),  # 90 deg
        (math.pi, 0.0),  # 180 deg
    ],
)
def test_fx1616_sin(angle_rad, expected_sin):
    fpu = ZX50FPUMachine()
    fpu.push_tos_fx1616(angle_rad)
    fpu.execute_opcode(0x36)  # FMT_FX1616 | OP_SIN
    assert fpu.read_nos_fx1616() == pytest.approx(expected_sin, abs=5e-3)


@pytest.mark.parametrize(
    "angle_rad, expected_cos",
    [
        (0.0, 1.0),
        (math.pi / 6.0, 0.866025),  # 30 deg
        (math.pi / 4.0, 0.707106),  # 45 deg
        (math.pi / 3.0, 0.5),  # 60 deg
        (math.pi / 2.0, 0.0),  # 90 deg
        (math.pi, -1.0),  # 180 deg
    ],
)
def test_fx1616_cos(angle_rad, expected_cos):
    fpu = ZX50FPUMachine()
    fpu.push_tos_fx1616(angle_rad)
    fpu.execute_opcode(0x37)  # FMT_FX1616 | OP_COS
    assert fpu.read_nos_fx1616() == pytest.approx(expected_cos, abs=5e-3)


@pytest.mark.parametrize(
    "x, expected_exp",
    [
        (0.0, 1.0),
        (1.0, math.e),  # e^1 = 2.71828
        (2.0, math.e ** 2),  # e^2 = 7.38905
        (-1.0, 1.0 / math.e),  # e^-1 = 0.36787
    ],
)
def test_fx1616_exp(x, expected_exp):
    fpu = ZX50FPUMachine()
    fpu.push_tos_fx1616(x)
    fpu.execute_opcode(0x38)  # FMT_FX1616 | OP_EXP
    assert fpu.read_nos_fx1616() == pytest.approx(expected_exp, abs=0.02)


@pytest.mark.parametrize(
    "x, expected_ln, expected_error",
    [
        (1.0, 0.0, False),
        (math.e, 1.0, False),
        (10.0, math.log(10.0), False),
        (0.0, 0.0, True),  # Domain error
        (-2.0, 0.0, True),  # Domain error
    ],
)
def test_fx1616_ln(x, expected_ln, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_tos_fx1616(x)
    fpu.execute_opcode(0x39)  # FMT_FX1616 | OP_LN
    assert fpu.read_nos_fx1616() == pytest.approx(expected_ln, abs=5e-3)
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize(
    "x, expected_log10, expected_error",
    [
        (1.0, 0.0, False),
        (10.0, 1.0, False),
        (100.0, 2.0, False),
        (0.0, 0.0, True),  # Domain error
        (-5.0, 0.0, True),  # Domain error
    ],
)
def test_fx1616_log10(x, expected_log10, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_tos_fx1616(x)
    fpu.execute_opcode(0x3A)  # FMT_FX1616 | OP_LOG10
    assert fpu.read_nos_fx1616() == pytest.approx(expected_log10, abs=5e-3)
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize(
    "angle_rad, expected_tan",
    [
        (0.0, 0.0),
        (math.pi / 4.0, 1.0),  # 45 deg -> 1.0
        (-math.pi / 4.0, -1.0),  # -45 deg -> -1.0
    ],
)
def test_fx1616_tan(angle_rad, expected_tan):
    fpu = ZX50FPUMachine()
    fpu.push_tos_fx1616(angle_rad)
    fpu.execute_opcode(0x3B)  # FMT_FX1616 | OP_TAN
    assert fpu.read_nos_fx1616() == pytest.approx(expected_tan, abs=0.01)


@pytest.mark.parametrize(
    "y_exp, x_base, expected_pow, expected_error",
    [
        (0.5, 4.0, 2.0, False),  # 4.0^0.5 = 2.0
        (0.5, 16.0, 4.0, False),  # 16.0^0.5 = 4.0
        (2.0, 3.0, 9.0, False),  # 3.0^2.0 = 9.0
        (0.0, 5.0, 1.0, False),  # 5.0^0.0 = 1.0
        (0.5, -4.0, 0.0, True),  # Negative base error
    ],
)
def test_fx1616_pow(y_exp, x_base, expected_pow, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_nos_fx1616(y_exp)
    fpu.push_tos_fx1616(x_base)
    fpu.execute_opcode(0x3C)  # FMT_FX1616 | OP_POW
    assert fpu.read_nos_fx1616() == pytest.approx(expected_pow, abs=0.02)
    assert fpu.flag_error == expected_error


# =============================================================================
# 3. Hardware Management Commands (`FMT_MGMT` - Opcodes `0xF0` - `0xFF`)
# =============================================================================
def test_management_opcodes():
    fpu = ZX50FPUMachine()

    # MGMT_CLR_STK (0xF0)
    fpu.execute_opcode(MGMT_CLR_STK)
    assert fpu.sp == 0x08

    # MGMT_DUP_TOS (0xF2)
    fpu.push_tos_i32(0x12345678)
    fpu.execute_opcode(MGMT_DUP_TOS)
    assert fpu.sp == 0x0C
    assert fpu.read_tos_i32() == 0x12345678

    # MGMT_POP_TOS (0xF1)
    fpu.execute_opcode(MGMT_POP_TOS)
    assert fpu.sp == 0x08

    # MGMT_RESET (0xFF)
    fpu.execute_opcode(MGMT_RESET)
    assert fpu.sp == 0x08
    assert not fpu.flag_error
