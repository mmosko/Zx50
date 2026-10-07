; =========================
; DIV_I32

USER_DIV_I32:
    POP BL                          ; divisor b
    JNZ UF, DIV_I32_HALT
    POP AL                          ; dividend a
    JNZ UF, DIV_I32_HALT
    DIV AL, BL
    JNZ ERR, DIV_I32_HALT           ; don'\''t push quotient if divide-by-zero error
    PUSH AL
DIV_I32_HALT:
    HALT
