; =========================
; CHS_F32

USER_CHS_F32:
    POP AL
    JNZ UF, CHS_F32_HALT
    FCHS AL
    PUSH AL
CHS_F32_HALT:
    HALT
