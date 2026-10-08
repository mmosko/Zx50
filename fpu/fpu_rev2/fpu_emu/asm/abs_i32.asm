; =========================
; ABS_I32
; =========================

USER_ABS_I32:
    CALL POP_ONE_32
    OR AL, AL
    JZ SIGN, ABS_I32_DONE
    NOT AL
    ADD AL, 1
ABS_I32_DONE:
    PUSH AL
    HALT
