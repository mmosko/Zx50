; =========================
; LOG2_F32
; =========================

.equ ONE_F32, 32
.equ SQRT2_MANT, 11
.equ LOG2_C3, 10
.equ LOG2_C2, 9
.equ LOG2_C1, 8
.equ LOG2_C0, 7

USER_LOG2_F32:
    CALL POP_ONE_32                 ; pop operand into AL
    MOV BH, AL                      ; BH <- input (preserves sign and value)
    UNPACK EA, AL                   ; EA <- exponent, AL <- mantissa, status.SIGN <- sign
    JZ ZERO, LOG2_DOMAIN_ERR        ; log2(0) or log2(-0) -> domain error
    JNZ SIGN, LOG2_DOMAIN_ERR       ; log2(negative) -> domain error
    MOV BL, EA
    CMP BL, 255
    JZ ZERO, LOG2_RET_INPUT         ; log2(+inf) or log2(NaN) -> return input
    LDC BL, CONST, ONE_F32
    CMP BL, BH
    JZ ZERO, LOG2_RET_ZERO          ; log2(1.0) == 0.0

    LDC BL, CHEB, SQRT2_MANT
    CMP BL, AL
    JNZ CARRY, LOG2_REDUCE_M
    JMP LOG2_PREPARE_DIV

LOG2_REDUCE_M:
    LSR AL, 1
    EXP_ADD EA, 1

LOG2_PREPARE_DIV:
    LDI BH, 1
    LSL BH, 23
    MOV BL, AL
    ADD BL, BH                      ; BL <- denominator = m + 1.0
    SUB AL, BH                      ; AL <- numerator = m - 1.0
    LDI EB, 0
    JZ SIGN, LOG2_DIV_START
    LDI EB, 1                       ; EB <- 1 if m < 1.0
    NOT AL
    ADD AL, 1

LOG2_DIV_START:
    LSL AL, 7
    DIVU AL, BL
    MOV AH, AL
    LDI C, 3
LOG2_DIV_LOOP:
    MOV AL, DL
    LSL AL, 7
    DIVU AL, BL
    LSL AH, 7
    OR AH, AL
    DJNZ LOG2_DIV_LOOP

    MOV AL, DL
    LSL AL, 3
    DIVU AL, BL
    LSL AH, 3
    OR AH, AL                       ; AH <- z in Q0.31

    MOV DH, AH                      ; DH <- z
    MOV AL, AH
    MULU AL, AH                     ; {AH, AL} <- z^2
    LSL AH, 1
    MOV DL, AH                      ; DL <- z^2 in Q1.31

    LDI C, 9
    LDC AL, CHEB, LOG2_C3
LOG2_POLY_LOOP:
    MULU AL, DL
    LSL AH, 1
    LDC BL, CHEB, C
    ADD AH, BL
    MOV AL, AH
    SUB C, 1
    CMP C, 6
    JNZ LOG2_POLY_LOOP

    MULU AL, DH                     ; P(z) * z
    LSL AH, 1
    LSR AH, 6                       ; AH <- log2(m) in Q9.23

    MOV BL, EB
    CMP BL, 0
    JZ ZERO, LOG2_CHECK_EXP
    NOT AH
    ADD AH, 1                       ; negate if m < 1.0

LOG2_CHECK_EXP:
    CMP EA, 127
    JZ ZERO, LOG2_EXP_ZERO
    JNZ CARRY, LOG2_EXP_NEG

    ; Exp > 127
    LDI BH, 0
    EXP_SUB EA, 127
    MOV BL, EA
    LSL BL, 23
    ADD AH, BL
    JMP LOG2_NORMALIZE

LOG2_EXP_NEG:
    LDI BH, 1
    LSL BH, 31
    LDI BL, 127
    SUB BL, EA
    LSL BL, 23
    SUB BL, AH
    MOV AH, BL
    JMP LOG2_NORMALIZE

LOG2_EXP_ZERO:
    LDI BH, 0
    MOV BL, AH
    CMP BL, 0
    JZ ZERO, LOG2_RET_ZERO
    LSR BL, 31
    CMP BL, 0
    JZ ZERO, LOG2_NORMALIZE
    LDI BH, 1
    LSL BH, 31
    NOT AH
    ADD AH, 1

LOG2_NORMALIZE:
    MOV AL, AH
    LDI EA, 127
    MOV AH, BH
    CALL NORMALIZE_F32
    PUSH AL
    HALT

LOG2_RET_ZERO:
    XOR AL, AL
    PUSH AL
    HALT

LOG2_RET_INPUT:
    PUSH BH
    HALT

LOG2_DOMAIN_ERR:
    LDI ERR, 1
    HALT
