; ==============================================================================
; ABS_I64: 64-bit integer absolute value (|X|)
;
; Inputs:
;   Stack: TOS = 64-bit integer X
;
; Outputs:
;   Stack: TOS = |X| (if X >= 0: X; if X < 0: -X)
;   Status flags:
;     Updated by OR or SUB (ZERO, SIGN, CARRY, OVERFLOW)
;
; Register Allocation:
;   AX (AL, AH) : Operand X, later |X|
;   FX (FL, FH) : Scratch copy of operand X if negative
;   B, D        : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_64
; ==============================================================================

USER_ABS_I64:
    CALL POP_ONE_64             ; AX <- X (TOS)
    OR AX, AX                   ; Test sign bit (AH[31])
    JZ SIGN, ABS_I64_DONE       ; If positive (SIGN == 0): already non-negative
    MOV FX, AX                  ; FX <- X (scratch copy)
    XOR AX, AX                  ; AX <- 0
    SUB AX, FX                  ; AX <- 0 - X = -X
ABS_I64_DONE:
    PUSH AX                     ; Push |X|
    HALT
