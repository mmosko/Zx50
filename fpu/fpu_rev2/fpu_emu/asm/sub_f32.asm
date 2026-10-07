; =============================
; A - B = A + (-B)

USER_SUB_F32:
    POP BL                         ; (pop operand B)
    JNZ UNDERFLOW, SUB_F32_49
    FCHS BL                        ; (invert sign bit: B <- -B)
    MOV DL, BL                     ; (stash packed -B into DL)
    POP AL                         ; (pop operand A)
    JNZ UNDERFLOW, SUB_F32_49
    MOV AH, AL                     ; (stash packed A into AH for sign preservation)
    UNPACK BL, EB                  ; (unpack -B)
    JZ ZERO, SUB_F32_43            ; (RETURN_A: jump to PUSH AL, HALT)
    UNPACK AL, EA                  ; (unpack A)
    JZ ZERO, SUB_F32_45           ;  (RETURN_B: jump to PUSH DL, HALT)
    CMP EA, EB
    JNZ CARRY, SUB_F32_17         ; (SWAP_OPS: EA < EB)
    JNZ ZERO, SUB_F32_20          ; (ALIGN_EXP: EA > EB)
    CMP AL, BL
    JNZ CARRY, SUB_F32_17         ;  (SWAP_OPS: AL < BL)
    JMP SUB_F32_20                ; (ALIGN_EXP: AL >= BL)
SUB_F32_17:
    SWAP AL, BL                   ; (larger mantissa in AL)
    SWAP EA, EB                   ; (larger exponent in EA)
    MOV AH, DL                    ; (AH now holds packed larger operand sign)
SUB_F32_20:
    EXP_SUB C, EA, EB             ; (C <- EA - EB; EA preserved!)
    CMP C, 32
    JNZ CARRY, SUB_F32_25         ; (DO_SHIFT: diff < 32)
    MOV BL, 0                     ; (diff >= 32: smaller mantissa shifts to 0)
    JMP SUB_F32_26                ; (DO_ARITH)
SUB_F32_25:
    LSR BL, C                     ; (shift BL right by C)
SUB_F32_26:
    JNZ DIFF_SIGN, SUB_F32_29     ; (DO_SUB)
    ADD AL, BL
    JMP SUB_F32_30               ; (NORMALIZE)
SUB_F32_29:
    SUB AL, BL
SUB_F32_30:
    LZC AL                        ; (leading zero count into C)
    JZ ZERO, SUB_F32_47           ;  (PACK_ZERO: exact cancellation)
    CMP C, 8
    JNZ CARRY, SUB_F32_39               ; (OVERFLOW_RIGHT: C < 8)
    JZ ZERO, SUB_F32_41           ;  (DONE_NORM: C == 8)
    SUB C, 8                  ; (C <- C - 8)
    LSL AL, C                 ;  (AL <- AL << C)
    EXP_SUB EA, C             ; (EA <- EA - C)
    JMP SUB_F32_41            ; (DONE_NORM)
SUB_F32_39:
    LSR AL, 1
    EXP_ADD EA, 1
SUB_F32_41:
    OR AH, AH               ; (restores status.sign from bit 31 of AH)
    PACK AL, EA
SUB_F32_43:
    PUSH AL
    HALT
SUB_F32_45:
    PUSH DL                     ; (RETURN_B: -B)
    HALT
SUB_F32_47:
    SUB AL, AL              ; (PACK_ZERO: AL <- 0)
    JMP SUB_F32_43
SUB_F32_49:
    HALT