; =========================
; MUL_I64
; =========================

USER_MUL_I64:
    CALL POP_TWO_64
    MOV DL, AL                  ; DL <- A_lo
    MOV DH, BL                  ; DH <- B_lo
    MOV FL, AH                  ; FL <- A_hi
    MULU AL, BH                 ; {AH, AL} <- A_lo * B_hi
    MOV BH, AL                  ; BH <- T1 (cross term 1)
    MOV AL, FL                  ; AL <- A_hi
    MULU AL, DH                 ; {AH, AL} <- A_hi * B_lo
    ADD BH, AL                  ; BH <- T1 + T2
    MOV AL, DL                  ; AL <- A_lo
    MOV BL, DH                  ; BL <- B_lo
    MULU AL, BL                 ; {AH, AL} <- A_lo * B_lo
    ADD AH, BH                  ; AH <- (A_lo * B_lo)_hi + T1 + T2
    PUSH AX
    HALT
