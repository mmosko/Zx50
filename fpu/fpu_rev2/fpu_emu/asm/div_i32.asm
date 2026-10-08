; ==============================================================================
; DIV_I32: 32-bit signed integer division: A / B
;
; Inputs:
;   Stack: TOS = 32-bit integer B (divisor), NOS = 32-bit integer A (dividend)
;
; Outputs:
;   Stack: TOS = quotient (A / B) truncated toward zero
;   Status flags:
;     ERR set if B == 0 (division by zero, aborts without pushing quotient)
;     Updated by DIV (ZERO, SIGN, OVERFLOW)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Dividend A (NOS), later quotient (A / B)
;   BL : Divisor B (TOS)
;   DL : Remainder (A % B), written by hardware divider
;   F  : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32
; ==============================================================================

USER_DIV_I32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    DIV AL, BL                  ; AL <- quotient, DL <- remainder
    JNZ ERR, DIV_I32_HALT       ; If divide-by-zero: abort without pushing quotient
    PUSH AL                     ; Push quotient
DIV_I32_HALT:
    HALT
