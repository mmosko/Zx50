; =========================
; ADD_I64
; =========================

USER_ADD_I64:
    CALL POP_TWO_64
    ADD AX, BX
    PUSH AX
    HALT