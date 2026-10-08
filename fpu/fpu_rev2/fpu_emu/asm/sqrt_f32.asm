; =========================
; SQRT_F32

USER_SQRT_F32:
    CALL POP_ONE_32
    MOV BH, AL                      ; Save raw input in BH (for zero/NaN preservation)
    UNPACK EA, AL                   ; AL <- mantissa (bit 23 set), EA <- biased exponent
    JZ ZERO, SQRT_F32_55            ; If X == 0: push original input (BH) and return
    JNZ SIGN, SQRT_F32_57           ; If X < 0: domain error (assert ERR and abort)
    MOV BL, EA                      ; BL <- biased exponent
    CMP BL, 255                     ; Check for Inf / NaN
    JZ ZERO, SQRT_F32_55            ; If Inf or NaN: push original input (BH) and return
    AND BL, 1                       ; Check exponent parity (BL & 1)
    JZ ZERO, SQRT_F32_18            ; If even exponent: jump to EVEN_EXP (line 18)
    ; --- ODD_EXP (E unbiased is even: e = 2k => E is odd) ---
    MOV DL, AL                      ; DL <- mantissa (Q0.24)
    LSL DL, 7                       ; DL <- S in Q2.30 (range [1.0, 2.0))
    MOV BL, AL                      ; BL <- mantissa
    LSR BL, 16                      ; Shift out low bits
    AND BL, 0x7F                    ; BL <- fraction index bits [22:16], bit 7 = 0
    EXP_ADD EA, 127                 ; EA <- (E + 127)
    JMP SQRT_F32_25                 ; Jump to REJOIN
    ; --- EVEN_EXP (E unbiased is odd: e = 2k+1 => E is even) ---
SQRT_F32_18:
    MOV DL, AL                      ; DL <- mantissa (Q0.24)
    LSL DL, 8                       ; DL <- 2*M = S in Q2.30 (range [2.0, 4.0))
    MOV BL, AL                      ; BL <- mantissa
    LSR BL, 16                      ; Shift out low bits
    AND BL, 0x7F                    ; Fraction index bits [22:16]
    OR BL, 0x80                     ; Set bit 7 = 1 (selects table range [2.0, 4.0))
    EXP_ADD EA, 126                 ; EA <- (E + 126)
    ; --- REJOIN (line 25) ---
SQRT_F32_25:
    MOV FL, EA                      ; FL <- EA
    LSR FL, 1                       ; FL <- EA >> 1 (unbiased exponent divided by 2 + 127)
    MOV EA, FL                      ; EA <- final biased exponent
    LDC AH, SQRT, BL                ; AH <- 16-bit seed y0 from EBR 4 (SQRT table)
    LSL AH, 16                      ; AH <- y0 in Q0.32
    MOV BL, AH                      ; BL <- y0 (initial reciprocal square root seed)
    LDI DH, 3                       ; Constant 3 in DH
    LSL DH, 30                      ; DH <- 3.0 in Q2.30 (0xC0000000)
    LDI C, 2                        ; Counter C <- 2 iterations of Newton-Raphson
    ; --- LOOP_NR (line 34..46) ---
SQRT_F32_34:
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
    DJNZ SQRT_F32_34                ; Loop 2 iterations
    ; --- RESULT FORMATION (line 47..53) ---
    MOV AL, BL                      ; AL <- final reciprocal square root y
    MULU AL, DL                     ; {AH, AL} <- S * y = sqrt(S) in Q2.30
    ADD AH, 0x40                    ; Half-ULP rounding bias
    LSR AH, 7                       ; Align mantissa: bit 23 implicit 1 is at bit 23
    PACK AH, EA                     ; Pack float32: mantissa AH, exponent EA, sign=0
    PUSH AH                         ; Push result to stack
    HALT                            ; Done
    ; --- SPECIAL & ERROR HANDLERS (line 54..58) ---
SQRT_F32_55:
    PUSH BH                         ; RET_INPUT: push original input (for 0.0, -0.0, +Inf, NaN)
    HALT
SQRT_F32_57:
    LDI ERR, 1                      ; DOMAIN_ERR: assert ERR flag (X < 0)
    HALT
