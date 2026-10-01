"""Unit and integration tests for Dispatcher and microcode sequencer."""

import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.dispatcher import Dispatcher
from fpu_emu.hardware import Hardware
from fpu_emu.memory import stack
from fpu_emu.memory.registers import Reg, StatusFlag, Registers
from fpu_emu.tests.testharness import RegTestHarness
from fpu_emu.micro_opcodes import MicroInstruction, MicroOp
from fpu_emu.user_opcodes import UserOpcode


def test_dispatcher_mode_commands():
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    assert not disp.batch_mode
    assert disp.blocking_mode

    # SET_BATCH
    disp.execute(UserOpcode.SET_BATCH)
    assert disp.batch_mode is True

    # SET_IMMEDIATE
    disp.execute(UserOpcode.SET_IMMEDIATE)
    assert disp.batch_mode is False

    # SET_NONBLOCKING
    disp.execute(UserOpcode.SET_NONBLOCKING)
    assert disp.blocking_mode is False

    # SET_BLOCKING
    disp.execute(UserOpcode.SET_BLOCKING)
    assert disp.blocking_mode is True

    # CLEAR_STACK
    hw.reg.sp = 16
    disp.execute(UserOpcode.CLEAR_STACK)
    assert hw.reg.sp == 0

    # RESET
    hw.clock.tick(100)
    disp.execute(UserOpcode.RESET)
    assert hw.clock.cycles == 0
    assert not disp.batch_mode
    assert disp.blocking_mode


def test_add_i32_immediate_execution():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Push 15 and 25 onto stack
    reg.set(Reg.AL, Registers.from_int(15, 4))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_int(25, 4))
    stack.push32(hw, Reg.AL)
    assert hw.reg.sp == 8

    start_cycles = hw.clock.cycles
    disp.execute(UserOpcode.ADD_I32)
    assert hw.clock.cycles > start_cycles

    # Stack should now have 1 item (result = 40)
    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.DL)
    assert Registers.to_int(reg.peek(Reg.DL)) == 40
    assert not hw.reg.get_flag(StatusFlag.BUSY)
    assert not hw.reg.get_flag(StatusFlag.ERR)


def test_sub_i32_immediate_execution():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Stack: Push 50 (first operand), then Push 20 (second operand)
    # Result: 50 - 20 = 30
    reg.set(Reg.AL, Registers.from_int(50, 4))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_int(20, 4))
    stack.push32(hw, Reg.AL)

    disp.execute(UserOpcode.SUB_I32)

    stack.pop32(hw, Reg.DL)
    assert Registers.to_int(reg.peek(Reg.DL)) == 30


def test_add_i64_immediate_execution():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    val_a = 0x00000001FFFFFFFF
    val_b = 0x0000000000000001
    reg.set(Reg.AX, Registers.from_int(val_a, 8))
    stack.push64(hw, Reg.AX)
    reg.set(Reg.AX, Registers.from_int(val_b, 8))
    stack.push64(hw, Reg.AX)

    disp.execute(UserOpcode.ADD_I64)

    assert hw.reg.sp == 8
    stack.pop64(hw, Reg.DX)
    assert Registers.to_int(reg.peek(Reg.DX)) == 0x0000000200000000


def test_underflow_triggers_trap():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Only 1 item on stack; ADD_I32 requires 2 operands
    reg.set(Reg.AL, Registers.from_int(10, 4))
    stack.push32(hw, Reg.AL)

    disp.execute(UserOpcode.ADD_I32)

    assert hw.reg.get_flag(StatusFlag.UNDERFLOW) is True
    assert hw.reg.get_flag(StatusFlag.ERR) is True


def test_batch_mode_queue_and_execution():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Put operands on stack: 10, 20, 30
    # Operations: ADD_I32 (10+20=30), then ADD_I32 (30+30=60)
    reg.set(Reg.AL, Registers.from_int(10, 4))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_int(20, 4))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_int(30, 4))
    stack.push32(hw, Reg.AL)

    # Enable batch mode
    disp.execute(UserOpcode.SET_BATCH)
    assert disp.batch_mode is True

    # Queue two ADD_I32 commands
    disp.execute(UserOpcode.ADD_I32)
    disp.execute(UserOpcode.ADD_I32)
    assert hw.reg.osp == 2  # 2 commands queued

    # Stack should still have all 3 items untouched
    assert hw.reg.sp == 12

    # Execute batch
    disp.execute(UserOpcode.EXEC_BATCH)

    # Queue should be cleared
    assert hw.reg.osp == 0
    # Final result on stack should be 60
    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.AL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 60


