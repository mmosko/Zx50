; =========================
; CHS_I64
; =========================

USER_CHS_I64:
    CALL POP_ONE_64
    MOV BX, AX
    XOR AX, AX
    SUB AX, BX
    PUSH AX
    HALT
