; =========================
; MUL_I32

USER_MUL_I32:
    POP BL
    JNZ UF, MUL_I32_HALT
    POP AL
    JNZ UF, MUL_I32_HALT
    MUL AL, BL
    PUSH AL
MUL_I32_HALT:
    HALT
