; =========================
; MUL_F32
; =========================

USER_MUL_F32:
    CALL POP_TWO_32
    MOV BH, AL                      ; stash A into BH
    XOR BH, BL                      ; BH[31] = s_A ^ s_B, preserved across MULU and shifts
    UNPACK BL, EB                   ; unpack B: EB <- exp_B, BL <- mant_B
    JZ ZERO, MUL_F32_ZERO           ; RETURN_ZERO
    UNPACK AL, EA                   ; unpack A: EA <- exp_A, AL <- mant_A
    JZ ZERO, MUL_F32_ZERO           ; RETURN_ZERO
    EXP_ADD EA, EB                  ; EA <- EA + EB
    EXP_SUB EA, 127                 ; EA <- EA - 127
    MULU AL, BL                     ; {AH, AL} <- AL * BL unsigned 48-bit product
    LSR AX, 23                      ; {AH, AL} >>= 23, mantissa in AL[24:0]
    MOV AH, BH                      ; AH[31] = sign
MUL_F32_NORM:
    CALL NORMALIZE_F32
    PUSH AL
    HALT
MUL_F32_ZERO:
    XOR AL, AL                      ; RETURN_ZERO: AL <- 0
    MOV AH, BH
    JMP MUL_F32_NORM
