; ==============================================================================
; MUL_U32: 32-bit unsigned integer multiplication: A * B
;
; Inputs:
;   Stack: TOS = 32-bit unsigned integer B, NOS = 32-bit unsigned integer A
;
; Outputs:
;   Stack: TOS = (A * B) mod 2^32
;   Status flags:
;     CARRY set to 1 if upper 32 bits non-zero (AH != 0); cleared to 0 otherwise
;     OVERFLOW cleared to 0
;     ZERO, SIGN updated
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Operand A (NOS), later product (A * B) low word
;   BL : Operand B (TOS)
;   AH : High word of 64-bit product (clobbered by 32x32 MULU)
;   D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32
; ==============================================================================

USER_MUL_U32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    MULU AL, BL                 ; {AH, AL} <- A * B; VF set if AH != 0
    JZ VF, MUL_U32_NO_CARRY     ; If VF == 0 (no overflow), skip setting CARRY
    LDI CARRY, 1                ; High 32-bit product non-zero: set CARRY = 1
MUL_U32_NO_CARRY:
    PUSH AL                     ; Push low 32 bits of product (clears VF to 0)
    HALT
