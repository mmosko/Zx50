; ==============================================================================
; POP_TWO_32 / POP_ONE_32: Shared Subroutines to pop 32-bit operands
;
; POP_TWO_32:
;   Pops two 32-bit operands from the evaluation stack.
;   TOS is popped first into BL, then NOS is popped into AL.
;   If either POP underflows (UF flag set), execution jumps to HALT immediately.
;   Returns via RET if both pops succeed.
;
; POP_ONE_32:
;   Pops a single 32-bit operand from the evaluation stack into AL.
;   If POP underflows (UF flag set), execution jumps to HALT immediately.
;   Returns via RET if the pop succeeds.
;
; Outputs:
;   POP_TWO_32: BL = TOS (32-bit), AL = NOS (32-bit)
;   POP_ONE_32: AL = TOS (32-bit)
;   Status flags:
;     UNDERFLOW (UF) set if stack contains fewer operands than requested.
;
; Register Allocation:
;   AL : Received operand (NOS for two, TOS for one)
;   BL : Received TOS operand (for POP_TWO_32)
;   D, F : Preserved / untouched
; ==============================================================================

POP_TWO_32:
    POP BL                      ; Pop TOS into BL
    JNZ UF, POP_TWO_32_HALT     ; If stack underflow: halt
POP_ONE_32:
    POP AL                      ; Pop NOS (or TOS for POP_ONE_32) into AL
    JNZ UF, POP_TWO_32_HALT     ; If stack underflow: halt
    RET
POP_TWO_32_HALT:
    HALT
