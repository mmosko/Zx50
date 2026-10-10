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
;   BX (BL, BH) : Operand B (TOS), preserved
;   CX (CL, CH) : Scratch copy of operand A (CL = A_lo, CH = A_hi),
;                 CH accumulates cross terms (T2 + T1)
;   DX (DL, DH) : Preserved / untouched
;   FX (FL, FH) : Preserved / untouched
; ==============================================================================

USER_MUL_I64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    MOV CX, AX                  ; CX <- A (CL = A_lo, CH = A_hi)
    MULU AL, CH, BL             ; {AH, AL} <- A_hi * B_lo
    MOV CH, AL                  ; CH <- T2
    MULU AL, CL, BH             ; {AH, AL} <- A_lo * B_hi
    ADD CH, CH, AL              ; CH <- T2 + T1
    MULU AL, CL, BL             ; {AH, AL} <- A_lo * B_lo
    ADD AH, AH, CH              ; AH <- (A_lo * B_lo)_hi + T1 + T2
    PUSH AX                     ; Push 64-bit product {AH, AL}
    HALT
