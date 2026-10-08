; =========================
; EXP2_F32
; =========================

.equ ONE_F32, 32
.equ POS_INF_F32, 38
.equ EXP2_C6, 6

USER_EXP2_F32:
    CALL POP_ONE_32                 ; pop operand into AL, check underflow
    MOV BH, AL                      ; BH <- original input (preserves sign and value)
    UNPACK EA, AL                   ; EA <- exponent, AL <- mantissa, status.SIGN <- sign
    JZ ZERO, EXP2_RET_ONE           ; 2^0 == 1.0

    MOV BL, EA                      ; check for NaN / Inf
    CMP BL, 255
    JZ ZERO, EXP2_RET_INPUT         ; return NaN or Inf directly

    CMP EA, 127
    JNZ CARRY, EXP2_EXP_LESS        ; if EA < 127 (|x| < 1.0), shift right

    ; Here EA >= 127 (|x| >= 1.0)
    EXP_SUB EA, 127                 ; EA <- exp - 127 (exponent offset >= 0)
    MOV BL, EA
    CMP BL, 8
    JNZ CARRY, EXP2_IN_RANGE        ; if EA < 8 (|x| < 256.0), in range

    ; Out of range (|x| >= 256.0)
    OR BH, BH                       ; restore sign flag from BH[31]
    JNZ SIGN, EXP2_RET_ZERO         ; negative and large -> 0.0
    JMP EXP2_RET_INF                ; positive and large -> +Inf

EXP2_IN_RANGE:
    LSL AL, BL                      ; AL <- fixed-point magnitude (Q8.23)
    JMP EXP2_EXTRACT_K_R

EXP2_EXP_LESS:
    LDI BL, 127
    SUB BL, EA                      ; BL <- 127 - exp
    LSR AL, BL                      ; AL <- fixed-point magnitude (Q8.23)

EXP2_EXTRACT_K_R:
    MOV BL, AL                      ; BL <- unrounded fixed-point magnitude
    LDI DL, 1
    LSL DL, 22                      ; DL <- 0.5 in Q8.23 (0x00400000)
    ADD AL, DL                      ; AL <- round(x)
    LSR AL, 23                      ; AL <- integer k
    MOV EA, AL                      ; EA <- k
    LSL AL, 23                      ; AL <- k << 23
    SUB BL, AL                      ; BL <- fraction r = magnitude - k (in [-0.5, 0.5])
    LSL BL, 8                       ; BL <- r in Q1.31

    LDI EB, 127
    OR BH, BH                       ; test original sign from BH[31]
    JNZ SIGN, EXP2_NEG_X

    ; Positive x: exponent = 127 + k
    EXP_ADD EA, EB                  ; EA <- 127 + k
    JMP EXP2_EVAL_POLY

EXP2_NEG_X:
    ; Negative x: remainder r is negated, exponent = 127 - k
    NOT BL
    ADD BL, 1                       ; BL <- -r
    EXP_SUB EA, EB, EA              ; EA <- 127 - k

EXP2_EVAL_POLY:
    MOV DH, BL                      ; DH <- r in Q1.31 (DH preserved across loop!)
    LDI C, 5
    LDC AL, CHEB, EXP2_C6           ; AL <- c6
EXP2_POLY_LOOP:
    MUL AL, DH                      ; AH:AL <- AL * r
    LSL AH, 1                       ; AH <- (AL * r) in Q1.31
    LDC BL, CHEB, C                 ; BL <- c_i (slots 5, 4, 3, 2, 1)
    ADD AH, BL                      ; AH <- AH + c_i
    MOV AL, AH                      ; AL <- accumulated term
    DJNZ EXP2_POLY_LOOP             ; C--, loop if C != 0

    MUL AL, DH                      ; final multiply: AL * r
    LSL AH, 1                       ; AH <- P(r) in Q1.31

    LDI BL, 1
    LSL BL, 31                      ; BL <- 1.0 in Q1.31 (0x80000000)
    ADD AH, BL                      ; AH <- 1.0 + P(r)
    LSR AH, 8                       ; align Q1.31 to bit 23
    MOV AL, AH                      ; AL <- mantissa for NORMALIZE_F32
    XOR AH, AH                      ; AH[31] = 0 (result sign is always positive)
    CALL NORMALIZE_F32              ; normalize mantissa, adjust EA, pack into AL
EXP2_RET_AL:
    PUSH AL
    HALT

EXP2_RET_ONE:
    LDC AL, CONST, ONE_F32
    JMP EXP2_RET_AL

EXP2_RET_ZERO:
    XOR AL, AL
    JMP EXP2_RET_AL

EXP2_RET_INF:
    LDC AL, CONST, POS_INF_F32
    JMP EXP2_RET_AL

EXP2_RET_INPUT:
    PUSH BH
    HALT
