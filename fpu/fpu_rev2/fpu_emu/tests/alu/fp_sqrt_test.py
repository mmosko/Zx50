import math
import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.alu import fp_sqrt
from fpu_emu.dispatcher import Dispatcher
from fpu_emu.hardware import Hardware
from fpu_emu.memory import stack
from fpu_emu.memory.registers import Reg, StatusFlag, Registers
from fpu_emu.tests.testharness import RegTestHarness
from fpu_emu.user_opcodes import UserOpcode


class TestFpSqrtAlu:
    """Unit tests for fp_sqrt ALU primitives."""

    @pytest.mark.parametrize(
        "ea, expected_ea, expected_odd",
        [
            (127, 127, False),  # 2^0 -> 2^0
            (128, 127, True),   # 2^1 -> 2^0 * sqrt(2)
            (129, 128, False),  # 2^2 -> 2^1
            (126, 126, True),   # 2^-1 -> 2^-1 * sqrt(2)
            (125, 126, False),  # 2^-2 -> 2^-1
        ],
    )
    def test_sqrt_exp_f32(self, ea: int, expected_ea: int, expected_odd: bool):
        new_ea, is_odd = fp_sqrt.sqrt_exp_f32(ea)
        assert new_ea == expected_ea
        assert is_odd == expected_odd

    @pytest.mark.parametrize(
        "ea, expected_ea, expected_odd",
        [
            (1023, 1023, False),  # 2^0 -> 2^0
            (1024, 1023, True),   # 2^1 -> 2^0 * sqrt(2)
            (1025, 1024, False),  # 2^2 -> 2^1
            (1022, 1022, True),   # 2^-1 -> 2^-1 * sqrt(2)
            (1021, 1022, False),  # 2^-2 -> 2^-1
        ],
    )
    def test_sqrt_exp_f64(self, ea: int, expected_ea: int, expected_odd: bool):
        new_ea, is_odd = fp_sqrt.sqrt_exp_f64(ea)
        assert new_ea == expected_ea
        assert is_odd == expected_odd


class TestSqrtDispatcher:
    """End-to-end integration tests for SQRT_F32 and SQRT_F64 via Dispatcher."""

    @pytest.fixture
    def setup_dispatcher(self):
        hw = Hardware()
        alu = Alu(hw)
        dispatcher = Dispatcher(hw, alu)
        return hw, dispatcher

    @pytest.mark.parametrize(
        "val",
        [
            0.0,
            1.0,
            2.0,
            3.0,
            4.0,
            9.0,
            16.0,
            25.0,
            100.0,
            0.25,
            0.5,
            2000000.0,
            12345.67,
        ],
    )
    def test_sqrt_f32_success(self, setup_dispatcher, val: float):
        hw, dispatcher = setup_dispatcher
        reg = RegTestHarness(hw.reg)
        # Push 32-bit float onto operand stack
        raw = Registers.from_f32(val)
        reg.set(Reg.AL, raw)
        stack.push32(hw, Reg.AL)

        dispatcher.execute(UserOpcode.SQRT_F32)

        assert not hw.reg.get_flag(StatusFlag.ERR), "ERR flag should not be asserted"
        stack.pop32(hw, Reg.AL)
        res_bytes = reg.peek(Reg.AL)
        res_f32 = Registers.to_f32(res_bytes)
        expected = math.sqrt(val)
        assert res_f32 == pytest.approx(expected, rel=1e-6)

    def test_sqrt_f32_negative_domain_error(self, setup_dispatcher):
        hw, dispatcher = setup_dispatcher
        reg = RegTestHarness(hw.reg)
        # Push negative float
        raw = Registers.from_f32(-4.0)
        reg.set(Reg.AL, raw)
        stack.push32(hw, Reg.AL)

        dispatcher.execute(UserOpcode.SQRT_F32)

        assert hw.reg.get_flag(StatusFlag.ERR), "ERR flag should be asserted on negative input"

    def test_sqrt_f32_underflow(self, setup_dispatcher):
        hw, dispatcher = setup_dispatcher
        # Empty stack
        dispatcher.execute(UserOpcode.SQRT_F32)

        assert hw.reg.get_flag(StatusFlag.UNDERFLOW), "UNDERFLOW flag should be asserted"
        assert hw.reg.get_flag(StatusFlag.ERR), "ERR flag should be asserted on underflow"

    @pytest.mark.parametrize(
        "val",
        [
            0.0,
            1.0,
            2.0,
            3.0,
            4.0,
            9.0,
            16.0,
            25.0,
            100.0,
            0.25,
            0.5,
            2000000.0,
            12345.6789012345,
        ],
    )
    def test_sqrt_f64_success(self, setup_dispatcher, val: float):
        hw, dispatcher = setup_dispatcher
        reg = RegTestHarness(hw.reg)
        # Push 64-bit double onto operand stack
        raw = Registers.from_f64(val)
        reg.set(Reg.AX, raw)
        stack.push64(hw, Reg.AX)

        dispatcher.execute(UserOpcode.SQRT_F64)

        assert not hw.reg.get_flag(StatusFlag.ERR), "ERR flag should not be asserted"
        stack.pop64(hw, Reg.AX)
        res_bytes = reg.peek(Reg.AX)
        res_f64 = Registers.to_f64(res_bytes)
        expected = math.sqrt(val)
        assert res_f64 == pytest.approx(expected, rel=1e-12)

    def test_sqrt_f64_negative_domain_error(self, setup_dispatcher):
        hw, dispatcher = setup_dispatcher
        reg = RegTestHarness(hw.reg)
        # Push negative double
        raw = Registers.from_f64(-9.0)
        reg.set(Reg.AX, raw)
        stack.push64(hw, Reg.AX)

        dispatcher.execute(UserOpcode.SQRT_F64)

        assert hw.reg.get_flag(StatusFlag.ERR), "ERR flag should be asserted on negative input"

    def test_sqrt_f64_underflow(self, setup_dispatcher):
        hw, dispatcher = setup_dispatcher
        # Empty stack
        dispatcher.execute(UserOpcode.SQRT_F64)

        assert hw.reg.get_flag(StatusFlag.UNDERFLOW), "UNDERFLOW flag should be asserted"
        assert hw.reg.get_flag(StatusFlag.ERR), "ERR flag should be asserted on underflow"
