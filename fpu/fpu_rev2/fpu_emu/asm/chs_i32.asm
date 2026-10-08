; =========================
; CHS_I32
; =========================

USER_CHS_I32:
    CALL POP_ONE_32
    NOT AL
    ADD AL, 1
    PUSH AL
    HALT
