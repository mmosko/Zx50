; ==============================================================================
; ABS_I32: 32-bit integer absolute value: |X|
;
; Inputs:
;   Stack: TOS = 32-bit integer X
;
; Outputs:
;   Stack: TOS = |X| (if X >= 0: X; if X < 0: -X)
;   Status flags:
;     Updated by OR or ADD (ZERO, SIGN, CARRY, OVERFLOW)
;     or set on underflow if stack < 1 word.
;
; Register Allocation:
;   AL : Operand X (TOS), later |X|
;   B, D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_ABS_I32:
    CALL POP_ONE_32             ; AL <- X (TOS)
    OR AL, AL                   ; Test sign bit (AL[31])
    JZ SIGN, ABS_I32_DONE       ; If positive (SIGN == 0): already non-negative
    NOT AL                      ; Negate in place: bitwise NOT
    ADD AL, 1                   ; Two's complement negation: ~AL + 1
ABS_I32_DONE:
    PUSH AL                     ; Push |X|
    HALT
