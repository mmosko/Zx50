; =========================
; ABS_F32
; =========================

USER_ABS_F32:
    CALL POP_ONE_32
    FABS AL
    PUSH AL
    HALT
