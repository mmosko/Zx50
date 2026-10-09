; ==============================================================================
; POW_F32: IEEE-754 Single-Precision Power: Y^X = EXP2_F32(X * LOG2_F32(Y))
;
; Inputs:
;   Stack: TOS = float32 X (exp), NOS = float32 Y (base)
;
; Outputs:
;   Stack: TOS = float32 Y^X
;   Status flags:
;     ZERO set if result underflows to 0.0
;     OVERFLOW set if result overflows to +Inf
;     ERR set if Y < 0.0 or on invalid domain (e.g. 0^neg)
;     UNDERFLOW set if stack underflow
;
; Register Allocation:
;   AL : Base (Y) / log2(Y) / product / result
;   BL : Exponent (X)
;   BH : Temporary for zero / one tests
;   Scratchpad:
;     SCR[0] : Exponent (X) preserved during LOG2_CORE evaluation
;
; Subroutines Called:
;   POP_TWO_32, LOG2_CORE, MUL_F32_CORE, EXP2_CORE
; ==============================================================================

.equ ONE_F32, 32
.equ POS_INF_F32, 38

USER_POW_F32:
    CALL POP_TWO_32             ; AL <- base (Y, NOS), BL <- exp (X, TOS)

    ; Test if exp == 0.0 or -0.0 -> Y^0 == 1.0
    MOV BH, BL
    LSL BH, 1                   ; Shift out sign bit
    JZ ZERO, POW_RET_ONE

    ; Test if base == 1.0f -> 1^X == 1.0
    LDC BH, CONST, ONE_F32
    CMP BH, AL
    JZ ZERO, POW_RET_ONE

    ; Test if base == 0.0 or -0.0
    MOV BH, AL
    LSL BH, 1                   ; Shift out sign bit
    JZ ZERO, POW_BASE_ZERO

    ; Test if base < 0.0 -> domain error
    OR AL, AL
    JNZ SIGN, POW_DOMAIN_ERR

    ; Save exp (BL) to scratchpad slot 0
    STO 0, BL

    ; AL holds base (Y > 0)
    CALL LOG2_CORE              ; AL <- log2(Y)

    ; Load exp (X) from scratchpad slot 0 into BL
    LD BL, 0

    ; Multiply: AL (log2(Y)) * BL (X)
    CALL MUL_F32_CORE           ; AL <- X * log2(Y)

    ; Compute 2^AL
    CALL EXP2_CORE              ; AL <- 2^(X * log2(Y)) = Y^X

    PUSH AL
    HALT

POW_RET_ONE:
    LDC AL, CONST, ONE_F32      ; Return 1.0f
    PUSH AL
    HALT

POW_BASE_ZERO:
    OR BL, BL                   ; Test sign of exp (BL)
    JNZ SIGN, POW_ZERO_NEG_EXP
    XOR AL, AL                  ; 0^positive = 0.0
    PUSH AL
    HALT

POW_ZERO_NEG_EXP:
    LDC AL, CONST, POS_INF_F32  ; 0^negative = +Inf
    PUSH AL
    LDI ERR, 1
    LDI VF, 1
    HALT

POW_DOMAIN_ERR:
    LDI ERR, 1
    HALT
