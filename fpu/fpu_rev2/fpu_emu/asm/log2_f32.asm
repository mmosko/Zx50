; =========================
; LOG2_F32

.equ ONE_F32, 32
.equ SQRT2_MANT, 10
.equ LOG2_C3, 3
.equ LOG2_C2, 2
.equ LOG2_C1, 1
.equ LOG2_C0, 0

USER_LOG2_F32:
    CALL POP_ONE_32                 ; 0: START
    MOV BH, AL                      ; 2
    UNPACK EA, AL                   ; 3
    JZ ZERO, LOG2_F32_114           ; 4
    JNZ SIGN, LOG2_F32_114          ; 5
    MOV BL, EA                      ; 6
    CMP BL, 255                     ; 7
    JZ ZERO, LOG2_F32_112           ; 8
    LDC BL, CONST, ONE_F32          ; 9
    CMP BL, BH                      ; 10
    JZ ZERO, LOG2_F32_109           ; 11
    LDC BL, CHEB, SQRT2_MANT        ; 12
    CMP BL, AL                      ; 13
    JNZ CARRY, LOG2_F32_16          ; 14
    JMP LOG2_F32_18                 ; 15
LOG2_F32_16:
    LSR AL, 1                       ; 16: REDUCE_M
    EXP_ADD EA, 1                   ; 17
LOG2_F32_18:
    LDI BH, 1                       ; 18: PREPARE_DIV
    LSL BH, 23                      ; 19
    MOV BL, AL                      ; 20
    ADD BL, BH                      ; 21
    SUB AL, BH                      ; 22
    LDI C, 0                        ; 23
    JNZ SIGN, LOG2_F32_26           ; 24
    JMP LOG2_F32_29                 ; 25
LOG2_F32_26:
    LDI C, 1                        ; 26: NEG_NUM
    NOT AL                          ; 27
    ADD AL, 1                       ; 28
LOG2_F32_29:
    LSL AL, 7                       ; 29: DIV_START
    DIVU AL, BL                     ; 30
    MOV AH, AL                      ; 31
    MOV AL, DL                      ; 32
    LSL AL, 7                       ; 33
    DIVU AL, BL                     ; 34
    LSL AH, 7                       ; 35
    OR AH, AL                       ; 36
    MOV AL, DL                      ; 37
    LSL AL, 7                       ; 38
    DIVU AL, BL                     ; 39
    LSL AH, 7                       ; 40
    OR AH, AL                       ; 41
    MOV AL, DL                      ; 42
    LSL AL, 7                       ; 43
    DIVU AL, BL                     ; 44
    LSL AH, 7                       ; 45
    OR AH, AL                       ; 46
    MOV AL, DL                      ; 47
    LSL AL, 3                       ; 48
    DIVU AL, BL                     ; 49
    LSL AH, 3                       ; 50
    OR AH, AL                       ; 51
    MOV DH, AH                      ; 52
    MOV AL, AH                      ; 53
    MULU AL, AH                     ; 54
    LSL AH, 1                       ; 55
    MOV DL, AH                      ; 56
    LDC AL, CHEB, LOG2_C3           ; 57
    MULU AL, DL                     ; 58
    LSL AH, 1                       ; 59
    LDC BL, CHEB, LOG2_C2           ; 60
    ADD AH, BL                      ; 61
    MOV AL, AH                      ; 62
    MULU AL, DL                     ; 63
    LSL AH, 1                       ; 64
    LDC BL, CHEB, LOG2_C1           ; 65
    ADD AH, BL                      ; 66
    MOV AL, AH                      ; 67
    MULU AL, DL                     ; 68
    LSL AH, 1                       ; 69
    LDC BL, CHEB, LOG2_C0           ; 70
    ADD AH, BL                      ; 71
    MOV AL, AH                      ; 72
    MULU AL, DH                     ; 73
    LSL AH, 1                       ; 74
    LSR AH, 6                       ; 75
    MOV BL, C                       ; 76
    CMP BL, 0                       ; 77
    JZ ZERO, LOG2_F32_81            ; 78
    NOT AH                          ; 79
    ADD AH, 1                       ; 80
LOG2_F32_81:
    CMP EA, 127                     ; 81: CHECK_EXP
    JZ ZERO, LOG2_F32_98            ; 82
    JNZ CARRY, LOG2_F32_90          ; 83
    LDI BH, 0                       ; 84: EXP_POS
    EXP_SUB EA, 127                 ; 85
    MOV BL, EA                      ; 86
    LSL BL, 23                      ; 87
    ADD AH, BL                      ; 88
    JMP LOG2_F32_117                ; 89
LOG2_F32_90:
    LDI BH, 1                       ; 90: EXP_NEG
    LSL BH, 31                      ; 91
    LDI BL, 127                     ; 92
    SUB BL, EA                      ; 93
    LSL BL, 23                      ; 94
    SUB BL, AH                      ; 95
    MOV AH, BL                      ; 96
    JMP LOG2_F32_117                ; 97
LOG2_F32_98:
    LDI BH, 0                       ; 98: EXP_ZERO
    MOV BL, AH                      ; 99
    CMP BL, 0                       ; 100
    JZ ZERO, LOG2_F32_109           ; 101
    LSR BL, 31                      ; 102
    CMP BL, 0                       ; 103
    JZ ZERO, LOG2_F32_117           ; 104
    LDI BH, 1                       ; 105
    LSL BH, 31                      ; 106
    NOT AH                          ; 107
    ADD AH, 1                       ; 108
LOG2_F32_109:
    XOR AL, AL                      ; 109: RET_ZERO
    PUSH AL                         ; 110
    HALT                            ; 111
LOG2_F32_112:
    PUSH BH                         ; 112: RET_INPUT
    HALT                            ; 113
LOG2_F32_114:
    LDI ERR, 1                      ; 114: DOMAIN_ERR
    HALT                            ; 115
LOG2_F32_117:
    LZC BL, AH                      ; 117: NORMALIZE
    LDI EA, 135                     ; 118
    EXP_SUB EA, BL                  ; 119
    LDI C, 8                        ; 120
    SUB C, BL                       ; 121
    JNZ SIGN, LOG2_F32_125          ; 122
    LSR AH, C                       ; 123
    JMP LOG2_F32_128                ; 124
LOG2_F32_125:
    NOT C                           ; 125: SHIFT_LEFT
    ADD C, 1                        ; 126
    LSL AH, C                       ; 127
LOG2_F32_128:
    MOV AL, AH                      ; 128: DO_PACK
    OR BH, BH                       ; 129
    PACK AL, EA                     ; 130
    PUSH AL                         ; 131
    HALT                            ; 132
