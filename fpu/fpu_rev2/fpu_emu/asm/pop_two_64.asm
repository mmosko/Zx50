; ==============================================================================
; POP_TWO_64 / POP_ONE_64: Shared Subroutines to pop 64-bit operands
;
; POP_TWO_64:
;   Pops two 64-bit operands from the evaluation stack.
;   TOS is popped first into BX {BH, BL}, then NOS is popped into AX {AH, AL}.
;   If either POP underflows (UF flag set), execution jumps to HALT immediately.
;   Returns via RET if both pops succeed.
;
; POP_ONE_64:
;   Pops a single 64-bit operand from the evaluation stack into AX {AH, AL}.
;   If POP underflows (UF flag set), execution jumps to HALT immediately.
;   Returns via RET if the pop succeeds.
;
; Outputs:
;   POP_TWO_64: BX = TOS (64-bit), AX = NOS (64-bit)
;   POP_ONE_64: AX = TOS (64-bit)
;   Status flags:
;     UNDERFLOW (UF) set if stack contains fewer operands than requested.
;
; Register Allocation:
;   AX (AL, AH) : Received operand (NOS for two, TOS for one)
;   BX (BL, BH) : Received TOS operand (for POP_TWO_64)
;   D, F        : Preserved / untouched
; ==============================================================================

POP_TWO_64:
    POP BX                      ; Pop 64-bit TOS into BX
    JNZ UF, POP_TWO_64_HALT     ; If stack underflow: halt
POP_ONE_64:
    POP AX                      ; Pop 64-bit NOS (or TOS for POP_ONE_64) into AX
    JNZ UF, POP_TWO_64_HALT     ; If stack underflow: halt
    RET
POP_TWO_64_HALT:
    HALT
