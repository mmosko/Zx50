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
;   C  : Slot index (0..15) latched by dispatcher / loop counter for ZERO_MEM
;   FL : Value loaded from storage slot and pushed to stack (CP_TOS_MEMx)
;   B, D : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32 (for CP_MEMx_TOS)
; ==============================================================================

USER_CP_MEM0_TOS:
USER_CP_MEM1_TOS:
USER_CP_MEM2_TOS:
USER_CP_MEM3_TOS:
USER_CP_MEM4_TOS:
USER_CP_MEM5_TOS:
USER_CP_MEM6_TOS:
USER_CP_MEM7_TOS:
USER_CP_MEM8_TOS:
USER_CP_MEM9_TOS:
USER_CP_MEM10_TOS:
USER_CP_MEM11_TOS:
USER_CP_MEM12_TOS:
USER_CP_MEM13_TOS:
USER_CP_MEM14_TOS:
USER_CP_MEM15_TOS:
    CALL POP_ONE_32
    STO [C], AL
    HALT

USER_CP_TOS_MEM0:
USER_CP_TOS_MEM1:
USER_CP_TOS_MEM2:
USER_CP_TOS_MEM3:
USER_CP_TOS_MEM4:
USER_CP_TOS_MEM5:
USER_CP_TOS_MEM6:
USER_CP_TOS_MEM7:
USER_CP_TOS_MEM8:
USER_CP_TOS_MEM9:
USER_CP_TOS_MEM10:
USER_CP_TOS_MEM11:
USER_CP_TOS_MEM12:
USER_CP_TOS_MEM13:
USER_CP_TOS_MEM14:
USER_CP_TOS_MEM15:
    LD FL, [C]
    PUSH FL
    HALT

USER_ZERO_MEM:
    XOR AL, AL
    LDI C, 15
ZERO_MEM_LOOP:
    STO [C], AL
    DJNZ ZERO_MEM_LOOP
    STO [C], AL
    HALT
