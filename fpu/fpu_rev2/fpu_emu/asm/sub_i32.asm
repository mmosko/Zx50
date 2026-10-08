; =========================
; SUB_I32
; =========================

USER_SUB_I32:
    CALL POP_TWO_32
    SUB AL, BL
    PUSH AL
    HALT
