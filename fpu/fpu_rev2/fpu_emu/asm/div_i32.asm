; =========================
; DIV_I32
; =========================

USER_DIV_I32:
    CALL POP_TWO_32
    DIV AL, BL
    JNZ ERR, DIV_I32_HALT           ; don't push quotient if divide-by-zero error
    PUSH AL
DIV_I32_HALT:
    HALT
