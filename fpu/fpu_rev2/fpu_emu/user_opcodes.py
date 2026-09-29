from enum import Enum


class UserOpcode(Enum):
    ADD_I32 = 0x00
    ADD_F32 = 0x01
    ADD_I64 = 0x02
    ADD_F64 = 0x03

    SUB_I32 = 0x08
    SUB_F32 = 0x09
    SUB_I64 = 0x0A
    SUB_F64 = 0x0B

    MUL_I32 = 0x10
    MUL_F32 = 0x11
    MUL_I64 = 0x12
    MUL_F64 = 0x13

    DIV_I32 = 0x18
    DIV_F32 = 0x19
    DIV_I64 = 0x1A
    DIV_F64 = 0x1B

    # Floating-Point Square Root (Pure F32/F64)
    SQRT_F32 = 0x21
    SQRT_F64 = 0x23

    # Floating-Point Power
    POW_F32 = 0x29
    POW_F64 = 0x2B

    # Natural Logarithm
    LN_F32 = 0x31
    LN_F64 = 0x33

    # Exponential (e^x)
    EXP_F32 = 0x39
    EXP_F64 = 0x3B

    # Absolute Value
    ABS_I32 = 0x58
    ABS_F32 = 0x59
    ABS_I64 = 0x5A
    ABS_F64 = 0x5B

    # Mathematical Constants (0xA0..0xAF)
    PUSH_PI_32 = 0xA0
    PUSH_PI_64 = 0xA1
    PUSH_E_32 = 0xA2
    PUSH_E_64 = 0xA3
    PUSH_LN2_32 = 0xA4
    PUSH_LN2_64 = 0xA5
    PUSH_LOG2E_32 = 0xA6
    PUSH_LOG2E_64 = 0xA7
    PUSH_LOG2_10_32 = 0xA8
    PUSH_LOG2_10_64 = 0xA9
    PUSH_LOG10_2_32 = 0xAA
    PUSH_LOG10_2_64 = 0xAB
    PUSH_SQRT2_32 = 0xAC
    PUSH_SQRT2_64 = 0xAD
    PUSH_INV_SQRT2_32 = 0xAE
    PUSH_INV_SQRT2_64 = 0xAF

    # Stack Manipulation
    DUP4 = 0xC0
    DUP8 = 0xC1

    # Type Conversions
    CONV_I32_I64 = 0xC8
    CONV_F32_F64 = 0xC9
    CONV_I64_I32 = 0xCA
    CONV_F64_F32 = 0xCB
    CONV_I32_F32 = 0xCC
    CONV_F32_I32 = 0xCD
    CONV_I64_F64 = 0xCE
    CONV_F64_I64 = 0xCF

    # User Storage Memory Slots (0xD0..0xDF: CP [x], TOS)
    CP_MEM0_TOS = 0xD0
    CP_MEM1_TOS = 0xD1
    CP_MEM2_TOS = 0xD2
    CP_MEM3_TOS = 0xD3
    CP_MEM4_TOS = 0xD4
    CP_MEM5_TOS = 0xD5
    CP_MEM6_TOS = 0xD6
    CP_MEM7_TOS = 0xD7
    CP_MEM8_TOS = 0xD8
    CP_MEM9_TOS = 0xD9
    CP_MEM10_TOS = 0xDA
    CP_MEM11_TOS = 0xDB
    CP_MEM12_TOS = 0xDC
    CP_MEM13_TOS = 0xDD
    CP_MEM14_TOS = 0xDE
    CP_MEM15_TOS = 0xDF

    # User Storage Memory Slots (0xE0..0xEF: CP TOS, [x])
    CP_TOS_MEM0 = 0xE0
    CP_TOS_MEM1 = 0xE1
    CP_TOS_MEM2 = 0xE2
    CP_TOS_MEM3 = 0xE3
    CP_TOS_MEM4 = 0xE4
    CP_TOS_MEM5 = 0xE5
    CP_TOS_MEM6 = 0xE6
    CP_TOS_MEM7 = 0xE7
    CP_TOS_MEM8 = 0xE8
    CP_TOS_MEM9 = 0xE9
    CP_TOS_MEM10 = 0xEA
    CP_TOS_MEM11 = 0xEB
    CP_TOS_MEM12 = 0xEC
    CP_TOS_MEM13 = 0xED
    CP_TOS_MEM14 = 0xEE
    CP_TOS_MEM15 = 0xEF

    ZERO_MEM = 0xF0

    CLEAR_STACK = 0xC6
    EXEC_BATCH = 0xFA
    SET_BATCH = 0xFB
    SET_IMMEDIATE = 0xFC
    SET_NONBLOCKING = 0xFD
    SET_BLOCKING = 0xFE
    RESET = 0xFF

