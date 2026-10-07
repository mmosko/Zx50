; =========================
; DUP4

USER_DUP4:
    POP FL
    JNZ UF, DUP4_HALT
    PUSH FL
    PUSH FL
DUP4_HALT:
    HALT