def test_mul_i32_immediate_execution():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Push 6 and 7 onto stack -> 6 * 7 = 42
    reg.set(Reg.AL, Registers.from_int(6, 4))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_int(7, 4))
    stack.push32(hw, Reg.AL)

    disp.execute(UserOpcode.MUL_I32)

    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.DL)
    assert Registers.to_int(reg.peek(Reg.DL)) == 42


def test_mul_i64_immediate_execution():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Push 1000 and -2000 onto stack -> -2000000
    reg.set(Reg.AX, Registers.from_int(1000, 8))
    stack.push64(hw, Reg.AX)
    reg.set(Reg.AX, Registers.from_int(-2000 & 0xFFFFFFFFFFFFFFFF, 8))
    stack.push64(hw, Reg.AX)

    disp.execute(UserOpcode.MUL_I64)

    assert hw.reg.sp == 8
    stack.pop64(hw, Reg.DX)
    res = Registers.to_int(reg.peek(Reg.DX))
    expected = (-2000000) & 0xFFFFFFFFFFFFFFFF
    assert res == expected


# =============================================================================
# Floating-Point F32 Tests (ADD_F32, SUB_F32)
# =============================================================================
@pytest.mark.parametrize(
    "val_a,val_b,expected,desc",
    [
        (1.0, 1.0, 2.0, "1.0 + 1.0"),
        (1.5, 2.5, 4.0, "1.5 + 2.5"),
        (100.0, 0.5, 100.5, "100.0 + 0.5"),
        (-3.0, -4.0, -7.0, "-3.0 + -4.0"),
        (1.0, -0.75, 0.25, "1.0 + -0.75"),
        (0.75, -1.0, -0.25, "0.75 + -1.0"),
        (1.0, -1.0, 0.0, "1.0 + -1.0 (exact cancellation)"),
        (0.0, 5.0, 5.0, "0.0 + 5.0"),
        (5.0, 0.0, 5.0, "5.0 + 0.0"),
        (0.0, 0.0, 0.0, "0.0 + 0.0"),
        (-2.5, 2.5, 0.0, "-2.5 + 2.5 (cancellation)"),
        (12.34, 56.78, 69.12, "12.34 + 56.78"),
    ],
)
def test_add_f32_execution(val_a, val_b, expected, desc):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Push operand A, then operand B
    reg.set(Reg.AL, Registers.from_f32(val_a))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_f32(val_b))
    stack.push32(hw, Reg.AL)

    disp.execute(UserOpcode.ADD_F32)

    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.AL)
    result = Registers.to_f32(reg.peek(Reg.AL))
    assert pytest.approx(result, rel=1e-5) == expected, f"Failed {desc}: got {result}, expected {expected}"
    assert not hw.reg.get_flag(StatusFlag.ERR)


@pytest.mark.parametrize(
    "val_a,val_b,expected,desc",
    [
        (5.0, 3.0, 2.0, "5.0 - 3.0"),
        (3.0, 5.0, -2.0, "3.0 - 5.0"),
        (5.0, 5.0, 0.0, "5.0 - 5.0 (exact cancellation)"),
        (10.0, -5.0, 15.0, "10.0 - -5.0"),
        (-10.0, 5.0, -15.0, "-10.0 - 5.0"),
        (-10.0, -5.0, -5.0, "-10.0 - -5.0"),
        (0.0, 5.0, -5.0, "0.0 - 5.0"),
        (5.0, 0.0, 5.0, "5.0 - 0.0"),
        (0.0, 0.0, 0.0, "0.0 - 0.0"),
        (2.5, 1.25, 1.25, "2.5 - 1.25"),
        (100.5, 0.5, 100.0, "100.5 - 0.5"),
    ],
)
def test_sub_f32_execution(val_a, val_b, expected, desc):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Push operand A, then operand B -> result is A - B
    reg.set(Reg.AL, Registers.from_f32(val_a))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_f32(val_b))
    stack.push32(hw, Reg.AL)

    disp.execute(UserOpcode.SUB_F32)

    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.AL)
    result = Registers.to_f32(reg.peek(Reg.AL))
    assert pytest.approx(result, rel=1e-5) == expected, f"Failed {desc}: got {result}, expected {expected}"
    assert not hw.reg.get_flag(StatusFlag.ERR)


