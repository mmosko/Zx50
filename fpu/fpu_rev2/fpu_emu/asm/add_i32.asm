; ==============================================================================
; ADD_I32: 32-bit integer addition
;
; Inputs:
;   Stack: TOS = 32-bit integer B, NOS = 32-bit integer A
;
; Outputs:
;   Stack: TOS = (A + B) mod 2^32
;   Status flags:
;     Updated by ADD AL, BL (ZERO, SIGN, CARRY, OVERFLOW)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Operand A (NOS), later sum (A + B)
;   BL : Operand B (TOS)
;   D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32
; ==============================================================================

USER_ADD_I32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    ADD AL, BL                  ; AL <- A + B
    PUSH AL                     ; Push result
    HALT
