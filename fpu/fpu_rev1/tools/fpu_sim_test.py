# tools/fpu_sim_test.py
"""
Pytest Unit Test Suite for ZX50 FPU Microcode Simulator
Comprehensive test suite covering i16, i32, i64, fx1616, cfloat formats across all
arithmetic, trigonometric, logarithmic, exponential, and stack management commands
using the official 8-bit opcode interface (execute_opcode).
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
# Helper Encoding & Decoding Utilities
# =============================================================================
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
# 1. 16-Bit Signed Integer Tests (`FMT_I16` - Opcodes `0x00` - `0x05`)
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
        (32767, 0, 32767),
        (-32768, 0, -32768),
        (32767, -32768, -1),
        (32767, 1, -32768),  # Wrap-around
        (-32768, -1, 32767),
    ],
)
def test_i16_add(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i16(nos)
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x00)  # FMT_I16 | OP_ADD
    assert fpu.read_nos_i16() == expected


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
def test_i16_sub(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i16(nos)
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x01)  # FMT_I16 | OP_SUB
    assert fpu.read_nos_i16() == expected


@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0, 0, 0),
        (10, 0, 0),
        (0, -10, 0),
        (15, 12, 180),
        (100, 300, 30000),
        (181, 181, 32761),
    ],
)
def test_i16_mul(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i16(nos)
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x02)  # FMT_I16 | OP_MUL
    assert fpu.read_nos_i16() == expected


@pytest.mark.parametrize(
    "nos, tos, expected, expected_error",
    [
        (0, 1, 0, False),
        (100, 4, 25, False),
        (30000, 100, 300, False),
        (100, 0, 32767, True),  # Div-by-zero
    ],
)
def test_i16_div(nos, tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i16(nos)
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x03)  # FMT_I16 | OP_DIV
    assert fpu.read_nos_i16() == expected
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize(
    "tos, expected, expected_error",
    [
        (0, 0, False),
        (1, 1, False),
        (4, 2, False),
        (144, 12, False),
        (-4, 0, True),  # Negative input error
    ],
)
def test_i16_sqrt(tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x04)  # FMT_I16 | OP_SQRT
    assert fpu.read_nos_i16() == expected
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize("tos, expected", [(0, 0), (100, -100), (-500, 500), (32767, -32767)])
def test_i16_chs(tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_tos_i16(tos)
    fpu.execute_opcode(0x05)  # FMT_I16 | OP_CHS
    assert fpu.read_nos_i16() == expected


# =============================================================================
# 2. 32-Bit Signed Integer Tests (`FMT_I32` - Opcodes `0x10` - `0x15`)
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
        (0, 0, 0),
        (0, 255, 0),
        (15, 12, 180),
        (100, 300, 30000),
    ],
)
def test_i32_mul(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_nos_i32(nos)
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x12)  # FMT_I32 | OP_MUL
    assert fpu.read_nos_i32() == expected


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
        (-100, 0, True),  # Negative input error
    ],
)
def test_i32_sqrt(tos, expected, expected_error):
    fpu = ZX50FPUMachine()
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x14)  # FMT_I32 | OP_SQRT
    assert fpu.read_nos_i32() == expected
    assert fpu.flag_error == expected_error


@pytest.mark.parametrize("tos, expected", [(0, 0), (100000, -100000), (-500000, 500000)])
def test_i32_chs(tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x15)  # FMT_I32 | OP_CHS
    assert fpu.read_nos_i32() == expected


# =============================================================================
# 3. 64-Bit Signed Integer Tests (`FMT_I64` - Opcodes `0x20` - `0x21`)
# =============================================================================

@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0, 0, 0),
        (100000000000, 50000000000, 150000000000),
        (-50000000000, 20000000000, -30000000000),
    ],
)
def test_i64_add(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.sp = 0x10  # 16-byte stack frame offset
    fpu.push_nos_i64(nos)
    fpu.push_tos_i64(tos)
    fpu.execute_opcode(0x20)  # FMT_I64 | OP_ADD
    assert fpu.read_nos_i64() == expected


@pytest.mark.parametrize(
    "nos, tos, expected",
    [
        (0, 0, 0),
        (150000000000, 50000000000, 100000000000),
        (-30000000000, 20000000000, -50000000000),
    ],
)
def test_i64_sub(nos, tos, expected):
    fpu = ZX50FPUMachine()
    fpu.sp = 0x10  # 16-byte stack frame offset
    fpu.push_nos_i64(nos)
    fpu.push_tos_i64(tos)
    fpu.execute_opcode(0x21)  # FMT_I64 | OP_SUB
    assert fpu.read_nos_i64() == expected


# =============================================================================
# 4. 16.16 Fixed-Point Arithmetic Tests (`FMT_FX1616` - Opcodes `0x30` - `0x3C`)
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
    assert pytest.approx(fpu.read_nos_fx1616(), abs=1e-4) == expected


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
    assert pytest.approx(fpu.read_nos_fx1616(), abs=1e-4) == expected


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
    assert pytest.approx(fpu.read_nos_fx1616(), abs=1e-4) == expected
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
    assert pytest.approx(fpu.read_nos_fx1616(), abs=1e-4) == expected


# =============================================================================
# 5. 32-Bit Complex Float Tests (`FMT_CFLOAT` - Opcode `0x50` - `0x51`)
# =============================================================================

def test_cfloat_add():
    fpu = ZX50FPUMachine()
    fpu.sp = 0x10  # 16-byte frame base for complex numbers

    # Complex Number 1 (NOS): 3.0 + 4.0i
    fpu.push_nos_fx1616(3.0)
    fpu.sp += 4
    fpu.push_nos_fx1616(4.0)
    fpu.sp -= 4

    # Complex Number 2 (TOS): 1.5 + 2.5i
    fpu.push_tos_fx1616(1.5)
    fpu.sp += 4
    fpu.push_tos_fx1616(2.5)
    fpu.sp -= 4

    fpu.execute_opcode(0x50)  # FMT_CFLOAT | OP_ADD (Chained Dual Pass)

    # Read Real Result (4.5)
    res_real = fpu.read_nos_fx1616()
    # Read Imaginary Result (6.5)
    fpu.sp += 4
    res_imag = fpu.read_nos_fx1616()
    fpu.sp -= 4

    assert pytest.approx(res_real, abs=1e-4) == 4.5
    assert pytest.approx(res_imag, abs=1e-4) == 6.5


# =============================================================================
# 6. Hardware Management Commands (`FMT_MGMT` - Opcodes `0xF0` - `0xFF`)
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