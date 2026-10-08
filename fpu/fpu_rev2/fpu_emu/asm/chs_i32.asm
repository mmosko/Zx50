; ==============================================================================
; CHS_I32: 32-bit integer negation: -X
;
; Inputs:
;   Stack: TOS = 32-bit integer X
;
; Outputs:
;   Stack: TOS = -X (mod 2^32)
;   Status flags:
;     Updated by ADD AL, 1 (ZERO, SIGN, CARRY, OVERFLOW)
;     or set on underflow if stack < 1 word.
;
; Register Allocation:
;   AL : Operand X (TOS), later -X
;   B, D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_CHS_I32:
    CALL POP_ONE_32             ; AL <- X (TOS)
    NOT AL                      ; Bitwise NOT
    ADD AL, 1                   ; Two's complement: ~AL + 1
    PUSH AL                     ; Push negated result
    HALT
