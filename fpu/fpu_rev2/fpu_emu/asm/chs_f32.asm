; ==============================================================================
; CHS_F32: IEEE-754 Single-Precision Negation: -X
;
; Inputs:
;   Stack: TOS = float32 X
;
; Outputs:
;   Stack: TOS = float32 -X (inverts bit 31)
;   Status flags:
;     Updated by FCHS (inverts SIGN flag)
;     or set on underflow if stack < 1 word.
;
; Register Allocation:
;   AL : Operand X (TOS), later -X
;   B, D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_CHS_F32:
    CALL POP_ONE_32             ; AL <- X (TOS)
    FCHS AL                     ; Invert sign bit (AL[31] ^= 1)
    PUSH AL                     ; Push -X
    HALT
