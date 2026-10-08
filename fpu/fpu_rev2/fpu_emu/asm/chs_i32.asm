; =========================
; CHS_I32
; =========================

USER_CHS_I32:
    CALL POP_ONE_32
    MOV BL, AL
    XOR AL, AL
    SUB AL, BL
    PUSH AL
    HALT
