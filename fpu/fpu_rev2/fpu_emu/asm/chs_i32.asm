; =========================
; CHS_I32

USER_CHS_I32:
    POP BL
    JNZ UF, CHS_I32_HALT
    SUB AL, AL
    SUB AL, BL
    PUSH AL
CHS_I32_HALT:
    HALT
