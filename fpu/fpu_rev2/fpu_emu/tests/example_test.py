"""End-to-End Validation of the 4 Canonical Example Programs from ProgrammersGuide.md Section 6.

Canonical Examples:
1. Section 6.1: Manhattan Distance (i32) - D = |X1 - X2| + |Y1 - Y2|
2. Section 6.2: Euclidean 3D Vector Norm (f32) - D = sqrt(X^2 + Y^2 + Z^2) (Immediate & Batch)
3. Section 6.3: Volume of a Sphere (f32) - V = (4/3) * pi * r^3 (using PUSH_PI_32 from Flash ROM)
4. Section 6.4: Quadratic Polynomial Evaluation (f32) - y = Ax^2 + Bx + C (using User Storage Slots)
"""

import math
import pytest
from fpu_emu.alu.alu import Alu
from fpu_emu.dispatcher import Dispatcher
from fpu_emu.hardware import Hardware
from fpu_emu.memory import stack
from fpu_emu.memory.registers import Reg, Registers, StatusFlag
from fpu_emu.user_opcodes import UserOpcode


# =============================================================================
# Helper Functions
# =============================================================================
def push_i32(hw: Hardware, val: int):
    """Pushes a 32-bit signed integer onto the operand stack."""
    hw.reg.testharness_set(Reg.AL, Registers.from_int(val, 4, signed=True))
    stack.push32(hw, Reg.AL)


def pop_i32(hw: Hardware) -> int:
    """Pops a 32-bit signed integer from the operand stack."""
    stack.pop32(hw, Reg.AL)
    return Registers.to_int(hw.reg.get(Reg.AL), signed=True)


def push_f32(hw: Hardware, val: float):
    """Pushes an IEEE-754 32-bit float onto the operand stack."""
    hw.reg.testharness_set(Reg.AL, Registers.from_f32(val))
    stack.push32(hw, Reg.AL)


def pop_f32(hw: Hardware) -> float:
    """Pops an IEEE-754 32-bit float from the operand stack."""
    stack.pop32(hw, Reg.AL)
    return Registers.to_f32(hw.reg.get(Reg.AL))


# =============================================================================
# 1. Canonical Example 1: Manhattan Distance (i32) - Section 6.1
# =============================================================================
@pytest.mark.parametrize(
    "x1, x2, y1, y2, expected",
    [
        (10, 2, 15, 5, 18),
        (-10, 5, 20, -30, 65),
        (100, 100, -50, -50, 0),
        (0, 0, 0, 0, 0),
        (-250, 250, 500, -500, 1500),
        (1000000, 2000000, -3000000, 4000000, 8000000),
    ],
)
def test_example_1_manhattan_distance_i32(x1: int, x2: int, y1, y2, expected: int):
    """Section 6.1: D = |X1 - X2| + |Y1 - Y2| using SUB_I32, ABS_I32, ADD_I32."""
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # 1. Push X1, Push X2, SUB_I32, ABS_I32
    push_i32(hw, x1)
    push_i32(hw, x2)
    disp.execute(UserOpcode.SUB_I32)
    disp.execute(UserOpcode.ABS_I32)

    # 2. Push Y1, Push Y2, SUB_I32, ABS_I32
    push_i32(hw, y1)
    push_i32(hw, y2)
    disp.execute(UserOpcode.SUB_I32)
    disp.execute(UserOpcode.ABS_I32)

    # 3. ADD_I32
    disp.execute(UserOpcode.ADD_I32)

    # 4. Pop result
    result = pop_i32(hw)
    assert result == expected
    assert not hw.reg.get_flag(StatusFlag.ERR)


# =============================================================================
# 2. Canonical Example 2: Euclidean 3D Vector Norm (f32) - Section 6.2
# =============================================================================
@pytest.mark.parametrize(
    "x, y, z, expected",
    [
        (3.0, 4.0, 12.0, 13.0),
        (1.0, 2.0, 2.0, 3.0),
        (0.0, 0.0, 0.0, 0.0),
        (6.0, 8.0, 0.0, 10.0),
        (2.0, 3.0, 6.0, 7.0),
        (4.0, 4.0, 7.0, 9.0),
    ],
)
def test_example_2_vector3d_norm_immediate(x: float, y: float, z: float, expected: float):
    """Section 6.2: D = sqrt(X^2 + Y^2 + Z^2) in Immediate Mode."""
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # Push X, DUP4, MUL_F32 -> X^2
    push_f32(hw, x)
    disp.execute(UserOpcode.DUP4)
    disp.execute(UserOpcode.MUL_F32)

    # Push Y, DUP4, MUL_F32, ADD_F32 -> X^2 + Y^2
    push_f32(hw, y)
    disp.execute(UserOpcode.DUP4)
    disp.execute(UserOpcode.MUL_F32)
    disp.execute(UserOpcode.ADD_F32)

    # Push Z, DUP4, MUL_F32, ADD_F32 -> X^2 + Y^2 + Z^2
    push_f32(hw, z)
    disp.execute(UserOpcode.DUP4)
    disp.execute(UserOpcode.MUL_F32)
    disp.execute(UserOpcode.ADD_F32)

    # SQRT_F32
    disp.execute(UserOpcode.SQRT_F32)

    # Pop result
    result = pop_f32(hw)
    assert pytest.approx(result, rel=1e-5) == expected
    assert not hw.reg.get_flag(StatusFlag.ERR)


