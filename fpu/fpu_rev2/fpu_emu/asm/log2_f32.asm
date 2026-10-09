; ==============================================================================
; LOG2_F32: IEEE-754 Single-Precision Base-2 Logarithm: log2(X)
;
; Operation:
;   Computes log2(X) = (E - 127) + log2(m)
;   Range reduction on mantissa m in [1.0, 2.0):
;     If m > sqrt(2): m = m / 2, E = E + 1, so m in [1/sqrt(2), sqrt(2)]
;     Transform variable: z = (m - 1) / (m + 1) via iterative division
;   Polynomial evaluation:
;     log2(m) = z * P(z^2), where P(z^2) = c0 + c1*z^2 + c2*z^4 + c3*z^6
;     Evaluated using Horner's method from Chebyshev ROM (EBR 5)
;   Recombination:
;     Combines integer exponent offset (E - 127) with log2(m) in Q9.23
;     Calls NORMALIZE_F32 to convert Q9.23 into IEEE-754 float32.
;
; Inputs:
;   Stack: TOS = float32 X
;
; Outputs:
;   Stack: TOS = float32 log2(X)
;   Status flags:
;     ZERO set if X == 1.0 (log2(1.0) == 0.0)
;     ERR set if X <= 0.0 (domain error, aborts without pushing)
;     UNDERFLOW set if stack underflow
;
; Register Allocation:
;   AL : Mantissa / division numerator / polynomial accumulator / result
;   AH : Quotient accumulator z / fixed-point Q9.23 result / sign in AH[31]
;   BL : Denominator (m + 1) / Chebyshev coefficients c_i / temporary terms
;   BH : Raw input preserved / sign tracker (BH[31])
;   EA : Exponent (unbiased E - 127) / normalization exponent
;   EB : Flag (1 if m was inverted / negated)
;   C  : Iterative division counter / Horner polynomial counter
;   DL : Hardware divider remainder register (written by DIVU)
;   FL : Scratch: z^2 in Q1.31
;   FH : Scratch: z in Q0.31
;
; ROM References:
;   CONST 32: 1.0f (ONE_F32)
;   CHEB 11: sqrt(2) mantissa threshold (SQRT2_MANT)
;   CHEB 10..7: Chebyshev polynomial coefficients c3..c0 (LOG2_C3..LOG2_C0)
;
; Subroutines Called:
;   POP_ONE_32, NORMALIZE_F32
; ==============================================================================

.equ ONE_F32, 32
.equ SQRT2_MANT, 11
.equ LOG2_C3, 10
.equ LOG2_C2, 9
.equ LOG2_C1, 8
.equ LOG2_C0, 7

USER_LOG2_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    CALL LOG2_CORE                  ; AL <- log2(AL)
    JNZ ERR, LOG2_HALT              ; If domain error (ERR set), abort without pushing
    PUSH AL
LOG2_HALT:
    HALT

LOG2_CORE:
    MOV BH, AL                      ; BH <- input (preserves sign and value)
    UNPACK EA, AL                   ; EA <- exponent, AL <- mantissa, status.SIGN <- sign
    JZ ZERO, LOG2_DOMAIN_ERR        ; log2(0) or log2(-0) -> domain error
    JNZ SIGN, LOG2_DOMAIN_ERR       ; log2(negative) -> domain error
    MOV BL, EA                      ; BL <- biased exponent
    CMP BL, 255                     ; Check for NaN / +Inf
    JZ ZERO, LOG2_RET_INPUT         ; If NaN or +Inf: return input
    LDC BL, CONST, ONE_F32          ; BL <- 1.0f
    CMP BL, BH                      ; Check if input is exactly 1.0f
    JZ ZERO, LOG2_RET_ZERO          ; log2(1.0) == 0.0

    LDC BL, CHEB, SQRT2_MANT        ; BL <- sqrt(2) mantissa threshold
    CMP BL, AL                      ; Compare mantissa with sqrt(2)
    JNZ CARRY, LOG2_REDUCE_M        ; If m > sqrt(2): reduce range
    JMP LOG2_PREPARE_DIV

LOG2_REDUCE_M:
    LSR AL, 1                       ; m <- m / 2
    EXP_ADD EA, 1                   ; E <- E + 1

