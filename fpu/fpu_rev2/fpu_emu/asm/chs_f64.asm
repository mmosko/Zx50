; ==============================================================================
; CHS_F64: IEEE-754 Double-Precision Negation: -X
;
; Inputs:
;   Stack: TOS = float64 X
;
; Outputs:
;   Stack: TOS = float64 -X (inverts bit 63 in high word AH)
;   Status flags:
;     Updated by FCHS (inverts SIGN flag)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AX (AL, AH) : Operand X (TOS), later -X
;   B, D, F     : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_64
; ==============================================================================

USER_CHS_F64:
    CALL POP_ONE_64             ; AX <- X (TOS)
    FCHS AX                     ; Invert sign bit (AH[31] ^= 1)
    PUSH AX                     ; Push 64-bit -X
    HALT
