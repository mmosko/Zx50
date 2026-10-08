; ==============================================================================
; PUSH_CONST: Mathematical Constant Load Handlers (Opcode range 0xA0..0xAF)
;
; Opcodes:
;   0xA0: PUSH_PI_32       0xA8: PUSH_PI_64
;   0xA1: PUSH_E_32        0xA9: PUSH_E_64
;   0xA2: PUSH_LN2_32      0xAA: PUSH_LN2_64
;   0xA3: PUSH_LOG2E_32    0xAB: PUSH_LOG2E_64
;   0xA4: PUSH_LOG2_10_32  0xAC: PUSH_LOG2_10_64
;   0xA5: PUSH_LOG10_2_32  0xAD: PUSH_LOG10_2_64
;   0xA6: PUSH_SQRT2_32    0xAE: PUSH_SQRT2_64
;   0xA7: PUSH_INV_SQRT2_32 0xAF: PUSH_INV_SQRT2_64
;
; Inputs:
;   None (stack unchanged prior to push)
;
; Outputs:
;   Stack: Pushes 32-bit (FL) or 64-bit (FX) constant loaded from CONST ROM
;
; Register Allocation:
;   FL : 32-bit constant loaded via LDC FL, CONST, slot
;   FX : 64-bit constant loaded via LDC FX, CONST, slot
;   A, B, D : Preserved / untouched
; ==============================================================================

.equ PI_F32, 0
.equ PI_F64, 2
.equ E_F32, 4
.equ E_F64, 6
.equ LN2_F32, 8
.equ LN2_F64, 10
.equ LOG2E_F32, 12
.equ LOG2E_F64, 14
.equ LOG2_10_F32, 16
.equ LOG2_10_F64, 18
.equ LOG10_2_F32, 20
.equ LOG10_2_F64, 22
.equ SQRT2_F32, 24
.equ SQRT2_F64, 26
.equ INV_SQRT2_F32, 28
.equ INV_SQRT2_F64, 30

USER_PUSH_PI_32:
    LDC FL, CONST, PI_F32
    JMP PUSH_FL_HALT

USER_PUSH_E_32:
    LDC FL, CONST, E_F32
    JMP PUSH_FL_HALT

USER_PUSH_LN2_32:
    LDC FL, CONST, LN2_F32
    JMP PUSH_FL_HALT

USER_PUSH_LOG2E_32:
    LDC FL, CONST, LOG2E_F32
    JMP PUSH_FL_HALT

USER_PUSH_LOG2_10_32:
    LDC FL, CONST, LOG2_10_F32
    JMP PUSH_FL_HALT

USER_PUSH_LOG10_2_32:
    LDC FL, CONST, LOG10_2_F32
    JMP PUSH_FL_HALT

USER_PUSH_SQRT2_32:
    LDC FL, CONST, SQRT2_F32
    JMP PUSH_FL_HALT

USER_PUSH_INV_SQRT2_32:
    LDC FL, CONST, INV_SQRT2_F32
PUSH_FL_HALT:
    PUSH FL
    HALT

USER_PUSH_PI_64:
    LDC FX, CONST, PI_F64
    JMP PUSH_FX_HALT

USER_PUSH_E_64:
    LDC FX, CONST, E_F64
    JMP PUSH_FX_HALT

USER_PUSH_LN2_64:
    LDC FX, CONST, LN2_F64
    JMP PUSH_FX_HALT

USER_PUSH_LOG2E_64:
    LDC FX, CONST, LOG2E_F64
    JMP PUSH_FX_HALT

USER_PUSH_LOG2_10_64:
    LDC FX, CONST, LOG2_10_F64
    JMP PUSH_FX_HALT

USER_PUSH_LOG10_2_64:
    LDC FX, CONST, LOG10_2_F64
    JMP PUSH_FX_HALT

USER_PUSH_SQRT2_64:
    LDC FX, CONST, SQRT2_F64
    JMP PUSH_FX_HALT

USER_PUSH_INV_SQRT2_64:
    LDC FX, CONST, INV_SQRT2_F64
PUSH_FX_HALT:
    PUSH FX
    HALT
