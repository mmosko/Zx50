; =========================
; ADD_I32
; =========================

USER_ADD_I32:
    CALL POP_TWO_32
    ADD AL, BL
    PUSH AL
    HALT
