; ==============================================================================
; POP_TWO_32: Pop two 32-bit operands from stack into BL (TOS) and AL (NOS)
; POP_ONE_32: Pop one 32-bit operand from stack into AL (TOS)
; Halts immediately on underflow.
; ==============================================================================

POP_TWO_32:
    POP BL
    JNZ UF, POP_TWO_32_HALT
POP_ONE_32:
    POP AL
    JNZ UF, POP_TWO_32_HALT
    RET
POP_TWO_32_HALT:
    HALT
