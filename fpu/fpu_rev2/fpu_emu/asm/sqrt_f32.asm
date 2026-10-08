; ==============================================================================
; SQRT_F32: IEEE-754 Single-Precision Square Root
;
; Operation:
;   Computes sqrt(X) using initial reciprocal square root table lookup (EBR 4)
;   followed by 2 Newton-Raphson iterations and a final multiplication:
;     y_{n+1} = y_n * (3.0 - S * y_n^2) / 2
;     sqrt(S) = S * y_final
;
; Inputs:
;   Stack: TOS = float32 X
;
; Outputs:
;   Stack: TOS = float32 sqrt(X)
;   Status flags:
;     ZERO set if X == 0.0 (+0.0 or -0.0)
;     ERR set if X < 0.0 (domain error, aborts without pushing)
;     UNDERFLOW set if stack underflow
;
; Register Allocation:
;   AL : Input mantissa / intermediate NR products / final mantissa
;   AH : NR product high words / packed result
;   BL : Initial table index / reciprocal square root approximation y
;   BH : Preserved raw input (for zero, NaN, Inf return) / scratch term (3.0 - S*y^2)
;   EA : Input exponent / unbiased exponent / result exponent
;   EB : Exponent parity check
;   C  : Newton-Raphson iteration counter (2 iterations)
;   FL : Scratch: scaled mantissa S in Q2.30 (range [1.0, 4.0))
;   FH : Scratch: constant 3.0 in Q2.30 (0xC0000000)
;   D  : (DL, DH) Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_SQRT_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    MOV BH, AL                      ; BH <- raw input (preserves sign and value)
    UNPACK EA, AL                   ; AL <- mantissa (bit 23 set), EA <- biased exponent
    JZ ZERO, SQRT_F32_RET_BH        ; If X == 0 (+0.0 or -0.0): return original input
    JNZ SIGN, SQRT_F32_DOMAIN_ERR   ; If X < 0: domain error (assert ERR and abort)
    MOV BL, EA                      ; BL <- biased exponent
    CMP BL, 255                     ; Check for NaN / Inf
    JZ ZERO, SQRT_F32_RET_BH        ; If NaN or +Inf: return original input

    MOV FL, AL                      ; FL <- mantissa (scratch copy for S)
    MOV BL, AL                      ; BL <- mantissa
    LSR BL, 16                      ; Shift out low bits
    AND BL, 0x7F                    ; Extract fraction index bits [22:16]

    LSL FL, 7                       ; S in Q2.30 (range [1.0, 2.0))
    EXP_ADD EA, 127                 ; EA <- (E + 127)
    MOV EB, EA
    AND EB, 1                       ; Check parity: (E + 127) & 1 == 0 if E was odd
    JZ ZERO, SQRT_REJOIN            ; If unbiased exp was even: keep [1.0, 2.0) range
    LSL FL, 1                       ; Unbiased exp was odd: scale S to [2.0, 4.0) range
    OR BL, 0x80                     ; Select second half of table [2.0, 4.0)
    EXP_SUB EA, 1                   ; EA <- (E + 126)

SQRT_REJOIN:
    LSR EA, 1                       ; Result exponent: EA <- (E + bias) >> 1
    LDC AH, SQRT, BL                ; AH <- 16-bit seed y0 from EBR 4 (SQRT table)
    LSL AH, 16                      ; AH <- y0 in Q0.32
    MOV BL, AH                      ; BL <- y0 (initial reciprocal square root seed)
    LDI FH, 3                       ; Scratch FH <- constant 3
    LSL FH, 30                      ; FH <- 3.0 in Q2.30 (0xC0000000)
    LDI C, 2                        ; C <- 2 iterations of Newton-Raphson

SQRT_LOOP_NR:
    MOV AL, BL                      ; AL <- y
    MULU AL, BL                     ; {AH, AL} <- y^2 (high word AH is in Q2.30)
    MOV AL, AH                      ; AL <- y^2
    MULU AL, FL                     ; {AH, AL} <- S * y^2 (high word AH is in Q2.30)
    MOV BH, FH                      ; BH <- 3.0 (from scratch FH)
    SUB BH, AH                      ; BH <- 3.0 - S * y^2
    MOV AL, BL                      ; AL <- y
    MULU AL, BH                     ; {AH, AL} <- y * (3.0 - S * y^2) (in Q2.62)
    LSL AH, 1                       ; Divide by 2: AH << 1 (Q0.32)
    LSR AL, 31                      ; Carry bit from AL: AL >> 31
    OR AH, AL                       ; AH <- (AH << 1) | (AL >> 31)
    MOV BL, AH                      ; BL <- updated y
    DJNZ SQRT_LOOP_NR               ; Repeat for 2 iterations

    MOV AL, BL                      ; AL <- final reciprocal square root y
    MULU AL, FL                     ; {AH, AL} <- S * y = sqrt(S) in Q2.30
    ADD AH, 0x40                    ; Half-ULP rounding bias
    LSR AH, 7                       ; Align mantissa: bit 23 implicit 1 is at bit 23
    PACK AH, EA                     ; Pack float32: mantissa AH, exponent EA, sign=0
    MOV BH, AH                      ; BH <- packed result
SQRT_F32_RET_BH:
    PUSH BH                         ; Push result
    HALT

SQRT_F32_DOMAIN_ERR:
    LDI ERR, 1
    HALT
