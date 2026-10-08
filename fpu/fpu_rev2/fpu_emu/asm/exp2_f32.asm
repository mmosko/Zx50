; ==============================================================================
; EXP2_F32: IEEE-754 Single-Precision Base-2 Exponential: 2^X
;
; Operation:
;   Computes 2^X by range reduction and polynomial evaluation:
;     X = k + r, where k = round(X) is integer, r in [-0.5, 0.5]
;     2^X = 2^k * 2^r
;   2^r is evaluated using degree-6 Horner polynomial from Chebyshev ROM (EBR 5)
;   2^k is applied directly to the exponent EA.
;
; Inputs:
;   Stack: TOS = float32 X
;
; Outputs:
;   Stack: TOS = float32 2^X
;   Status flags:
;     ZERO set if result underflows to 0.0 (or X == -Inf)
;     OVERFLOW set if result overflows to +Inf
;     UNDERFLOW set if stack underflow
;
; Register Allocation:
;   AL : Input mantissa / fixed-point X / polynomial accumulator / final result
;   AH : Product high words / packed result sign tracking (AH[31] = 0)
;   BL : Exponent offset / fraction r / Chebyshev coefficients c_i
;   BH : Preserved raw input (for sign, Inf/NaN return)
;   EA : Exponent / integer k / final biased exponent
;   EB : Biasing constant (127)
;   C  : Horner polynomial loop counter (5 down to 1)
;   FL : Scratch: rounding constant 0.5 in Q8.23 (0x00400000)
;   FH : Scratch: fraction r in Q1.31 (preserved across Horner loop)
;   D  : (DL, DH) Preserved / untouched
;
; ROM References:
;   CONST 32: 1.0f (ONE_F32)
;   CONST 38: +Inf (POS_INF_F32)
;   CHEB 6..1: Chebyshev polynomial coefficients c6..c1
;
; Subroutines Called:
;   POP_ONE_32, NORMALIZE_F32
; ==============================================================================

.equ ONE_F32, 32
.equ POS_INF_F32, 38
.equ EXP2_C6, 6

USER_EXP2_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    MOV BH, AL                      ; BH <- raw input (preserves sign and value)
    UNPACK EA, AL                   ; EA <- exponent, AL <- mantissa, status.SIGN <- sign
    JZ ZERO, EXP2_RET_ONE           ; 2^0 == 1.0

    MOV BL, EA                      ; BL <- biased exponent
    CMP BL, 255                     ; Check for NaN / Inf
    JZ ZERO, EXP2_RET_INPUT         ; If NaN or Inf: return original input

    CMP EA, 127
    JNZ CARRY, EXP2_EXP_LESS        ; If EA < 127 (|x| < 1.0), shift right

    ; Here EA >= 127 (|x| >= 1.0)
    EXP_SUB EA, 127                 ; EA <- exp - 127 (exponent offset >= 0)
    MOV BL, EA
    CMP BL, 8
    JNZ CARRY, EXP2_IN_RANGE        ; If EA < 8 (|x| < 256.0), in range

    ; Out of range (|x| >= 256.0)
    OR BH, BH                       ; Restore sign flag from BH[31]
    JNZ SIGN, EXP2_RET_ZERO         ; Negative large |x| -> underflow to 0.0
    JMP EXP2_RET_INF                ; Positive large |x| -> overflow to +Inf

EXP2_IN_RANGE:
    LSL AL, BL                      ; AL <- fixed-point magnitude (Q8.23)
    JMP EXP2_EXTRACT_K_R

EXP2_EXP_LESS:
    LDI BL, 127
    SUB BL, EA                      ; BL <- 127 - exp
    LSR AL, BL                      ; AL <- fixed-point magnitude (Q8.23)

EXP2_EXTRACT_K_R:
    MOV BL, AL                      ; BL <- unrounded fixed-point magnitude
    LDI FL, 1                       ; Scratch FL <- 1
    LSL FL, 22                      ; FL <- 0.5 in Q8.23 (0x00400000)
    ADD AL, FL                      ; AL <- round(x)
    LSR AL, 23                      ; AL <- integer k
    MOV EA, AL                      ; EA <- k
    LSL AL, 23                      ; AL <- k << 23
    SUB BL, AL                      ; BL <- fraction r = magnitude - k (in [-0.5, 0.5])
    LSL BL, 8                       ; BL <- r in Q1.31

    LDI EB, 127
    OR BH, BH                       ; Test original sign from BH[31]
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
    MOV FH, BL                      ; Scratch FH <- r in Q1.31 (preserved across Horner loop)
    LDI C, 5                        ; Horner loop counter: 5 down to 1
    LDC AL, CHEB, EXP2_C6           ; AL <- c6
EXP2_POLY_LOOP:
    MUL AL, FH                      ; AH:AL <- AL * r
    LSL AH, 1                       ; AH <- (AL * r) in Q1.31
    LDC BL, CHEB, C                 ; BL <- c_i (slots 5, 4, 3, 2, 1)
    ADD AH, BL                      ; AH <- AH + c_i
    MOV AL, AH                      ; AL <- accumulated term
    DJNZ EXP2_POLY_LOOP             ; Repeat for all coefficients

    MUL AL, FH                      ; Final multiply: AL * r
    LSL AH, 1                       ; AH <- P(r) in Q1.31

    LDI BL, 1
    LSL BL, 31                      ; BL <- 1.0 in Q1.31 (0x80000000)
    ADD AH, BL                      ; AH <- 1.0 + P(r)
    LSR AH, 8                       ; Align Q1.31 to bit 23
    MOV AL, AH                      ; AL <- mantissa for NORMALIZE_F32
    XOR AH, AH                      ; AH[31] = 0 (result sign is always positive)
    CALL NORMALIZE_F32              ; Normalize mantissa, adjust EA, pack into AL
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
