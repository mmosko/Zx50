# tools/fpu_sim_test.py
"""
Pytest Unit Test Suite for ZX50 FPU Microcode Simulator
Tests I32 and FX1616 operations strictly via execute_opcode.
"""

import pytest
from fpu_sim import (
    ZX50FPUMachine,
    MGMT_CLR_STK,
    MGMT_POP_TOS,
    MGMT_DUP_TOS,
    MGMT_RESET,
)


# =============================================================================
# 1. 32-Bit Signed Integer Tests (`FMT_I32` - Opcodes `0x10` - `0x15`)
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
    "nos, tos, expected, expected_error",
    [
        (0, 1, 0, False),
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


@pytest.mark.parametrize("tos, expected", [(0, 0), (100000, -100000), (-500000, 500000)])
def test_i32_chs(tos, expected):
    fpu = ZX50FPUMachine()
    fpu.push_tos_i32(tos)
    fpu.execute_opcode(0x15)  # FMT_I32 | OP_CHS
    assert fpu.read_nos_i32() == expected


# =============================================================================
# 2. 16.16 Fixed-Point Arithmetic Tests (`FMT_FX1616` - Opcodes `0x30` - `0x35`)
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
