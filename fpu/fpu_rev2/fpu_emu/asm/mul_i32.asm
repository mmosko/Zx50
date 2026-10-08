; =========================
; MUL_I32
; =========================

USER_MUL_I32:
    CALL POP_TWO_32
    MUL AL, BL
    PUSH AL
    HALT