# =============================================================================
# Floating-Point F64 Tests (ADD_F64, SUB_F64)
# =============================================================================
@pytest.mark.parametrize(
    "val_a,val_b,expected,desc",
    [
        (1.0, 1.0, 2.0, "1.0 + 1.0"),
        (1.5, 2.5, 4.0, "1.5 + 2.5"),
        (100.0, 0.5, 100.5, "100.0 + 0.5"),
        (-3.0, -4.0, -7.0, "-3.0 + -4.0"),
        (1.0, -0.75, 0.25, "1.0 + -0.75"),
        (0.75, -1.0, -0.25, "0.75 + -1.0"),
        (1.0, -1.0, 0.0, "1.0 + -1.0 (exact cancellation)"),
        (0.0, 5.0, 5.0, "0.0 + 5.0"),
        (5.0, 0.0, 5.0, "5.0 + 0.0"),
        (0.0, 0.0, 0.0, "0.0 + 0.0"),
        (-2.5, 2.5, 0.0, "-2.5 + 2.5 (cancellation)"),
        (12.345678901234, 56.789012345678, 69.134691246912, "High-precision addition"),
        (1e-15, 1e-15, 2e-15, "Small numbers addition"),
        (1e20, 2e20, 3e20, "Large numbers addition"),
    ],
)
def test_add_f64_execution(val_a, val_b, expected, desc):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Push operand A, then operand B
    reg.set(Reg.AX, Registers.from_f64(val_a))
    stack.push64(hw, Reg.AX)
    reg.set(Reg.AX, Registers.from_f64(val_b))
    stack.push64(hw, Reg.AX)

    disp.execute(UserOpcode.ADD_F64)

    assert hw.reg.sp == 8
    stack.pop64(hw, Reg.AX)
    result = Registers.to_f64(reg.peek(Reg.AX))
    assert pytest.approx(result, rel=1e-12) == expected, f"Failed {desc}: got {result}, expected {expected}"
    assert not hw.reg.get_flag(StatusFlag.ERR)


@pytest.mark.parametrize(
    "val_a,val_b,expected,desc",
    [
        (5.0, 3.0, 2.0, "5.0 - 3.0"),
        (3.0, 5.0, -2.0, "3.0 - 5.0"),
        (5.0, 5.0, 0.0, "5.0 - 5.0 (exact cancellation)"),
        (10.0, -5.0, 15.0, "10.0 - -5.0"),
        (-10.0, 5.0, -15.0, "-10.0 - 5.0"),
        (-10.0, -5.0, -5.0, "-10.0 - -5.0"),
        (0.0, 5.0, -5.0, "0.0 - 5.0"),
        (5.0, 0.0, 5.0, "5.0 - 0.0"),
        (0.0, 0.0, 0.0, "0.0 - 0.0"),
        (2.5, 1.25, 1.25, "2.5 - 1.25"),
        (100.5, 0.5, 100.0, "100.5 - 0.5"),
        (56.789012345678, 12.345678901234, 44.443333444444, "High-precision subtraction"),
    ],
)
def test_sub_f64_execution(val_a, val_b, expected, desc):
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Push operand A, then operand B -> result is A - B
    reg.set(Reg.AX, Registers.from_f64(val_a))
    stack.push64(hw, Reg.AX)
    reg.set(Reg.AX, Registers.from_f64(val_b))
    stack.push64(hw, Reg.AX)

    disp.execute(UserOpcode.SUB_F64)

    assert hw.reg.sp == 8
    stack.pop64(hw, Reg.AX)
    result = Registers.to_f64(reg.peek(Reg.AX))
    assert pytest.approx(result, rel=1e-12) == expected, f"Failed {desc}: got {result}, expected {expected}"
    assert not hw.reg.get_flag(StatusFlag.ERR)


# =============================================================================
# Additional Dispatcher Edge Cases & 64-bit Coverage
# =============================================================================


