; =========================
; SUB_I64

USER_SUB_I64:
    POP BX
    JNZ UF, SUB_I64_HALT
    POP AX
    JNZ UF, SUB_I64_HALT
    SUB AX, BX
    PUSH AX
SUB_I64_HALT:
    HALT
