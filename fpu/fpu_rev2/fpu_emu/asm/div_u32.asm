; ==============================================================================
; DIV_U32: 32-bit unsigned integer division: A / B
;
; Inputs:
;   Stack: TOS = 32-bit unsigned integer B (divisor), NOS = 32-bit unsigned integer A (dividend)
;
; Outputs:
;   Stack: TOS = quotient (A / B)
;   Status flags:
;     ERR set if B == 0 (division by zero, aborts without pushing quotient)
;     Updated by DIVU (ZERO, SIGN)
;     OVERFLOW cleared to 0 (or set on divide-by-zero)
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

USER_DIV_U32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    DIVU AL, BL                 ; AL <- quotient, DL <- remainder
    JNZ ERR, DIV_U32_HALT       ; If divide-by-zero: abort without pushing quotient
    PUSH AL                     ; Push quotient (clears VF to 0)
DIV_U32_HALT:
    HALT
