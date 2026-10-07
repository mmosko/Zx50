; =========================
; DUP8

USER_DUP8:
    POP FX
    JNZ UF, DUP8_HALT
    PUSH FX
    PUSH FX
DUP8_HALT:
    HALT
