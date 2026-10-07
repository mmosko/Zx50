; =========================
; ABS_I32

USER_ABS_I32:
    POP AL
    JNZ UF, ABS_I32_HALT
    OR AL, AL
    JZ SIGN, ABS_I32_7
    MOV BL, AL
    SUB AL, AL
    SUB AL, BL
ABS_I32_7:
    PUSH AL
ABS_I32_HALT:
    HALT
