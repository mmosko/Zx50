; =========================
; DUP8

USER_DUP8:
    POP AX
    JNZ UF, DUP8_HALT
    PUSH AX
    PUSH AX
DUP8_HALT:
    HALT
