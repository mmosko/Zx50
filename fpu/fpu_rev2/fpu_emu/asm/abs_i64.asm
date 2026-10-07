; =========================
; ABS_I64

USER_ABS_I64:
    POP AX
    JNZ UF, ABS_I64_HALT
    OR AX, AX
    JZ SIGN, ABS_I64_7
    MOV BX, AX
    SUB AX, AX
    SUB AX, BX
ABS_I64_7:
    PUSH AX
ABS_I64_HALT:
    HALT
