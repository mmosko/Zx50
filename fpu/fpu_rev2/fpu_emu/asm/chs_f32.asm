; =========================
; CHS_F32
; =========================

USER_CHS_F32:
    CALL POP_ONE_32
    FCHS AL
    PUSH AL
    HALT
