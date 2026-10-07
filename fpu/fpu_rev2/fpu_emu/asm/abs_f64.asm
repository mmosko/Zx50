; =========================
; ABS_F64

USER_ABS_F64:
    POP AX
    JNZ UF, ABS_F64_HALT
    FABS AX
    PUSH AX
ABS_F64_HALT:
    HALT
