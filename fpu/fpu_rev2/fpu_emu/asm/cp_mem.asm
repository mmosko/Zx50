; ==============================================================================
; CP_MEM: Storage Memory Operations (Opcode range 0xD0..0xF0)
;
; Opcodes:
;   0xD0..0xDF : CP_MEMx_TOS (Store TOS 32-bit value into scratchpad slot 0..15)
;   0xE0..0xEF : CP_TOS_MEMx (Load scratchpad slot 0..15 and push to stack)
;   0xF0       : ZERO_MEM    (Clear all 16 slots of scratchpad storage memory)
;
; Inputs:
;   CP_MEMx_TOS : Stack TOS = 32-bit value (popped into AL)
;   CP_TOS_MEMx : None (loads from storage slot x)
;   ZERO_MEM    : None
;
; Outputs:
;   CP_MEMx_TOS : Storage slot x <- TOS
;   CP_TOS_MEMx : Stack TOS <- Storage slot x
;   ZERO_MEM    : Slots 0..15 cleared to 0
;
; Register Allocation:
;   AL : Value popped from stack (CP_MEMx_TOS) / zero value (ZERO_MEM)
;   AH : Zero value (ZERO_MEM)
;   FL : Value loaded from storage slot and pushed to stack (CP_TOS_MEMx)
;   B, D : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32 (for CP_MEMx_TOS)
; ==============================================================================

USER_CP_MEM0_TOS:
    CALL POP_ONE_32
    STO 0, AL
    HALT

USER_CP_MEM1_TOS:
    CALL POP_ONE_32
    STO 1, AL
    HALT

USER_CP_MEM2_TOS:
    CALL POP_ONE_32
    STO 2, AL
    HALT

USER_CP_MEM3_TOS:
    CALL POP_ONE_32
    STO 3, AL
    HALT

USER_CP_MEM4_TOS:
    CALL POP_ONE_32
    STO 4, AL
    HALT

USER_CP_MEM5_TOS:
    CALL POP_ONE_32
    STO 5, AL
    HALT

USER_CP_MEM6_TOS:
    CALL POP_ONE_32
    STO 6, AL
    HALT

USER_CP_MEM7_TOS:
    CALL POP_ONE_32
    STO 7, AL
    HALT

USER_CP_MEM8_TOS:
    CALL POP_ONE_32
    STO 8, AL
    HALT

USER_CP_MEM9_TOS:
    CALL POP_ONE_32
    STO 9, AL
    HALT

USER_CP_MEM10_TOS:
    CALL POP_ONE_32
    STO 10, AL
    HALT

USER_CP_MEM11_TOS:
    CALL POP_ONE_32
    STO 11, AL
    HALT

USER_CP_MEM12_TOS:
    CALL POP_ONE_32
    STO 12, AL
    HALT

USER_CP_MEM13_TOS:
    CALL POP_ONE_32
    STO 13, AL
    HALT

USER_CP_MEM14_TOS:
    CALL POP_ONE_32
    STO 14, AL
    HALT

USER_CP_MEM15_TOS:
    CALL POP_ONE_32
    STO 15, AL
    HALT

USER_CP_TOS_MEM0:
    LD FL, 0
    JMP CP_TOS_HALT

USER_CP_TOS_MEM1:
    LD FL, 1
    JMP CP_TOS_HALT

USER_CP_TOS_MEM2:
    LD FL, 2
    JMP CP_TOS_HALT

USER_CP_TOS_MEM3:
    LD FL, 3
    JMP CP_TOS_HALT

USER_CP_TOS_MEM4:
    LD FL, 4
    JMP CP_TOS_HALT

USER_CP_TOS_MEM5:
    LD FL, 5
    JMP CP_TOS_HALT

USER_CP_TOS_MEM6:
    LD FL, 6
    JMP CP_TOS_HALT

USER_CP_TOS_MEM7:
    LD FL, 7
    JMP CP_TOS_HALT

USER_CP_TOS_MEM8:
    LD FL, 8
    JMP CP_TOS_HALT

USER_CP_TOS_MEM9:
    LD FL, 9
    JMP CP_TOS_HALT

USER_CP_TOS_MEM10:
    LD FL, 10
    JMP CP_TOS_HALT

USER_CP_TOS_MEM11:
    LD FL, 11
    JMP CP_TOS_HALT

USER_CP_TOS_MEM12:
    LD FL, 12
    JMP CP_TOS_HALT

USER_CP_TOS_MEM13:
    LD FL, 13
    JMP CP_TOS_HALT

USER_CP_TOS_MEM14:
    LD FL, 14
    JMP CP_TOS_HALT

USER_CP_TOS_MEM15:
    LD FL, 15
CP_TOS_HALT:
    PUSH FL
    HALT

USER_ZERO_MEM:
    XOR AL, AL
    XOR AH, AH
    STO.64 0, AL
    STO.64 2, AL
    STO.64 4, AL
    STO.64 6, AL
    STO.64 8, AL
    STO.64 10, AL
    STO.64 12, AL
    STO.64 14, AL
    HALT
