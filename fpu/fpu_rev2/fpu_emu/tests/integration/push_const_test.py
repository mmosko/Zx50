"""Integration tests for UserOpcode.PUSH_<CONST> operations executed via dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import Reg, StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, bits_to_f64, user_pop32, user_pop64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "opcode,expected,desc",
    [
        (UserOpcode.PUSH_PI_32, math.pi, "pi (f32)"),
        (UserOpcode.PUSH_E_32, math.e, "e (f32)"),
        (UserOpcode.PUSH_LN2_32, math.log(2), "ln(2) (f32)"),
        (UserOpcode.PUSH_LOG2E_32, math.log2(math.e), "log2(e) (f32)"),
        (UserOpcode.PUSH_LOG2_10_32, math.log2(10), "log2(10) (f32)"),
        (UserOpcode.PUSH_LOG10_2_32, math.log10(2), "log10(2) (f32)"),
        (UserOpcode.PUSH_SQRT2_32, math.sqrt(2), "sqrt(2) (f32)"),
        (UserOpcode.PUSH_INV_SQRT2_32, 1.0 / math.sqrt(2), "1/sqrt(2) (f32)"),
    ],
)
def test_push_const_f32(fpga: FpgaModel, opcode: UserOpcode, expected: float, desc: str) -> None:
    """Tests executing 32-bit PUSH_<CONST> via dispatcher: pushes float constant to TOS."""
    # Ensure AL has sentinel data to verify PUSH_const uses scratch register FL without clobbering AL
    sentinel = 0x12345678
    fpga.reg_file.al.write(sentinel)

    fpga.dispatcher.execute(opcode)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # AL must remain intact
    assert fpga.reg_file.al.read_int() == sentinel

    res_bits = user_pop32(fpga)
    res_float = bits_to_f32(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    assert pytest.approx(res_float, rel=1e-6) == expected, (
        f"Failed {desc}: got {res_float}, expected {expected}"
    )


@pytest.mark.parametrize(
    "opcode,expected,desc",
    [
        (UserOpcode.PUSH_PI_64, math.pi, "pi (f64)"),
        (UserOpcode.PUSH_E_64, math.e, "e (f64)"),
        (UserOpcode.PUSH_LN2_64, math.log(2), "ln(2) (f64)"),
        (UserOpcode.PUSH_LOG2E_64, math.log2(math.e), "log2(e) (f64)"),
        (UserOpcode.PUSH_LOG2_10_64, math.log2(10), "log2(10) (f64)"),
        (UserOpcode.PUSH_LOG10_2_64, math.log10(2), "log10(2) (f64)"),
        (UserOpcode.PUSH_SQRT2_64, math.sqrt(2), "sqrt(2) (f64)"),
        (UserOpcode.PUSH_INV_SQRT2_64, 1.0 / math.sqrt(2), "1/sqrt(2) (f64)"),
    ],
)
def test_push_const_f64(fpga: FpgaModel, opcode: UserOpcode, expected: float, desc: str) -> None:
    """Tests executing 64-bit PUSH_<CONST> via dispatcher: pushes double constant to TOS."""
    sentinel_lo = 0x12345678
    sentinel_hi = 0x9ABCDEF0
    fpga.reg_file.al.write(sentinel_lo)
    fpga.reg_file.ah.write(sentinel_hi)

    fpga.dispatcher.execute(opcode)

    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # AL and AH must remain intact
    assert fpga.reg_file.al.read_int() == sentinel_lo
    assert fpga.reg_file.ah.read_int() == sentinel_hi

    res_bits = user_pop64(fpga)
    res_float = bits_to_f64(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    assert pytest.approx(res_float, rel=1e-15) == expected, (
        f"Failed {desc}: got {res_float}, expected {expected}"
    )
