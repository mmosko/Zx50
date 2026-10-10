; ==============================================================================
; ADD_U32: 32-bit unsigned integer addition: A + B
;
; Inputs:
;   Stack: TOS = 32-bit unsigned integer B, NOS = 32-bit unsigned integer A
;
; Outputs:
;   Stack: TOS = (A + B) mod 2^32
;   Status flags:
;     Updated by ADD AL, BL (ZERO, SIGN, CARRY)
;     OVERFLOW cleared to 0 by PUSH AL
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

USER_ADD_U32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    ADD AL, BL                  ; AL <- A + B (sets CARRY on unsigned overflow)
    PUSH AL                     ; Push result (clears OVERFLOW to 0)
    HALT
