; ==============================================================================
; SUB_F32: IEEE-754 Single-Precision Subtraction
;
; Operation:
;   A - B = A + (-B)
;
; Inputs:
;   Stack: TOS = float32 B, NOS = float32 A
;
; Outputs:
;   Stack: TOS = float32 (A - B)
;   Status flags:
;     Updated by NORMALIZE_F32 (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Operand A (NOS)
;   BL : Operand B (TOS), inverted via FCHS BL
;   Shares all registers and logic with ADD_F32_CORE.
;
; Subroutines Called:
;   POP_TWO_32, ALIGN_F32, NORMALIZE_F32
; ==============================================================================

USER_SUB_F32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    CALL SUB_F32_CORE           ; AL <- A - B
    PUSH AL                     ; Push result
    HALT

SUB_F32_CORE:
    FCHS BL                     ; Invert sign bit of subtrahend: B <- -B
    CALL ADD_F32_CORE           ; Add A + (-B)
    RET