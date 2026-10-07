; =========================
; DIV_F32

USER_DIV_F32:
    POP BL                          ; divisor b
    JNZ UF, DIV_F32_HALT            ; TRAP on underflow
    POP AL                          ; dividend a
    JNZ UF, DIV_F32_HALT            ; TRAP on underflow
    MOV BH, AL
    XOR BH, BL                      ; BH[31] = s_A ^ s_B
    UNPACK BL, EB                   ; unpack divisor B: EB <- exp_B, BL <- mant_B
    JZ ZERO, DIV_F32_33             ; DIV_BY_ZERO
    UNPACK AL, EA                   ; unpack dividend A: EA <- exp_A, AL <- mant_A
    JZ ZERO, DIV_F32_31             ; RETURN_ZERO
    EXP_SUB EA, EB                  ; EA <- EA - EB
    EXP_ADD EA, 127                 ; EA <- EA + 127
    LSL AL, 8                       ; AL <- AL << 8
    DIVU AL, BL                     ; AL <- q0, DL <- r0
    MOV AH, AL                      ; AH <- q0
    MOV AL, DL                      ; AL <- r0
    LSL AL, 8                       ; AL <- r0 << 8
    DIVU AL, BL                     ; AL <- q1, DL <- r1
    LSL AH, 8                       ; AH <- q0 << 8
    OR AH, AL                       ; AH <- (q0 << 8) | q1
    MOV AL, DL                      ; AL <- r1
    LSL AL, 8                       ; AL <- r1 << 8
    DIVU AL, BL                     ; AL <- q2, DL <- r2
    LSL AH, 8                       ; AH <- (q0 << 16) | (q1 << 8)
    OR AH, AL                       ; AH <- (q0 << 16) | (q1 << 8) | q2
    MOV AL, AH                      ; AL <- Q_24
    LZC AL                          ; C <- leading zero count
    CMP C, 8                        ; compare C with 8
    JNZ CARRY, DIV_F32_37           ; SHIFT_RIGHT: C < 8, bit 24 is 1
    EXP_SUB EA, 1                   ; bit 24 is 0, normalize exponent: EA -= 1
    JMP DIV_F32_38                  ; DONE_NORM
DIV_F32_31:
    SUB AL, AL                      ; RETURN_ZERO: AL <- 0
    JMP DIV_F32_38                  ; DONE_NORM
DIV_F32_33:
    SUB BL, BL                      ; DIV_BY_ZERO: BL <- 0
    DIVU AL, BL                     ; trigger divide-by-zero error
    HALT
DIV_F32_HALT:
    HALT                            ; TRAP
DIV_F32_37:
    LSR AL, 1                       ; SHIFT_RIGHT: AL >>= 1, falls through to 38
DIV_F32_38:
    OR BH, BH                       ; DONE_NORM: restore sign bit
    PACK AL, EA                     ; pack float32
    PUSH AL
    HALT
