; ==============================================================================
; ADD_I64: 64-bit integer addition
;
; Inputs:
;   Stack: TOS = 64-bit integer B, NOS = 64-bit integer A
;
; Outputs:
;   Stack: TOS = (A + B) mod 2^64
;   Status flags:
;     Updated by ADD AX, BX (ZERO, SIGN, CARRY, OVERFLOW)
;     or set on underflow if stack < 4 words.
;
; Register Allocation:
;   AX (AL, AH) : Operand A (NOS), later sum (A + B)
;   BX (BL, BH) : Operand B (TOS)
;   D, F        : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_64
; ==============================================================================

USER_ADD_I64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    ADD AX, BX                  ; AX <- A + B (64-bit add)
    PUSH AX                     ; Push 64-bit result {AH, AL}
    HALT