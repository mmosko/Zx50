; ==============================================================================
; SUB_I32: 32-bit integer subtraction: A - B
;
; Inputs:
;   Stack: TOS = 32-bit integer B (subtrahend), NOS = 32-bit integer A (minuend)
;
; Outputs:
;   Stack: TOS = (A - B) mod 2^32
;   Status flags:
;     Updated by SUB AL, BL (ZERO, SIGN, CARRY, OVERFLOW)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Operand A (NOS), later difference (A - B)
;   BL : Operand B (TOS)
;   D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32
; ==============================================================================

USER_SUB_I32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    SUB AL, BL                  ; AL <- A - B
    PUSH AL                     ; Push result
    HALT
