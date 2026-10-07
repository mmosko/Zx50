; =========================
; EXP2_F32

.equ ONE_F32, 32
.equ EXP2_C6, 9
.equ EXP2_C5, 8
.equ EXP2_C4, 7
.equ EXP2_C3, 6
.equ EXP2_C2, 5
.equ EXP2_C1, 4

USER_EXP2_F32:
    POP AL                          ; 0: START
    JNZ UF, EXP2_F32_116            ; 1
    MOV BH, AL                      ; 2
    UNPACK EA, AL                   ; 3
    JZ ZERO, EXP2_F32_101           ; 4
    LDI C, 0                        ; 5
    JNZ SIGN, EXP2_F32_8            ; 6
    JMP EXP2_F32_9                  ; 7
EXP2_F32_8:
    LDI C, 1                        ; 8: SAVE_NEG
EXP2_F32_9:
    MOV BL, EA                      ; 9: CHECK_SPECIAL
    CMP BL, 255                     ; 10
    JZ ZERO, EXP2_F32_114           ; 11
    CMP EA, 127                     ; 12: CHECK_EXP
    JNZ CARRY, EXP2_F32_26          ; 13
    EXP_SUB EA, 127                 ; 14: EXP_GE
    MOV BL, EA                      ; 15
    CMP BL, 7                       ; 16
    JNZ CARRY, EXP2_F32_23          ; 17
    JZ ZERO, EXP2_F32_23            ; 18
    MOV BL, C                       ; 19
    CMP BL, 0                       ; 20
    JZ ZERO, EXP2_F32_107           ; 21
    JMP EXP2_F32_104                ; 22
EXP2_F32_23:
    MOV BL, EA                      ; 23: IN_RANGE_GE
    LSL AL, BL                      ; 24
    JMP EXP2_F32_29                 ; 25
EXP2_F32_26:
    LDI BL, 127                     ; 26: EXP_LESS
    SUB BL, EA                      ; 27
    LSR AL, BL                      ; 28
EXP2_F32_29:
    MOV BL, AL                      ; 29: EXTRACT_K_R
    LDI BH, 1                       ; 30
    LSL BH, 22                      ; 31
    ADD AL, BH                      ; 32
    LSR AL, 23                      ; 33
    MOV EA, AL                      ; 34
    LSL AL, 23                      ; 35
    SUB BL, AL                      ; 36
    LSL BL, 8                       ; 37
    MOV BH, C                       ; 38
    CMP BH, 0                       ; 39
    JZ ZERO, EXP2_F32_43            ; 40
    NOT BL                          ; 41
    ADD BL, 1                       ; 42
EXP2_F32_43:
    MOV DH, BL                      ; 43: EVAL_POLY
    LDC AL, CHEB, EXP2_C6           ; 44
    MUL AL, DH                      ; 45
    LSL AH, 1                       ; 46
    LDC BL, CHEB, EXP2_C5           ; 47
    ADD AH, BL                      ; 48
    MOV AL, AH                      ; 49
    MUL AL, DH                      ; 50
    LSL AH, 1                       ; 51
    LDC BL, CHEB, EXP2_C4           ; 52
    ADD AH, BL                      ; 53
    MOV AL, AH                      ; 54
    MUL AL, DH                      ; 55
    LSL AH, 1                       ; 56
    LDC BL, CHEB, EXP2_C3           ; 57
    ADD AH, BL                      ; 58
    MOV AL, AH                      ; 59
    MUL AL, DH                      ; 60
    LSL AH, 1                       ; 61
    LDC BL, CHEB, EXP2_C2           ; 62
    ADD AH, BL                      ; 63
    MOV AL, AH                      ; 64
    MUL AL, DH                      ; 65
    LSL AH, 1                       ; 66
    LDC BL, CHEB, EXP2_C1           ; 67
    ADD AH, BL                      ; 68
    MOV AL, AH                      ; 69
    MUL AL, DH                      ; 70
    LSL AH, 1                       ; 71
    LDI BL, 1                       ; 72
    LSL BL, 31                      ; 73
    ADD AH, BL                      ; 74
    MOV BL, AH                      ; 75
    LSR BL, 31                      ; 76
    CMP BL, 0                       ; 77
    JZ ZERO, EXP2_F32_82            ; 78
    LDI EB, 127                     ; 79
    LSR AH, 8                       ; 80
    JMP EXP2_F32_85                 ; 81
EXP2_F32_82:
    LDI EB, 126                     ; 82: MANT_LESS_ONE
    LSL AH, 1                       ; 83
    LSR AH, 8                       ; 84
EXP2_F32_85:
    MOV BL, C                       ; 85: CALC_FINAL_EXP
    CMP BL, 0                       ; 86
    JZ ZERO, EXP2_F32_92            ; 87
    MOV BL, EA                      ; 88
    MOV EA, EB                      ; 89
    EXP_SUB EA, BL                  ; 90
    JMP EXP2_F32_95                 ; 91
EXP2_F32_92:
    MOV BL, EA                      ; 92: POS_EXP_SUM
    MOV EA, EB                      ; 93
    EXP_ADD EA, BL                  ; 94
EXP2_F32_95:
    MOV AL, AH                      ; 95: DO_PACK
    LDI BH, 0                       ; 96
    OR BH, BH                       ; 97
    PACK AL, EA                     ; 98
    PUSH AL                         ; 99
    HALT                            ; 100
EXP2_F32_101:
    LDC AL, CONST, ONE_F32          ; 101: RET_ONE
    PUSH AL                         ; 102
    HALT                            ; 103
EXP2_F32_104:
    SUB AL, AL                      ; 104: RET_ZERO
    PUSH AL                         ; 105
    HALT                            ; 106
EXP2_F32_107:
    LDI EA, 255                     ; 107: RET_INF
    LDI AL, 0                       ; 108
    LDI BH, 0                       ; 109
    OR BH, BH                       ; 110
    PACK AL, EA                     ; 111
    PUSH AL                         ; 112
    HALT                            ; 113
EXP2_F32_114:
    PUSH BH                         ; 114: RET_INPUT
    HALT                            ; 115
EXP2_F32_116:
    HALT                            ; 116: TRAP_UNDERFLOW
