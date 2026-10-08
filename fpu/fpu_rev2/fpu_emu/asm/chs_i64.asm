; ==============================================================================
; CHS_I64: 64-bit integer negation (-X = 0 - X)
;
; Inputs:
;   Stack: TOS = 64-bit integer X
;
; Outputs:
;   Stack: TOS = -X (mod 2^64)
;   Status flags:
;     Updated by SUB AX, FX (ZERO, SIGN, CARRY, OVERFLOW)
;
; Register Allocation:
;   AX (AL, AH) : Operand X, later zero and final negated result
;   FX (FL, FH) : Scratch copy of operand X
;   B, D        : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_64
; ==============================================================================

USER_CHS_I64:
    CALL POP_ONE_64             ; AX <- X (TOS)
    MOV FX, AX                  ; FX <- X (scratch copy)
    XOR AX, AX                  ; AX <- 0
    SUB AX, FX                  ; AX <- 0 - X = -X
    PUSH AX                     ; Push negated result
    HALT
