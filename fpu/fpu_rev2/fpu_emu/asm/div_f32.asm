; =========================
; DIV_F32
; =========================

USER_DIV_F32:
    CALL POP_TWO_32
    MOV BH, AL
    XOR BH, BL                      ; BH[31] = s_A ^ s_B
    UNPACK BL, EB                   ; unpack divisor B: EB <- exp_B, BL <- mant_B
    JZ ZERO, DIV_F32_DIV_ZERO       ; DIV_BY_ZERO
    UNPACK AL, EA                   ; unpack dividend A: EA <- exp_A, AL <- mant_A
    JZ ZERO, DIV_F32_ZERO           ; RETURN_ZERO
    EXP_SUB EA, EB                  ; EA <- EA - EB
    EXP_ADD EA, 126                 ; EA <- EA + 126 (NORMALIZE_F32 adds 1 if bit 24 is set)
    LSL AL, 8                       ; AL <- AL << 8
    DIVU AL, BL                     ; AL <- q0, DL <- r0
    MOV AH, AL                      ; AH <- q0
    LDI C, 2
DIV_LOOP:
    MOV AL, DL                      ; AL <- r
    LSL AL, 8                       ; AL <- r << 8
    DIVU AL, BL                     ; AL <- q_i, DL <- r_i
    LSL AH, 8                       ; AH <- q << 8
    OR AH, AL                       ; AH <- (q << 8) | q_i
    DJNZ DIV_LOOP

    MOV AL, AH                      ; AL <- Q_24
    MOV AH, BH                      ; AH[31] = sign
DIV_F32_NORM:
    CALL NORMALIZE_F32
    PUSH AL
    HALT

DIV_F32_ZERO:
    XOR AL, AL                      ; RETURN_ZERO: AL <- 0
    MOV AH, BH
    JMP DIV_F32_NORM

DIV_F32_DIV_ZERO:
    XOR BL, BL                      ; DIV_BY_ZERO: BL <- 0
    DIVU AL, BL                     ; trigger divide-by-zero error
    HALT
