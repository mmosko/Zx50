"""Integration tests for CP_MEMx_TOS, CP_TOS_MEMx, and ZERO_MEM executed via dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize("slot", list(range(16)))
def test_cp_mem_tos_and_cp_tos_mem(fpga: FpgaModel, slot: int) -> None:
    """Tests storing TOS into slot (CP_MEMx_TOS) and reading slot to TOS (CP_TOS_MEMx)."""
    test_val = 0x1000A000 + slot * 0x1111

    # 1. Push test value to stack
    user_push32(fpga, test_val)
    assert fpga.reg_file.sp.read_int() == 1

    # 2. Store to user slot `slot` (0xD0 + slot)
    cp_mem_tos_op = UserOpcode(0xD0 + slot)
    fpga.dispatcher.execute(cp_mem_tos_op)

    # Stack should be popped
    assert fpga.reg_file.sp.read_int() == 0
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # 3. Read back from slot `slot` (0xE0 + slot)
    cp_tos_mem_op = UserOpcode(0xE0 + slot)
    fpga.dispatcher.execute(cp_tos_mem_op)

    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res = user_pop32(fpga)
    assert res == test_val
    assert fpga.reg_file.sp.read_int() == 0

    # 4. Verify reading again produces the same value (slot is not consumed)
    fpga.dispatcher.execute(cp_tos_mem_op)
    assert fpga.reg_file.sp.read_int() == 1
    res2 = user_pop32(fpga)
    assert res2 == test_val


def test_cp_mem_tos_underflow(fpga: FpgaModel) -> None:
    """Tests CP_MEMx_TOS underflow when stack is empty; memory slot must not be overwritten."""
    # Pre-populate slot 3 with known value
    user_push32(fpga, 0xCAFEBABE)
    fpga.dispatcher.execute(UserOpcode.CP_MEM3_TOS)
    assert fpga.reg_file.sp.read_int() == 0

    # Stack is now empty: attempt to store to slot 3
    fpga.dispatcher.execute(UserOpcode.CP_MEM3_TOS)

    # Must flag UNDERFLOW and ERR
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # Slot 3 must remain unmodified (0xCAFEBABE)
    fpga.dispatcher.execute(UserOpcode.CP_TOS_MEM3)
    val = user_pop32(fpga)
    assert val == 0xCAFEBABE


def test_cp_tos_mem_overflow(fpga: FpgaModel) -> None:
    """Tests CP_TOS_MEMx overflow when stack is full (SP=127)."""
    # Set SP to maximum capacity (127)
    fpga.reg_file.sp.write(127)
    assert fpga.reg_file.sp.read_int() == 127

    # Attempt to push from memory slot 0
    fpga.dispatcher.execute(UserOpcode.CP_TOS_MEM0)

    # Must flag OVERFLOW and ERR
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.sp.read_int() == 127


def test_zero_mem(fpga: FpgaModel) -> None:
    """Tests ZERO_MEM clears all 16 user storage memory slots to zero."""
    # Populate all 16 slots with non-zero values
    for slot in range(16):
        user_push32(fpga, 0x12340000 + slot)
        fpga.dispatcher.execute(UserOpcode(0xD0 + slot))
    assert fpga.reg_file.sp.read_int() == 0

    # Execute ZERO_MEM
    fpga.dispatcher.execute(UserOpcode.ZERO_MEM)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # Verify all 16 slots are now zero
    for slot in range(16):
        fpga.dispatcher.execute(UserOpcode(0xE0 + slot))
        val = user_pop32(fpga)
        assert val == 0, f"Slot {slot} was not cleared to 0 (got {hex(val)})"
