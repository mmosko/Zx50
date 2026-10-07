; =========================
; ADD_I32

USER_ADD_I32:
    POP BL
    JNZ UF, ADD_I32_HALT
    POP AL
    JNZ UF, ADD_I32_HALT
    ADD AL, BL
    PUSH AL
ADD_I32_HALT:
    HALT
