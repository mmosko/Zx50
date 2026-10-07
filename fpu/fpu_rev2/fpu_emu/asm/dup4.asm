; =========================
; DUP4

USER_DUP4:
    POP AL
    JNZ UF, DUP4_HALT
    PUSH AL
    PUSH AL
DUP4_HALT:
    HALT
