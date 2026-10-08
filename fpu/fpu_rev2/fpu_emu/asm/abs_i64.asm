; =========================
; ABS_I64
; =========================

USER_ABS_I64:
    CALL POP_ONE_64
    OR AX, AX
    JZ SIGN, ABS_I64_7
    MOV BX, AX
    XOR AX, AX
    SUB AX, BX
ABS_I64_7:
    PUSH AX
    HALT
