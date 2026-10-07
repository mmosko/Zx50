; =========================
; CHS_F64

USER_CHS_F64:
    POP AX
    JNZ UF, CHS_F64_HALT
    FCHS AX
    PUSH AX
CHS_F64_HALT:
    HALT
