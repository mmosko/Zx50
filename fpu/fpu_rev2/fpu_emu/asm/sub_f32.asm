; ==============================================================================
; SUB_F32: IEEE-754 Single-Precision Subtraction: A - B = A + (-B)
; ==============================================================================

USER_SUB_F32:
    CALL POP_TWO_32
    FCHS BL                        ; (invert sign bit: B <- -B)
    JMP ADD_F32_CORE