def test_dispatcher_bwait_n():
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # By default, blocking_mode = True, BUSY = False -> bwait_n = True (ready)
    assert disp.bwait_n is True

    # When BUSY is True and blocking_mode is True -> bwait_n = False (hold CPU)
    hw.reg.set_flag(StatusFlag.BUSY, True)
    assert disp.bwait_n is False

    # When non-blocking, bwait_n is always True
    disp.execute(UserOpcode.SET_NONBLOCKING)
    assert disp.bwait_n is True


def test_batch_queue_overflow():
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)
    disp.execute(UserOpcode.SET_BATCH)

    # Queue has capacity 32
    for _ in range(32):
        disp.execute(UserOpcode.ADD_I32)
        assert not hw.reg.get_flag(StatusFlag.OVERFLOW)

    # 33rd command triggers OVERFLOW and ERR
    disp.execute(UserOpcode.ADD_I32)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)


def test_batch_execution_error_early_halt():
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)
    disp.execute(UserOpcode.SET_BATCH)

    # Enqueue ADD_I32 on empty stack (causes UNDERFLOW/ERR)
    disp.execute(UserOpcode.ADD_I32)
    # Enqueue another command
    disp.execute(UserOpcode.PUSH_PI_32)

    disp.execute(UserOpcode.EXEC_BATCH)
    assert hw.reg.get_flag(StatusFlag.ERR)
    # PUSH_PI_32 shouldn't have executed because batch halted early
    assert hw.reg.sp == 0


def test_mul_f64_and_div_f64_execution():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # MUL_F64: 2.5 * 4.0 = 10.0
    reg.set(Reg.AX, Registers.from_f64(2.5))
    stack.push64(hw, Reg.AX)
    reg.set(Reg.AX, Registers.from_f64(4.0))
    stack.push64(hw, Reg.AX)
    disp.execute(UserOpcode.MUL_F64)
    assert hw.reg.sp == 8
    stack.pop64(hw, Reg.AX)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 10.0

    # DIV_F64: 10.0 / 2.0 = 5.0
    reg.set(Reg.AX, Registers.from_f64(10.0))
    stack.push64(hw, Reg.AX)
    reg.set(Reg.AX, Registers.from_f64(2.0))
    stack.push64(hw, Reg.AX)
    disp.execute(UserOpcode.DIV_F64)
    assert hw.reg.sp == 8
    stack.pop64(hw, Reg.AX)
    assert Registers.to_f64(reg.peek(Reg.AX)) == 5.0


def test_abs_i64_and_constants():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # ABS_I64: -100 -> 100
    reg.set(Reg.AX, Registers.from_int(-100, 8, signed=True))
    stack.push64(hw, Reg.AX)
    disp.execute(UserOpcode.ABS_I64)
    assert hw.reg.sp == 8
    stack.pop64(hw, Reg.AX)
    assert Registers.to_int(reg.peek(Reg.AX)) == 100

    # PUSH_PI_64
    disp.execute(UserOpcode.PUSH_PI_64)
    assert hw.reg.sp == 8
    stack.pop64(hw, Reg.AX)
    import math
    assert pytest.approx(Registers.to_f64(reg.peek(Reg.AX)), rel=1e-12) == math.pi


