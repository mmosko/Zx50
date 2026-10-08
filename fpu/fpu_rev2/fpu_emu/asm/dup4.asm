; ==============================================================================
; DUP4: Duplicate top 32-bit (4-byte) value on stack
;
; Inputs:
;   Stack: TOS = 32-bit word X
;
; Outputs:
;   Stack: TOS = X, NOS = X
;   Status flags:
;     UNDERFLOW set if stack is empty
;
; Register Allocation:
;   AL : Value X popped from stack and pushed twice
;   B, D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_DUP4:
    CALL POP_ONE_32             ; AL <- X (TOS)
    PUSH AL                     ; Push first copy
    PUSH AL                     ; Push second copy
    HALT
