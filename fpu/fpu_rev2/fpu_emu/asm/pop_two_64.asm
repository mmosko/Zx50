; ==============================================================================
; POP_TWO_64: Pop two 64-bit operands from stack into BX (TOS) and AX (NOS)
; POP_ONE_64: Pop one 64-bit operand from stack into AX (TOS)
; Halts immediately on underflow.
; ==============================================================================

POP_TWO_64:
    POP BX
    JNZ UF, POP_TWO_64_HALT
POP_ONE_64:
    POP AX
    JNZ UF, POP_TWO_64_HALT
    RET
POP_TWO_64_HALT:
    HALT