def test_user_memory_slot_errors_and_zero_mem():
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # CP_MEM0_TOS when stack is empty -> UNDERFLOW & ERR
    disp.execute(UserOpcode.CP_MEM0_TOS)
    assert hw.reg.get_flag(StatusFlag.UNDERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # CP_TOS_MEM when stack is full (sp = 254 + 4 > 256) -> OVERFLOW & ERR
    hw.reg.set_flag(StatusFlag.ERR, False)
    hw.reg.sp = 254
    disp.execute(UserOpcode.CP_TOS_MEM0)
    assert hw.reg.get_flag(StatusFlag.OVERFLOW)
    assert hw.reg.get_flag(StatusFlag.ERR)

    # ZERO_MEM
    hw.mem.store_user_mem(0, bytearray(b"\x12\x34\x56\x78"))
    disp.execute(UserOpcode.ZERO_MEM)
    assert hw.mem.load_user_mem(0, 4) == bytearray(4)


def test_micro_ops_direct_run():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Test ADD/ADC/SUB/SBB/CMP 32 & 64, logic, shifts, exp, and sqrt
    reg.set(Reg.AL, Registers.from_int(10, 4))
    reg.set(Reg.BL, Registers.from_int(5, 4))
    reg.set(Reg.AX, Registers.from_int(100, 8))
    reg.set(Reg.BX, Registers.from_int(50, 8))

    ucode = [
        MicroInstruction(MicroOp.ADC, src=Reg.BL),
        MicroInstruction(MicroOp.SBB, src=Reg.BL),
        MicroInstruction(MicroOp.CMP, src=Reg.BL),
        MicroInstruction(MicroOp.ADC64, src=Reg.BX),
        MicroInstruction(MicroOp.SUB64, src=Reg.BX),
        MicroInstruction(MicroOp.SBB64, src=Reg.BX),
        MicroInstruction(MicroOp.CMP64, src=Reg.BX),
        MicroInstruction(MicroOp.ASR, dst=Reg.AL, imm=1),
        MicroInstruction(MicroOp.RRC, dst=Reg.AX),
        MicroInstruction(MicroOp.AND, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(MicroOp.OR, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(MicroOp.XOR, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(MicroOp.NOT, dst=Reg.AL),
        MicroInstruction(MicroOp.ABS, dst=Reg.AH),
        MicroInstruction(MicroOp.EXP_ADD),
        MicroInstruction(MicroOp.EXP_SUB),
        MicroInstruction(MicroOp.EXP_DEC),
        MicroInstruction(MicroOp.SQRT_EXP, dst=Reg.EA),
        MicroInstruction(MicroOp.SQRT_CORE, dst=Reg.AL),
        MicroInstruction(MicroOp.SQRT_EXP64, dst=Reg.EA),
        MicroInstruction(MicroOp.SQRT_CORE64, dst=Reg.AX),
        MicroInstruction(MicroOp.AND64, dst=Reg.AX, src=Reg.BX),
        MicroInstruction(MicroOp.OR64, dst=Reg.AX, src=Reg.BX),
        MicroInstruction(MicroOp.XOR64, dst=Reg.AX, src=Reg.BX),
        MicroInstruction(MicroOp.NOT64, dst=Reg.AX),
        MicroInstruction(MicroOp.LSL64, dst=Reg.AX, imm=1),
        MicroInstruction(MicroOp.LSR64, dst=Reg.AX, imm=1),
        MicroInstruction(MicroOp.ASR64, dst=Reg.AX, imm=1),
        MicroInstruction(MicroOp.SWAP, dst=Reg.AL, src=Reg.BL),
        MicroInstruction(MicroOp.MOV, dst=Reg.BL, src=Reg.AL),
        MicroInstruction(MicroOp.LD, dst=Reg.FL, imm=0x12345678),
        MicroInstruction(MicroOp.NOP),
        MicroInstruction(MicroOp.RET),
    ]
    disp._run(ucode)
    assert not hw.reg.get_flag(StatusFlag.ERR)
    assert Registers.to_int(reg.peek(Reg.FL)) == 0x12345678


def test_batch_invalid_opcode_error():
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Directly inject an invalid opcode byte (0x7F) into the batch buffer
    from fpu_emu.dispatcher import CMD_STACK_BASE
    hw.mem[CMD_STACK_BASE] = 0x7F
    hw.reg.osp = 1

    disp.execute(UserOpcode.EXEC_BATCH)
    assert hw.reg.get_flag(StatusFlag.ERR)
    assert hw.reg.osp == 0


def test_more_dispatcher_user_opcodes():
    hw = Hardware()
    reg = RegTestHarness(hw.reg)
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # ABS_I32: -42 -> 42
    reg.set(Reg.AL, Registers.from_int(-42, 4, signed=True))
    stack.push32(hw, Reg.AL)
    disp.execute(UserOpcode.ABS_I32)
    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.AL)
    assert Registers.to_int(reg.peek(Reg.AL)) == 42

    # MUL_F32: 1.5 * 2.0 = 3.0
    reg.set(Reg.AL, Registers.from_f32(1.5))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_f32(2.0))
    stack.push32(hw, Reg.AL)
    disp.execute(UserOpcode.MUL_F32)
    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.AL)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 3.0

    # DIV_F32: 6.0 / 2.0 = 3.0
    reg.set(Reg.AL, Registers.from_f32(6.0))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_f32(2.0))
    stack.push32(hw, Reg.AL)
    disp.execute(UserOpcode.DIV_F32)
    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.AL)
    assert Registers.to_f32(reg.peek(Reg.AL)) == 3.0

    # PUSH_PI_32 (LOAD_CONST 32-bit)
    disp.execute(UserOpcode.PUSH_PI_32)
    assert hw.reg.sp == 4
    stack.pop32(hw, Reg.AL)
    import math
    assert pytest.approx(Registers.to_f32(reg.peek(Reg.AL)), rel=1e-6) == math.pi

    # Successful CP_MEM0_TOS and CP_TOS_MEM0
    reg.set(Reg.AL, Registers.from_int(0x12345678, 4))
    stack.push32(hw, Reg.AL)
    disp.execute(UserOpcode.CP_MEM0_TOS)
    # Check that memory slot 0 has 0x12345678
    assert hw.mem.load_user_mem(0, 4) == bytearray(b"\x78\x56\x34\x12")

    # Now load it back with CP_TOS_MEM0
    disp.execute(UserOpcode.CP_TOS_MEM0)
    assert hw.reg.sp == 8
    stack.pop32(hw, Reg.BL)
    assert Registers.to_int(reg.peek(Reg.BL)) == 0x12345678

    # LN_F32: ln(e) = 1.0
    reg.set(Reg.AL, Registers.from_f32(math.e))
    stack.push32(hw, Reg.AL)
    disp.execute(UserOpcode.LN_F32)
    assert hw.reg.sp == 8
    stack.pop32(hw, Reg.AL)
    assert pytest.approx(Registers.to_f32(reg.peek(Reg.AL)), rel=1e-5) == 1.0

    # EXP_F32: exp(1.0) = e
    reg.set(Reg.AL, Registers.from_f32(1.0))
    stack.push32(hw, Reg.AL)
    disp.execute(UserOpcode.EXP_F32)
    assert hw.reg.sp == 8
    stack.pop32(hw, Reg.AL)
    assert pytest.approx(Registers.to_f32(reg.peek(Reg.AL)), rel=1e-5) == math.e

    # POW_F32: (2.0, 3.0) -> 8.0
    reg.set(Reg.AL, Registers.from_f32(2.0))
    stack.push32(hw, Reg.AL)
    reg.set(Reg.AL, Registers.from_f32(3.0))
    stack.push32(hw, Reg.AL)
    disp.execute(UserOpcode.POW_F32)
    assert hw.reg.sp == 8
    stack.pop32(hw, Reg.AL)
    assert pytest.approx(Registers.to_f32(reg.peek(Reg.AL)), rel=1e-5) == 8.0

    # LN_F64: ln(e) = 1.0
    reg.set(Reg.AX, Registers.from_f64(math.e))
    stack.push64(hw, Reg.AX)
    disp.execute(UserOpcode.LN_F64)
    assert hw.reg.sp == 12
    stack.pop64(hw, Reg.AX)
    assert pytest.approx(Registers.to_f64(reg.peek(Reg.AX)), rel=1e-10) == 1.0

    # EXP_F64: exp(1.0) = e
    reg.set(Reg.AX, Registers.from_f64(1.0))
    stack.push64(hw, Reg.AX)
    disp.execute(UserOpcode.EXP_F64)
    assert hw.reg.sp == 12
    stack.pop64(hw, Reg.AX)
    assert pytest.approx(Registers.to_f64(reg.peek(Reg.AX)), rel=1e-10) == math.e

    # POW_F64: (2.0, 4.0) -> 16.0
    reg.set(Reg.AX, Registers.from_f64(2.0))
    stack.push64(hw, Reg.AX)
    reg.set(Reg.AX, Registers.from_f64(4.0))
    stack.push64(hw, Reg.AX)
    disp.execute(UserOpcode.POW_F64)
    assert hw.reg.sp == 12
    stack.pop64(hw, Reg.AX)
    assert pytest.approx(Registers.to_f64(reg.peek(Reg.AX)), rel=1e-10) == 16.0

    # Unimplemented microcode lookup
    from fpu_emu.micro_code import MicroCode
    with pytest.raises(NotImplementedError):
        MicroCode.get(UserOpcode.CONV_I32_I64)
