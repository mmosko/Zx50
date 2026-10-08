; ==============================================================================
; MUL_I64: 64-bit integer multiplication
;
; Inputs:
;   Stack: TOS = 64-bit integer B, NOS = 64-bit integer A
;
; Outputs:
;   Stack: TOS = (A * B) mod 2^64
;   Status flags:
;     Updated by final ADD (or underflow if stack < 4 words)
;
; Register Allocation:
;   AX (AL, AH) : Operand A (NOS), later low/high words of product
;   BX (BL, BH) : Operand B (TOS), BH accumulates cross terms (T1 + T2)
;   FX (FL, FH) : Scratch copy of operand A (FL = A_lo, FH = A_hi)
;   DX (DL, DH) : Preserved / untouched
; ==============================================================================

USER_MUL_I64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    MOV FX, AX                  ; FX <- A (FL = A_lo, FH = A_hi)
    MULU AL, BH                 ; {AH, AL} <- A_lo * B_hi
    MOV BH, AL                  ; BH <- T1 (low word of cross product 1)
    MOV AL, FH                  ; AL <- A_hi
    MULU AL, BL                 ; {AH, AL} <- A_hi * B_lo
    ADD BH, AL                  ; BH <- T1 + T2
    MOV AL, FL                  ; AL <- A_lo
    MULU AL, BL                 ; {AH, AL} <- A_lo * B_lo
    ADD AH, BH                  ; AH <- (A_lo * B_lo)_hi + T1 + T2
    PUSH AX                     ; Push 64-bit product {AH, AL}
    HALT
