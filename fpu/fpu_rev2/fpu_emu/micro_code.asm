
; =========================
; ADD_I32

USER_ADD_I32:
    POP BL
    JNZ UF, ADD_I32_HALT
    POP AL
    JNZ UF, ADD_I32_HALT
    ADD AL, BL
    PUSH AL
ADD_I32_HALT:
    HALT

; =========================
; ADD_I64

USER_ADD_I64:
    POP BX
    JNZ UF, ADD_I64_HALT
    POP AX
    JNZ UF, ADD_I64_HALT
    ADD AX, BX
    PUSH AX
ADD_I64_HALT:
    HALT

; =========================
; SUB_I32

USER_SUB_I32:
    POP BL
    JNZ UF, SUB_I32_HALT
    POP AL
    JNZ UF, SUB_I32_HALT
    SUB AL, BL
    PUSH AL
SUB_I32_HALT:
    HALT

; =========================
; SUB_I64

USER_SUB_I64:
    POP BX
    JNZ UF, SUB_I64_HALT
    POP AX
    JNZ UF, SUB_I64_HALT
    SUB AX, BX
    PUSH AX
SUB_I64_HALT:
    HALT
; =========================
; ADD_F32

USER_ADD_F32:
    POP BL                      ; (pop operand B)
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
    MOV BL, 0                   ; (diff >= 32: smaller mantissa shifts to 0)
    JMP ADD_F32_25              ; (DO_ARITH)
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
    JZ ZERO, ADD_F32_46                 ; (PACK_ZERO: exact cancellation)
    CMP C, 8
    JNZ CARRY, ADD_F32_OVERFLOW_RIGHT   ; (OVERFLOW_RIGHT: C < 8)
    JZ ZERO, ADD_F32_DONE_NORM          ; (DONE_NORM: C == 8)
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
    PUSH DL                 ; RETURN_B
    HALT
ADD_F32_46:
    SUB AL, AL               ; (PACK_ZERO: AL <- 0)
    JMP ADD_F32_RETURN_A     ; (PUSH AL, HALT)
ADD_F32_HALT:
    HALT

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