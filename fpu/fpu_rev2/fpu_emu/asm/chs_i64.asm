; =========================
; CHS_I64

USER_CHS_I64:
    POP BX
    JNZ UF, CHS_I64_HALT
    SUB AX, AX
    SUB AX, BX
    PUSH AX
CHS_I64_HALT:
    HALT
