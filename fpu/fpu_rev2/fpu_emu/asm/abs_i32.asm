; =========================
; ABS_I32
; =========================

USER_ABS_I32:
    CALL POP_ONE_32
    OR AL, AL
    JZ SIGN, ABS_I32_7
    MOV BL, AL
    XOR AL, AL
    SUB AL, BL
ABS_I32_7:
    PUSH AL
    HALT
