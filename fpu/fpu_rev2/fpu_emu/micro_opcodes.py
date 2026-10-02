"""Micro-operation codes and MicroInstruction dataclass for the micro-sequencer."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
from fpu_emu.memory.registers import Reg, StatusFlag


class MicroOp(Enum):
    """Micro-sequencer primitive operations."""

    # Stack Operations
    POP = auto()  # 32-bit stack pop to register
    PUSH = auto()  # 32-bit register push to stack
    POP64 = auto()  # 64-bit stack pop to register
    PUSH64 = auto()  # 64-bit register push to stack

    # ALU 32-bit Operations
    ADD = auto()  # ADD AL, src
    ADC = auto()  # ADC AL, src
    SUB = auto()  # SUB AL, src
    SBB = auto()  # SBB AL, src
    CMP = auto()  # CMP AL, src

    # ALU 64-bit Operations
    ADD64 = auto()  # ADD AX, src
    ADC64 = auto()  # ADC AX, src
    SUB64 = auto()  # SUB AX, src
    SBB64 = auto()  # SBB AX, src
    CMP64 = auto()  # CMP AX, src

    # Shifter Operations
    LSL = auto()  # LSL AL, C
    LSR = auto()  # LSR AL, C
    ASR = auto()  # ASR AL, C
    RRC = auto()  # RRC AL (Rotate Right through Carry 1 bit)
    LSL64 = auto()  # LSL AX, C
    LSR64 = auto()  # LSR AX, C
    ASR64 = auto()  # ASR AX, C
    RRC64 = auto()  # RRC AX (Rotate Right through Carry 1 bit 64-bit)

    # Leading Zero Counter
    LZC = auto()  # LZC C, AL (or src)
    LZC64 = auto()  # LZC C, AX (or src)

    # Bitwise Logic & Sign Manipulator
    AND = auto()  # AND AL, src
    OR = auto()  # OR AL, src
    XOR = auto()  # XOR AL, src
    NOT = auto()  # NOT AL
    AND64 = auto()  # AND AX, src
    OR64 = auto()  # OR AX, src
    XOR64 = auto()  # XOR AX, src
    NOT64 = auto()  # NOT AX
    CHS = auto()  # CHS (AH[31] <- ~AH[31])
    ABS = auto()  # ABS (AH[31] <- 0)
    ABS_INT = auto()  # Integer ABS (AL <- |AL|, 2's complement, V on 0x80000000)
    ABS_INT64 = auto()  # Integer ABS 64-bit (AX <- |AX|, V on 0x80000000_00000000)

    # Radix-4 Booth Multiplier & Divider
    MUL = auto()  # MUL AL, src (32-bit -> AX, 16 cycles)
    MUL64 = auto()  # MUL AX, src (64-bit -> {DX, AX}, 32 cycles)
    MUL_F32 = auto()  # Single-precision float multiply (AL <- AL * BL)
    DIV_F32 = auto()  # Single-precision float divide (AL <- AL / BL)
    MUL_F64 = auto()  # Double-precision float multiply (AX <- AX * BX)
    DIV_F64 = auto()  # Double-precision float divide (AX <- AX / BX)
    LN_F32 = auto()  # Single-precision float natural log (AL <- ln(AL))
    LN_F64 = auto()  # Double-precision float natural log (AX <- ln(AX))
    EXP_F32 = auto()  # Single-precision float exp (AL <- exp(AL))
    EXP_F64 = auto()  # Double-precision float exp (AX <- exp(AX))
    POW_F32 = auto()  # Single-precision float pow (AL <- AL ** BL)
    POW_F64 = auto()  # Double-precision float pow (AX <- AX ** BX)

    # Constant & User Storage Operations
    LOAD_CONST = auto()  # FL/FX <- ROM constant by opcode (imm = opcode 0xA0..0xAF)
    CP_MEM_TOS = auto()  # [imm] <- TOS (copy/peek without popping)
    CP_TOS_MEM = auto()  # push [imm] to TOS
    ZERO_MEM = auto()  # Zero all 16 user storage slots

    # 12-Bit Exponent ALU (alu_exp12)
    EXP_ADD = auto()  # EA <- EA + EB
    EXP_SUB = auto()  # EA <- EA - EB
    EXP_DIFF = auto()  # C <- min(|EA - EB|, 63), CF <- (EA < EB)
    EXP_NORM = auto()  # EA <- EA - C
    EXP_INC = auto()  # EA <- EA + 1
    EXP_DEC = auto()  # EA <- EA - 1

    # Floating-Point Unpack & Pack (Approach 1)
    UNPACK_F32 = auto()  # Unpack 32-bit float: dst_exp <- src[30:23], src <- mantissa left-justified
    PACK_F32 = auto()  # Pack 32-bit float: dst <- {sign, exp, mantissa}
    UNPACK_F64 = auto()  # Unpack 64-bit float
    PACK_F64 = auto()  # Pack 64-bit float

    # Floating-Point Square Root Micro-Ops
    SQRT_EXP = auto()  # EA <- (EA - 127)/2 + 127, latch exponent odd parity
    SQRT_CORE = auto()  # AL <- sqrt_mantissa(AL, seed, parity)
    SQRT_EXP64 = auto()  # EA <- (EA - 1023)/2 + 1023, latch exponent odd parity
    SQRT_CORE64 = auto()  # AX <- sqrt_mantissa64(AX, seed, parity)

    # Register Transfer & Immediate Load
    LD = auto()  # LD dst, imm
    MOV = auto()  # MOV dst, src
    SWAP = auto()  # SWAP dst, src, overwrites FL or FX

    # Branch & Control
    JMP = auto()  # Unconditional jump to target index
    JZ = auto()  # Jump to target if flag == 0 (cleared)
    JNZ = auto()  # Jump to target if flag == 1 (asserted)
    RET = auto()  # Return from microcode (normal completion)
    TRAP = auto()  # Set ERR flag and terminate microcode
    NOP = auto()  # No operation


@dataclass
class MicroInstruction:
    """Represents a single micro-instruction word executed by the micro-sequencer."""

    op: MicroOp
    dst: Optional[Reg] = None
    src: Optional[Reg] = None
    imm: int = 0
    flag: Optional[StatusFlag] = None
    target: int = 0
