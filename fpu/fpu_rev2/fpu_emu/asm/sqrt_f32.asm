; =========================
; SQRT_F32
; =========================

USER_SQRT_F32:
    CALL POP_ONE_32
    MOV BH, AL                      ; Save raw input in BH (for zero/NaN preservation)
    UNPACK EA, AL                   ; AL <- mantissa (bit 23 set), EA <- biased exponent
    JZ ZERO, SQRT_F32_RET_BH        ; If X == 0: push original input (BH) and return
    JNZ SIGN, SQRT_F32_DOMAIN_ERR   ; If X < 0: domain error (assert ERR and abort)
    MOV BL, EA                      ; BL <- biased exponent
    CMP BL, 255                     ; Check for Inf / NaN
    JZ ZERO, SQRT_F32_RET_BH        ; If Inf or NaN: push original input (BH) and return

    MOV DL, AL                      ; DL <- mantissa
    MOV BL, AL                      ; BL <- mantissa
    LSR BL, 16                      ; Shift out low bits
    AND BL, 0x7F                    ; fraction index bits [22:16]

    LSL DL, 7                       ; DL <- S in Q2.30 (range [1.0, 2.0))
    EXP_ADD EA, 127                 ; EA <- (E + 127)
    MOV EB, EA
    AND EB, 1                       ; Check parity: (E + 127) & 1 == 0 if E was odd
    JZ ZERO, SQRT_REJOIN
    LSL DL, 1                       ; Even E: S in range [2.0, 4.0)
    OR BL, 0x80                     ; Select table range [2.0, 4.0)
    EXP_SUB EA, 1                   ; EA <- (E + 126)

SQRT_REJOIN:
    LSR EA, 1                       ; EA <- (E + bias) >> 1
    LDC AH, SQRT, BL                ; AH <- 16-bit seed y0 from EBR 4 (SQRT table)
    LSL AH, 16                      ; AH <- y0 in Q0.32
    MOV BL, AH                      ; BL <- y0 (initial reciprocal square root seed)
    LDI DH, 3                       ; Constant 3 in DH
    LSL DH, 30                      ; DH <- 3.0 in Q2.30 (0xC0000000)
    LDI C, 2                        ; Counter C <- 2 iterations of Newton-Raphson

SQRT_LOOP_NR:
    MOV AL, BL                      ; AL <- y
    MULU AL, BL                     ; {AH, AL} <- y^2 (high 32 bits in AH is Q2.30)
    MOV AL, AH                      ; AL <- y^2
    MULU AL, DL                     ; {AH, AL} <- S * y^2 (high 32 bits in AH is Q2.30)
    MOV BH, DH                      ; BH <- 3.0 (from DH)
    SUB BH, AH                      ; BH <- 3.0 - S * y^2 (valid on ha_mux!)
    MOV AL, BL                      ; AL <- y
    MULU AL, BH                     ; {AH, AL} <- y * (3.0 - S * y^2) (Q2.62)
    LSL AH, 1                       ; High word shift: AH << 1 (divide by 2 in Q0.32)
    LSR AL, 31                      ; Carry bit from AL: AL >> 31
    OR AH, AL                       ; AH <- (AH << 1) | (AL >> 31)
    MOV BL, AH                      ; BL <- updated y
    DJNZ SQRT_LOOP_NR               ; Loop 2 iterations

    MOV AL, BL                      ; AL <- final reciprocal square root y
    MULU AL, DL                     ; {AH, AL} <- S * y = sqrt(S) in Q2.30
    ADD AH, 0x40                    ; Half-ULP rounding bias
    LSR AH, 7                       ; Align mantissa: bit 23 implicit 1 is at bit 23
    PACK AH, EA                     ; Pack float32: mantissa AH, exponent EA, sign=0
    MOV BH, AH                      ; BH <- packed result
SQRT_F32_RET_BH:
    PUSH BH
    HALT

SQRT_F32_DOMAIN_ERR:
    LDI ERR, 1
    HALT
