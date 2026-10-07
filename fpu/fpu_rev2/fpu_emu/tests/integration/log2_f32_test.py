"""Integration tests for UserOpcode.LOG2_F32 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        # Exact powers of 2
        (1.0, 0.0, "log2(1.0)"),
        (2.0, 1.0, "log2(2.0)"),
        (4.0, 2.0, "log2(4.0)"),
        (8.0, 3.0, "log2(8.0)"),
        (16.0, 4.0, "log2(16.0)"),
        (1024.0, 10.0, "log2(1024.0)"),
        (1048576.0, 20.0, "log2(1048576.0)"),
        (0.5, -1.0, "log2(0.5)"),
        (0.25, -2.0, "log2(0.25)"),
        (0.125, -3.0, "log2(0.125)"),
        # General positive numbers
        (3.0, math.log2(3.0), "log2(3.0)"),
        (5.0, math.log2(5.0), "log2(5.0)"),
        (10.0, math.log2(10.0), "log2(10.0)"),
        (100.0, math.log2(100.0), "log2(100.0)"),
        (1.41421356, math.log2(1.41421356), "log2(sqrt(2))"),
        (1.5, math.log2(1.5), "log2(1.5)"),
        (0.70710678, math.log2(0.70710678), "log2(1/sqrt(2))"),
        (0.1, math.log2(0.1), "log2(0.1)"),
        (0.01, math.log2(0.01), "log2(0.01)"),
        (0.001, math.log2(0.001), "log2(0.001)"),
        # Dynamic range
        (1e-10, math.log2(1e-10), "log2(1e-10)"),
        (1e-20, math.log2(1e-20), "log2(1e-20)"),
        (1e10, math.log2(1e10), "log2(1e10)"),
        (1e20, math.log2(1e20), "log2(1e20)"),
        (1e30, math.log2(1e30), "log2(1e30)"),
    ],
)
def test_user_opcode_log2_f32(fpga: FpgaModel, x: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.LOG2_F32 via dispatcher: computes log2(x)."""
    user_push32(fpga, f32_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.LOG2_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    assert pytest.approx(res_float, rel=1e-5, abs=1e-6) == expected, (
        f"Failed {desc}: got {res_float}, expected {expected}"
    )


@pytest.mark.parametrize(
    "x,desc",
    [
        (0.0, "log2(0.0)"),
        (-0.0, "log2(-0.0)"),
        (-1.0, "log2(-1.0)"),
        (-10.0, "log2(-10.0)"),
        (-0.5, "log2(-0.5)"),
        (float("-inf"), "log2(-inf)"),
    ],
)
def test_log2_f32_domain_error(fpga: FpgaModel, x: float, desc: str) -> None:
    """Tests that x <= 0 asserts ERR and aborts push (domain error)."""
    user_push32(fpga, f32_to_bits(x))
    fpga.dispatcher.execute(UserOpcode.LOG2_F32)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR), f"Expected ERR for {desc}"


def test_log2_f32_pos_inf(fpga: FpgaModel) -> None:
    """Tests that log2(+inf) == +inf."""
    user_push32(fpga, f32_to_bits(float("inf")))
    fpga.dispatcher.execute(UserOpcode.LOG2_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert math.isinf(res_float) and res_float > 0


def test_log2_f32_nan(fpga: FpgaModel) -> None:
    """Tests that log2(nan) == nan."""
    user_push32(fpga, f32_to_bits(float("nan")))
    fpga.dispatcher.execute(UserOpcode.LOG2_F32)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert math.isnan(res_float)


def test_log2_f32_stack_underflow(fpga: FpgaModel) -> None:
    """Tests executing LOG2_F32 on an empty stack asserts UNDERFLOW and ERR."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.LOG2_F32)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.sp.read_int() == 0
