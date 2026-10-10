; ==============================================================================
; SUB_U32: 32-bit unsigned integer subtraction: A - B
;
; Inputs:
;   Stack: TOS = 32-bit unsigned integer B (subtrahend), NOS = 32-bit unsigned integer A (minuend)
;
; Outputs:
;   Stack: TOS = (A - B) mod 2^32
;   Status flags:
;     Updated by SUB AL, BL (ZERO, SIGN, CARRY)
;     OVERFLOW cleared to 0 by PUSH AL
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

USER_SUB_U32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    SUB AL, BL                  ; AL <- A - B (sets CARRY on unsigned borrow, A < B)
    PUSH AL                     ; Push result (clears OVERFLOW to 0)
    HALT