@pytest.mark.parametrize(
    "x, y, z, expected",
    [
        (3.0, 4.0, 12.0, 13.0),
        (1.0, 2.0, 2.0, 3.0),
        (2.0, 3.0, 6.0, 7.0),
    ],
)
def test_example_2_vector3d_norm_batch_with_storage_slots(
    x: float, y: float, z: float, expected: float
):
    """Section 6.2: D = sqrt(X^2 + Y^2 + Z^2) streamed and executed in Batch Queuing Mode."""
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    # 1. Store X to slot 0, Y to slot 1, Z to slot 2
    push_f32(hw, x)
    disp.execute(UserOpcode.CP_MEM0_TOS)
    stack.pop32(hw, Reg.AL)

    push_f32(hw, y)
    disp.execute(UserOpcode.CP_MEM1_TOS)
    stack.pop32(hw, Reg.AL)

    push_f32(hw, z)
    disp.execute(UserOpcode.CP_MEM2_TOS)
    stack.pop32(hw, Reg.AL)

    # 2. Enter batch mode and stream queued formula
    disp.execute(UserOpcode.SET_BATCH)

    batch_opcodes = [
        UserOpcode.CP_TOS_MEM0,  # Load X
        UserOpcode.DUP4,
        UserOpcode.MUL_F32,      # X^2
        UserOpcode.CP_TOS_MEM1,  # Load Y
        UserOpcode.DUP4,
        UserOpcode.MUL_F32,      # Y^2
        UserOpcode.ADD_F32,      # X^2 + Y^2
        UserOpcode.CP_TOS_MEM2,  # Load Z
        UserOpcode.DUP4,
        UserOpcode.MUL_F32,      # Z^2
        UserOpcode.ADD_F32,      # X^2 + Y^2 + Z^2
        UserOpcode.SQRT_F32,     # sqrt(X^2 + Y^2 + Z^2)
    ]
    for op in batch_opcodes:
        disp.execute(op)

    # 3. Execute entire batch at once
    disp.execute(UserOpcode.EXEC_BATCH)
    disp.execute(UserOpcode.SET_IMMEDIATE)

    # 4. Pop result
    result = pop_f32(hw)
    assert pytest.approx(result, rel=1e-5) == expected
    assert not hw.reg.get_flag(StatusFlag.ERR)


# =============================================================================
# 3. Canonical Example 3: Volume of a Sphere (f32) - Section 6.3
# =============================================================================
@pytest.mark.parametrize(
    "r",
    [1.0, 2.0, 3.0, 0.5, 10.0],
)
def test_example_3_sphere_volume_f32(r: float):
    """Section 6.3: V = (4/3) * pi * r^3 using PUSH_PI_32 from Flash ROM."""
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    expected = (4.0 / 3.0) * math.pi * (r ** 3)

    # 1. Push r
    push_f32(hw, r)

    # 2. Compute r^3: DUP4, DUP4, MUL_F32, MUL_F32
    disp.execute(UserOpcode.DUP4)
    disp.execute(UserOpcode.DUP4)
    disp.execute(UserOpcode.MUL_F32)  # r^2
    disp.execute(UserOpcode.MUL_F32)  # r^3

    # 3. Push PI: PUSH_PI_32 (0xA0) loaded directly from Flash ROM
    disp.execute(UserOpcode.PUSH_PI_32)
    disp.execute(UserOpcode.MUL_F32)  # pi * r^3

    # 4. Multiply by 4.0
    push_f32(hw, 4.0)
    disp.execute(UserOpcode.MUL_F32)  # 4 * pi * r^3

    # 5. Divide by 3.0
    push_f32(hw, 3.0)
    disp.execute(UserOpcode.DIV_F32)  # (4/3) * pi * r^3

    # 6. Pop result
    result = pop_f32(hw)
    assert pytest.approx(result, rel=1e-5) == expected
    assert not hw.reg.get_flag(StatusFlag.ERR)


# =============================================================================
# 4. Canonical Example 4: Quadratic Evaluation (f32) - Section 6.4
# =============================================================================
@pytest.mark.parametrize(
    "x, a, b, c",
    [
        (2.0, 3.0, 4.0, 5.0),      # 3(4) + 4(2) + 5 = 25.0
        (-1.0, 2.0, -3.0, 4.0),    # 2(1) - 3(-1) + 4 = 9.0
        (0.0, 10.0, 20.0, 30.0),   # 30.0
        (1.5, 2.0, -1.0, -3.0),    # 2(2.25) - 1.5 - 3 = 0.0
        (5.0, 1.0, 0.0, -25.0),    # 25 - 25 = 0.0
    ],
)
def test_example_4_polynomial_evaluation(x: float, a: float, b: float, c: float):
    """Section 6.4: y = (A*x + B)*x + C (Horner's rule) using User Storage Slots."""
    hw = Hardware()
    alu = Alu(hw)
    disp = Dispatcher(hw, alu)

    expected = (a * x + b) * x + c

    # 1. Push x
    push_f32(hw, x)

    # 2. Stash x into slot 0: CP [0], TOS (0xD0) without popping
    disp.execute(UserOpcode.CP_MEM0_TOS)

    # 3. Push A and compute A * x
    push_f32(hw, a)
    disp.execute(UserOpcode.MUL_F32)

    # 4. Push B and compute (A * x) + B
    push_f32(hw, b)
    disp.execute(UserOpcode.ADD_F32)

    # 5. Reload cached x from slot 0: CP TOS, [0] (0xE0)
    disp.execute(UserOpcode.CP_TOS_MEM0)

    # 6. Compute ((A * x) + B) * x
    disp.execute(UserOpcode.MUL_F32)

    # 7. Push C and compute ((A * x) + B) * x + C
    push_f32(hw, c)
    disp.execute(UserOpcode.ADD_F32)

    # 8. Pop result
    result = pop_f32(hw)
    assert pytest.approx(result, rel=1e-5) == expected
    assert not hw.reg.get_flag(StatusFlag.ERR)
