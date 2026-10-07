; =========================
; ADD_I64

USER_ADD_I64:
    POP BX
    JNZ UF, ADD_I64_HALT
    POP AX
    JNZ UF, ADD_I64_HALT
    ADD AX, BX
    PUSH AX
ADD_I64_HALT:
    HALT
   