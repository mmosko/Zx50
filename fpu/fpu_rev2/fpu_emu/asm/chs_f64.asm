; =========================
; CHS_F64
; =========================

USER_CHS_F64:
    CALL POP_ONE_64
    FCHS AX
    PUSH AX
    HALT
