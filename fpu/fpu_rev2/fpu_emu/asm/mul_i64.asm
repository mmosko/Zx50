; =========================
; MUL_I64

USER_MUL_I64:
    POP BX
    JNZ UF, MUL_I64_HALT
    STO 0, BX
    POP AX
    JNZ UF, MUL_I64_HALT
    STO 2, AX
    LD BL, 1
    MULU AL, BL
    STO 4, AL
    LD AL, 3
    LD BL, 0
    MULU AL, BL
    LD BL, 4
    ADD AL, BL
    STO 4, AL
    LD AL, 2
    LD BL, 0
    MULU AL, BL
    LD BL, 4
    ADD AH, BL
    PUSH AX
MUL_I64_HALT:
    HALT
