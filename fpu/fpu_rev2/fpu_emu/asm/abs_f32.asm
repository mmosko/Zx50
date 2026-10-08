; ==============================================================================
; ABS_F32: IEEE-754 Single-Precision Absolute Value: |X|
;
; Inputs:
;   Stack: TOS = float32 X
;
; Outputs:
;   Stack: TOS = float32 |X| (clears bit 31)
;   Status flags:
;     Updated by FABS (clears SIGN flag)
;     or set on underflow if stack < 1 word.
;
; Register Allocation:
;   AL : Operand X (TOS), later |X|
;   B, D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_ABS_F32:
    CALL POP_ONE_32             ; AL <- X (TOS)
    FABS AL                     ; Clear sign bit (AL[31] = 0)
    PUSH AL                     ; Push |X|
    HALT
