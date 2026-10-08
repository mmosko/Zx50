; ==============================================================================
; MUL_I32: 32-bit signed integer multiplication: A * B
;
; Inputs:
;   Stack: TOS = 32-bit integer B, NOS = 32-bit integer A
;
; Outputs:
;   Stack: TOS = (A * B) mod 2^32
;   Status flags:
;     Updated by MUL AL, BL (ZERO, SIGN, OVERFLOW)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Operand A (NOS), later product (A * B) low word
;   BL : Operand B (TOS)
;   AH : High word of 64-bit product (clobbered by 32x32 MUL)
;   D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32
; ==============================================================================

USER_MUL_I32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    MUL AL, BL                  ; {AH, AL} <- A * B
    PUSH AL                     ; Push low 32 bits of product
    HALT
