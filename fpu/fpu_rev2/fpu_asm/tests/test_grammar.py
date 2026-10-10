"""Unit tests for FPU microcode Lark grammar (ucode.lark)."""

from pathlib import Path
import pytest
from lark import Lark


@pytest.fixture(scope="module")
def parser() -> Lark:
    grammar_file = Path(__file__).parent.parent / "ucode.lark"
    with open(grammar_file, "r") as f:
        return Lark(f.read(), parser="earley")


def test_directives(parser: Lark) -> None:
    lines = [
        ".org 0x000\n",
        ".org 100\n",
        ".equ COUNT, 16\n",
        ".equ OFFSET 0x20\n",
        ".align 4\n",
        ".align 8\n",
        ".entry User_AddF32\n",
        ".entry 0x10\n",
        ".global User_AddF32\n",
        ".global .shared_sub\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_arithmetic_instructions(parser: Lark) -> None:
    lines = [
        "ADD AL, BL\n",
        "ADC AL, BL\n",
        "SUB AL, BL\n",
        "SBB AL, BL\n",
        "EXP_ADD EA, EB\n",
        "EXP_SUB EA, EB\n",
        "SUB DL, AL, BL\n",
        "SBB DL, AL, BL\n",
        "EXP_SUB C, EA, EB\n",
        "EXP_ADD EA, #1\n",
        "EXP_ADD EA, 1\n",
        "EXP_ADD EA, IMM=1\n",
        "ADD AL, 10\n",
        "ADD.64 AL, BL\n",
        "ADD AX, BX\n",
        "SUB.64 DL, AL, BL\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_cmp_instruction(parser: Lark) -> None:
    lines = [
        "CMP EA, EB\n",
        "CMP C, #32\n",
        "CMP C, IMM=32\n",
        "CMP AL, BL\n",
        "CMP.64 AX, BX\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_math_instructions(parser: Lark) -> None:
    lines = [
        "PACK AL, EA\n",
        "UNPACK BL, EB\n",
        "UNPACK AL, EA\n",
        "MUL AX, BL\n",
        "MULU AX, AL, BL\n",
        "DIV AL, BL\n",
        "DIVU AL, BL\n",
        "MUL.64 AX, BX\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_logic_instructions(parser: Lark) -> None:
    lines = [
        "AND AL, BL\n",
        "OR DL, AL, BL\n",
        "XOR AL, BL\n",
        "FABS AL\n",
        "FCHS AL\n",
        "NOT AL\n",
        "FABS AX\n",
        "FCHS.64 AL\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_shift_instructions(parser: Lark) -> None:
    lines = [
        "LSL AL\n",
        "LSL AL, C\n",
        "LSL AL, 8\n",
        "LSL AL, #8\n",
        "LSL.64 AL, C\n",
        "LSR BL\n",
        "LSR BL, C\n",
        "LSR BL, 1\n",
        "LSR.64 AL, 23\n",
        "ASL AL\n",
        "ASL AL, C\n",
        "ASL.64 AL, 1\n",
        "ASR BL\n",
        "ASR BL, C\n",
        "ASR.64 AL, 32\n",
        "LZC AL\n",
        "LZC C, AL\n",
        "LZC BL, AH\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_stack_instructions(parser: Lark) -> None:
    lines = [
        "PUSH AL\n",
        "PUSH DL\n",
        "PUSH #0\n",
        "PUSH.64 AX\n",
        "POP BL\n",
        "POP AL\n",
        "POP.64 BX\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_memory_and_status_instructions(parser: Lark) -> None:
    lines = [
        "LDC AL, CONST, 0x02\n",
        "LDC AL, RECIP, C\n",
        "LDC AL, SQRT, EA\n",
        "LDI C, 24\n",
        "LDI ERR, 1\n",
        "LDI CF, 0\n",
        "LDI ZERO, 1\n",
        "LDI DIFF_SIGN, 0\n",
        "LD AL, 0x10\n",
        "LD AL, [C]\n",
        "LD.64 AX, [BL]\n",
        "STO 0x20, AL\n",
        "STO [C], AL\n",
        "STO.64 [BL], AX\n",
        "LDU AL, 0x30\n",
        "STU 0x40, AL\n",
        "MOV DL, BL\n",
        "MOV.64 DL, AL\n",
        "SWAP AL, BL\n",
        "SWAP EA, EB\n",
        "SSAV\n",
        "SRES\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_control_instructions(parser: Lark) -> None:
    lines = [
        "JMP .target\n",
        "JMP target\n",
        "JZ .target\n",
        "JZ ZERO, .target\n",
        "JZ CF, .target\n",
        "JNZ .target\n",
        "JNZ DIFF_SIGN, .target\n",
        "JNZ UNDERFLOW, .trap\n",
        "JNZ ERR, .trap\n",
        "DJNZ .loop\n",
        "CALL .sub_align\n",
        "CALL sub_align\n",
        "RET\n",
        "NOP\n",
        "HALT\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_delay_slot_annotation(parser: Lark) -> None:
    lines = [
        ".delay NOP\n",
        ".delay ADD AL, BL\n",
        ".delay MOV DL, BL\n",
    ]
    for line in lines:
        tree = parser.parse(line)
        assert tree is not None


def test_comments_and_empty_lines(parser: Lark) -> None:
    program = """
    ; Semicolon full line comment
    # Hash full line comment

    User_AddF32: ; entry label
        POP BL   ; inline semicolon
        POP AL   # inline hash
        ADD AL, BL
        HALT
    """
    tree = parser.parse(program)
    assert tree is not None


def test_full_sample_program(parser: Lark) -> None:
    program = """
    ; ======================================================================
    ; Full Sample Program for Floating Point Add
    ; ======================================================================
    .org 0x000
    .global User_AddF32

    User_AddF32:
        POP     BL
        JNZ     UNDERFLOW, .trap_underflow
        MOV     DL, BL
        POP     AL
        JNZ     UNDERFLOW, .trap_underflow
        MOV     AH, AL
        UNPACK  BL, EB
        JZ      ZERO, .ret_a
        UNPACK  AL, EA
        JZ      ZERO, .ret_b

        CALL    .sub_align_f32

        JNZ     DIFF_SIGN, .do_sub
        ADD     AL, BL
        JMP     .do_norm

    .do_sub:
        SUB     AL, BL

    .do_norm:
        LZC     AL
        JZ      ZERO, .pack_zero
        CMP     C, 8
        JNZ     CF, .over_r
        JZ      ZERO, .done_norm
        SUB     C, 8
        LSL     AL, C
        EXP_SUB EA, C
        JMP     .done_norm

    .over_r:
        LSR     AL, 1
        EXP_ADD EA, 1

    .done_norm:
        OR      AH, AH
        PACK    AL, EA
        PUSH    AL
        HALT

    .ret_a:
        PUSH    AL
        HALT

    .ret_b:
        PUSH    DL
        HALT

    .pack_zero:
        SUB     AL, AL
        JMP     .ret_a

    .trap_underflow:
        HALT

    .sub_align_f32:
        CMP     EA, EB
        JNZ     CF, .swap_ops
        EXP_SUB C, EA, EB
        CMP     C, #32
        JNZ     CF, .do_shift
        MOV     BL, #0
        RET

    .swap_ops:
        SWAP    AL, BL
        SWAP    EA, EB
        MOV     AH, DL
        EXP_SUB C, EA, EB
        CMP     C, #32
        JNZ     CF, .do_shift
        MOV     BL, #0
        RET

    .do_shift:
        LSR     BL, C
        RET
    """
    tree = parser.parse(program)
    assert tree is not None
