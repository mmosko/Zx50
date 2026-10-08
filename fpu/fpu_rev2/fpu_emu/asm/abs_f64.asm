; =========================
; ABS_F64
; =========================

USER_ABS_F64:
    CALL POP_ONE_64
    FABS AX
    PUSH AX
    HALT
