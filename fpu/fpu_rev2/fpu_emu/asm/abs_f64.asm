; ==============================================================================
; ABS_F64: IEEE-754 Double-Precision Absolute Value: |X|
;
; Inputs:
;   Stack: TOS = float64 X
;
; Outputs:
;   Stack: TOS = float64 |X| (clears bit 63 in high word AH)
;   Status flags:
;     Updated by FABS (clears SIGN flag)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AX (AL, AH) : Operand X (TOS), later |X|
;   B, D, F     : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_64
; ==============================================================================

USER_ABS_F64:
    CALL POP_ONE_64             ; AX <- X (TOS)
    FABS AX                     ; Clear sign bit (AH[31] = 0)
    PUSH AX                     ; Push 64-bit |X|
    HALT
