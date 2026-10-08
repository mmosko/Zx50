; ==============================================================================
; SUB_I64: 64-bit integer subtraction: A - B
;
; Inputs:
;   Stack: TOS = 64-bit integer B (subtrahend), NOS = 64-bit integer A (minuend)
;
; Outputs:
;   Stack: TOS = (A - B) mod 2^64
;   Status flags:
;     Updated by SUB AX, BX (ZERO, SIGN, CARRY, OVERFLOW)
;     or set on underflow if stack < 4 words.
;
; Register Allocation:
;   AX (AL, AH) : Operand A (NOS), later difference (A - B)
;   BX (BL, BH) : Operand B (TOS)
;   D, F        : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_64
; ==============================================================================

USER_SUB_I64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    SUB AX, BX                  ; AX <- A - B (64-bit sub)
    PUSH AX                     ; Push 64-bit result {AH, AL}
    HALT
