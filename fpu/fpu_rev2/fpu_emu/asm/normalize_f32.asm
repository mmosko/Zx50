; ==============================================================================
; NORMALIZE_F32: Subroutine to normalize and pack a float32 result
;
; Inputs:
;   AL : Unnormalized mantissa
;   EA : Exponent
;   AH : Packed float of larger operand (AH[31] holds sign)
;
; Outputs:
;   AL : Normalized, packed IEEE-754 float32
;   Status flags:
;     Updated by PACK AL, EA (or ZF=1 on exact cancellation)
;
; Returns via RET.
; ==============================================================================

NORMALIZE_F32:
    LZC AL                              ; (leading zero count into C)
    JZ ZERO, NORMALIZE_F32_ZERO         ; (exact cancellation: AL == 0)
    CMP C, 8
    JNZ CARRY, NORMALIZE_F32_RIGHT      ; (OVERFLOW_RIGHT: C < 8)
    JZ ZERO, NORMALIZE_F32_DONE         ; (DONE_NORM: C == 8)
    SUB C, 8                            ; (C <- C - 8)
    LSL AL, C                           ; (AL <- AL << C)
    EXP_SUB EA, C                       ; (EA <- EA - C)
    JMP NORMALIZE_F32_DONE
NORMALIZE_F32_RIGHT:
    LDI BL, 8
    SUB BL, C
    LSR AL, BL
    EXP_ADD EA, BL
    JMP NORMALIZE_F32_DONE
NORMALIZE_F32_ZERO:
    XOR AL, AL                          ; AL <- 0
NORMALIZE_F32_DONE:
    OR AH, AH                           ; restores status.sign from bit 31 of AH
    PACK AL, EA
    RET
