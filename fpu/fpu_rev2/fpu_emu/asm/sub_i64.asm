; =========================
; SUB_I64
; =========================

USER_SUB_I64:
    CALL POP_TWO_64
    SUB AX, BX
    PUSH AX
    HALT
