; ==============================================================================
; DUP8: Duplicate top 64-bit (8-byte) value on stack
;
; Inputs:
;   Stack: TOS = 64-bit value X (2 words)
;
; Outputs:
;   Stack: TOS = X, NOS = X (4 words total)
;   Status flags:
;     UNDERFLOW set if stack has fewer than 2 words
;
; Register Allocation:
;   AX (AL, AH) : 64-bit value X popped from stack and pushed twice
;   B, D, F     : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_64
; ==============================================================================

USER_DUP8:
    CALL POP_ONE_64             ; AX <- X (TOS)
    PUSH AX                     ; Push first 64-bit copy
    PUSH AX                     ; Push second 64-bit copy
    HALT