LOG2_PREPARE_DIV:
    LDI BH, 1
    LSL BH, 23                      ; BH <- 1.0 in bit 23
    MOV BL, AL
    ADD BL, BH                      ; BL <- denominator = m + 1.0
    SUB AL, BH                      ; AL <- numerator = m - 1.0
    LDI EB, 0                       ; EB <- 0 (default: m >= 1.0)
    JZ SIGN, LOG2_DIV_START         ; If numerator >= 0: proceed to divide
    LDI EB, 1                       ; EB <- 1 (flag: m was < 1.0, negate result later)
    NOT AL
    ADD AL, 1                       ; AL <- |m - 1.0|

LOG2_DIV_START:
    LSL AL, 7                       ; First divide step: AL << 7
    DIVU AL, BL                     ; AL <- q0, DL <- r0
    MOV AH, AL                      ; AH <- q0
    LDI C, 3                        ; 3 iterations of 7-bit division
LOG2_DIV_LOOP:
    MOV AL, DL                      ; AL <- remainder from DIVU
    LSL AL, 7
    DIVU AL, BL
    LSL AH, 7
    OR AH, AL
    DJNZ LOG2_DIV_LOOP

    MOV AL, DL                      ; Final 3 bits of quotient
    LSL AL, 3
    DIVU AL, BL
    LSL AH, 3
    OR AH, AL                       ; AH <- z = (m - 1) / (m + 1) in Q0.31

    MOV FH, AH                      ; Scratch FH <- z
    MOV AL, AH
    MULU AL, AH                     ; {AH, AL} <- z^2
    LSL AH, 1
    MOV FL, AH                      ; Scratch FL <- z^2 in Q1.31

    LDI C, 9                        ; Horner loop counter (starts with c2 at slot 9)
    LDC AL, CHEB, LOG2_C3           ; AL <- c3
LOG2_POLY_LOOP:
    MULU AL, FL                     ; {AH, AL} <- term * z^2
    LSL AH, 1
    LDC BL, CHEB, C                 ; BL <- c_i
    ADD AH, BL                      ; AH <- AH + c_i
    MOV AL, AH
    SUB C, 1
    CMP C, 6
    JNZ LOG2_POLY_LOOP              ; Loops for c2, c1, c0

    MULU AL, FH                     ; Final multiply: P(z^2) * z
    LSL AH, 1
    LSR AH, 6                       ; AH <- log2(m) in Q9.23

    MOV BL, EB
    CMP BL, 0
    JZ ZERO, LOG2_CHECK_EXP
    NOT AH
    ADD AH, 1                       ; Negate log2(m) if m was < 1.0

LOG2_CHECK_EXP:
    CMP EA, 127
    JZ ZERO, LOG2_EXP_ZERO
    JNZ CARRY, LOG2_EXP_NEG

    ; Exp > 127 (E > 0): result is positive
    LDI BH, 0                       ; Sign = 0 (positive)
    EXP_SUB EA, 127                 ; EA <- E - 127
    MOV BL, EA
    LSL BL, 23                      ; BL <- (E - 127) in Q9.23
    ADD AH, BL                      ; AH <- (E - 127) + log2(m)
    JMP LOG2_NORMALIZE

LOG2_EXP_NEG:
    ; Exp < 127 (E < 0): result is negative
    LDI BH, 1
    LSL BH, 31                      ; Sign = 1 (negative, BH[31] = 1)
    LDI BL, 127
    SUB BL, EA                      ; BL <- 127 - E
    LSL BL, 23                      ; BL <- (127 - E) in Q9.23
    SUB BL, AH                      ; BL <- (127 - E) - log2(m)
    MOV AH, BL
    JMP LOG2_NORMALIZE

LOG2_EXP_ZERO:
    ; Exp == 127 (E == 0): result sign determined by log2(m)
    LDI BH, 0                       ; Default sign = 0
    MOV BL, AH
    CMP BL, 0
    JZ ZERO, LOG2_RET_ZERO          ; If exactly zero: return 0.0
    LSR BL, 31
    CMP BL, 0
    JZ ZERO, LOG2_NORMALIZE         ; If positive: sign is 0
    LDI BH, 1
    LSL BH, 31                      ; If negative: sign = 1
    NOT AH
    ADD AH, 1                       ; Make magnitude positive

LOG2_NORMALIZE:
    MOV AL, AH                      ; AL <- Q9.23 mantissa magnitude
    LDI EA, 127                     ; EA <- reference exponent
    MOV AH, BH                      ; AH[31] <- result sign
    CALL NORMALIZE_F32              ; Normalize into IEEE-754 float32 in AL
    RET

LOG2_RET_ZERO:
    XOR AL, AL
    RET

LOG2_RET_INPUT:
    MOV AL, BH
    RET

LOG2_DOMAIN_ERR:
    LDI ERR, 1
    RET
