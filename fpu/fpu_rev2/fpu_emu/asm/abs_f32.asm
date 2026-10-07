; =========================
; ABS_F32

USER_ABS_F32:
    POP AL
    JNZ UF, ABS_F32_HALT
    FABS AL
    PUSH AL
ABS_F32_HALT:
    HALT
