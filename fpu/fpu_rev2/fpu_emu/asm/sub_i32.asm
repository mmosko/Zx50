; =========================
; SUB_I32

USER_SUB_I32:
    POP BL
    JNZ UF, SUB_I32_HALT
    POP AL
    JNZ UF, SUB_I32_HALT
    SUB AL, BL
    PUSH AL
SUB_I32_HALT:
    HALT

