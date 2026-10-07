
; =========================
; ADD_I32

ADD_I32:
    POP BL
    JNZ UF, ADD_I32_HALT
    POP AL
    JNZ UF, ADD_I32_HALT
    ADD AL, BL
    PUSH AL
ADD_I32_HALT:
    HALT
    
; =========================
; ADD_F32
ADD_F32:
    POP BL (pop operand B)
    JNZ UNDERFLOW, ADD_F32_HALT
    MOV DL, BL                  ; stash packed B into DL
    POP AL
    JNZ UNDERFLOW, ADD_F32_HALT
    MOV AH, AL                  ; stash packed A into AH for sign preservation)
    UNPACK BL, EB
    JZ ZERO, ADD_F32_RETURN_A   ; (RETURN_A: jump to PUSH AL, HALT)
    UNPACK AL, EA
    JZ ZERO, ADD_F32_RETURN_B    ; (RETURN_B: jump to PUSH DL, HALT)
    CMP EA, EB
    JNZ CARRY, ADD_F32_16        ; (SWAP_OPS: EA < EB)
    JNZ ZERO, ADD_F32_19         ;   (ALIGN_EXP: EA > EB)
    CMP AL, BL
    JNZ CARRY, ADD_F32_16        ; (SWAP_OPS: AL < BL)
    JMP ADD_F32_19               ; (ALIGN_EXP: AL >= BL)
ADD_F32_16:
    SWAP AL, BL                 ; (larger mantissa in AL)
    SWAP EA, EB                 ; (larger exponent in EA)
    MOV AH, DL                  ; (AH now holds packed B with sign S_B)
ADD_F32_19:
    EXP_SUB C, EA, EB           ; (C <- EA - EB; EA preserved!)
    CMP C, 32
    JNZ CARRY, ADD_F32_24       ; (DO_SHIFT: diff < 32)
    MOV BL, IMM=0               ; (diff >= 32: smaller mantissa shifts to 0)
    JMP ADD_F32_24              ; (DO_ARITH)
ADD_F32_24:
    LSR BL, C                   ; (shift BL right by C)
ADD_F32_25:
    JNZ DIFF_SIGN, ADD_F32_28   ; (DO_SUB)
    ADD AL, BL
    JMP NORMALIZE               ; (NORMALIZE)
ADD_F32_28:
    SUB AL, BL
NORMALIZE:
    LZC AL                              ; (leading zero count into C)
    JZ ZERO, ADD_F32_46               ; (PACK_ZERO: exact cancellation)
    CMP C, 8
    JNZ CARRY, ADD_F32_OVERFLOW_RIGHT   ; (OVERFLOW_RIGHT: C < 8)
    JZ ZERO -> ADD_F32_DONE_NORM        ; (DONE_NORM: C == 8)
    SUB C, 8                            ; (C <- C - 8)
    LSL AL, C                           ; (AL <- AL << C)
    EXP_SUB EA, C                       ; (EA <- EA - C)
    JMP ADD_F32_DONE_NORM
ADD_F32_OVERFLOW_RIGHT:
    LSR AL, 1
    EXP_ADD EA, 1
ADD_F32_DONE_NORM:
    OR AH, AH                       ; restores status.sign from bit 31 of AH
    PACK AL, EA
ADD_F32_RETURN_A:
    PUSH AL
    HALT
ADD_F32_RETURN_B:
    PUSH DL ; RETURN_B
    HALT
ADD_F32_46:
    SUB AL, AL               ; (PACK_ZERO: AL <- 0)
    JMP ADD_F32_RETURN_A     ; (PUSH AL, HALT)
ADD_F32_HALT:
    HALT
