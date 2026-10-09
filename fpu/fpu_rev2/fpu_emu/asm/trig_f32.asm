; ==============================================================================
; TRIG_F32: IEEE-754 Single-Precision Trigonometric Functions (SIN, COS, TAN)
;
; Implements:
;   - USER_SIN_F32 (Opcode 0x71)
;   - USER_COS_F32 (Opcode 0x79)
;   - USER_TAN_F32 (Opcode 0x81)
;
; Uses:
;   - Cody-Waite range reduction (mod pi/2) with quadrant tracking
;   - 24-stage circular CORDIC vector rotation (Z -> 0 mode)
;   - Quadrant reconstruction and NORMALIZE_F32 packing
;   - Tangent asymptote handling at +/- pi/2 asserting ERR=1, VF=1
;
; Scratchpad Allocation (DATA_RAM words 128..133):
;   SCR[0] : Original input float theta
;   SCR[1] : Opcode ID (0 = SIN, 1 = COS, 2 = TAN)
;   SCR[2] : Quadrant q (0, 1, 2, 3)
;   SCR[3] : Original input sign mask (0x00000000 or 0x80000000)
;   SCR[4] : Input mantissa during range reduction
;
; Register Allocation during CORDIC:
;   FL : X coordinate (starts as 1/K, ends as cos(r) in Q2.30)
;   BL : Y coordinate (starts as 0, ends as sin(r) in Q2.30)
;   BH : Z angle accumulator (starts as r in Q2.30, driven toward 0)
;   C  : Loop stage counter (0..23)
;   AH : Elementary angle theta_C from TRIG table (LDC AH, TRIG, C)
;   DH : Shifted X coordinate (X >> C)
;   FH : Shifted Y coordinate (Y >> C with sign extension)
; ==============================================================================

USER_SIN_F32:
    LDI BL, 0                   ; Opcode 0 = SIN
    JMP TRIG_ENTRY

USER_COS_F32:
    LDI BL, 1                   ; Opcode 1 = COS
    JMP TRIG_ENTRY

USER_TAN_F32:
    LDI BL, 2                   ; Opcode 2 = TAN
    JMP TRIG_ENTRY

TRIG_ENTRY:
    STO 1, BL                   ; Save Opcode ID in SCR[1]
    CALL POP_ONE_32             ; AL <- theta (TOS)
    STO 0, AL                   ; Save original theta in SCR[0]

    ; Extract and save original sign bit in SCR[3]
    ; Extract sign bit theta[31] into SCR[3]
    MOV AH, AL
    LDI BL, 1
    LSL BL, 31                  ; BL <- 0x80000000
    AND AH, BL                  ; AH <- sign bit of theta (bit 31)
    STO 3, AH

    ; Check for zero, NaN, Inf, and tiny angles
    UNPACK AL, EA               ; EA <- exponent, AL <- mantissa (bit 23 = 1)
    JZ ZERO, TRIG_ZERO          ; If input == 0.0: special zero handling
    CMP EA, 255
    JZ ZERO, TRIG_NAN_ERR       ; If NaN or Inf: error handling
    CMP EA, 115                 ; |theta| < 2^-12 (E < 115)
    JNZ CARRY, TRIG_SMALL_ANGLE ; If small angle: fast path (CARRY=1 on borrow)

    ; --------------------------------------------------------------------------
    ; Range Reduction (Cody-Waite mod pi/2)
    ; --------------------------------------------------------------------------
    CMP EA, 126
    JZ CARRY, TRIG_REDUCE_GENERAL  ; If EA >= 126 (no borrow, C=0): Cody-Waite reduction

    ; Here 115 <= EA < 126: |theta| < 0.5 < pi/4, so k = 0, q = 0, r = |theta|
    LDI BL, 0
    STO 2, BL                   ; SCR[2] <- quadrant 0
    CMP EA, 120
    JNZ CARRY, TRIG_SMALL_SHIFT_RIGHT ; If EA < 120 (borrow, C=1)
    MOV C, EA
    SUB C, 120                  ; C <- EA - 120 (0 <= C <= 5)
    LSL AL, C                   ; Shift mantissa to Q2.30
    MOV BH, AL                  ; BH <- Z0 = r in Q2.30
    JMP TRIG_START_CORDIC
TRIG_SMALL_SHIFT_RIGHT:
    LDI C, 120
    SUB C, EA                   ; C <- 120 - EA (1 <= C <= 5)
    LSR AL, C                   ; Shift mantissa to Q2.30
    MOV BH, AL                  ; BH <- Z0 = r in Q2.30
    JMP TRIG_START_CORDIC

TRIG_REDUCE_GENERAL:
    ; EA >= 126: Compute k = round(|theta| * 2/pi)
    STO 4, AL                   ; Save mantissa in SCR[4]
    LDC BL, CONST, 44           ; BL <- TWO_OVER_PI_F32 (0x3F22F983)
    UNPACK BL, EB               ; BL <- 0x00A2F983 (mantissa of 2/pi)
    MULU AL, BL                 ; {AH, AL} <- mantissa * (2/pi mantissa)

    ; Shift amount s_hi = 142 - EA
    LDI C, 142
    SUB C, EA                   ; C <- s_hi
    SUB C, 1                    ; C <- s_hi - 1
    LDI BL, 1
    LSL BL, C                   ; BL <- rounding bit: 1 << (s_hi - 1)
    ADD AH, BL                  ; Add rounding bit to product high word
    ADD C, 1                    ; C <- s_hi
    LSR AH, C                   ; AH <- k (rounded integer)

    ; Store full k into SCR[5] so it can be reused
    STO 5, AH

    ; Extract quadrant q = k & 3
    MOV BL, AH
    AND BL, 3
    STO 2, BL                   ; SCR[2] <- quadrant q

    ; Cody-Waite subtraction: r = theta_q30 - k*C1 - k*C2
    ; 1. theta_q30:
    LD AL, 4                    ; AL <- original mantissa
    MOV C, EA
    SUB C, 120                  ; C <- EA - 120
    LSL AL, C                   ; AL <- theta in Q2.30
    STO 4, AL                   ; Save theta_q30 in SCR[4]

    ; 2. Subtract k * C1:
    ; Synthesize 102943 = (100 << 10) + 543 into BL
    LDI BL, 100
    LSL BL, 10
    LDI DL, 543
    ADD BL, DL                  ; BL <- 102943

    LD AL, 5                    ; AL <- k
    MULU AL, BL                 ; {AH, AL} <- k * 102943
    LSL AL, 14                  ; AL <- (k * 102943) << 14 = k * C1
    MOV DH, AL                  ; DH <- k * C1

    ; 3. Subtract k * C2:
    ; Synthesize 11601 = (45 << 8) + 81 into BL
    LDI BL, 45
    LSL BL, 8
    LDI DL, 81
    ADD BL, DL                  ; BL <- 11601

    LD AL, 5                    ; AL <- k
    MULU AL, BL                 ; {AH, AL} <- k * 11601
    ADD AL, DH                  ; AL <- (k * C2) + (k * C1)
    MOV DH, AL                  ; DH <- total subtracted amount

    LD AL, 4                    ; AL <- theta in Q2.30
    SUB AL, DH                  ; AL <- theta - (k*C1 + k*C2)
    MOV BH, AL                  ; BH <- Z0 = r in Q2.30

    ; --------------------------------------------------------------------------
    ; Circular CORDIC Engine (24 stages, Z -> 0 vector rotation)
    ; --------------------------------------------------------------------------
TRIG_START_CORDIC:
    LDC FL, CONST, 55           ; FL <- CORDIC_INV_K_32 (0x26DD3B6A = 1/K in Q2.30)
    XOR BL, BL                  ; BL <- Y0 = 0
    LDI C, 0                    ; C <- 0 (stage counter)

CORDIC_STAGE_LOOP:
    ; Compute X_shift = X >> C in DH (X is always positive)
    MOV AL, FL
    LSR AL, C
    MOV DH, AL                  ; DH <- X_shift

    ; Compute Y_shift = Y >> C with sign extension in FH
    MOV AL, BL
    LSR AL, C
    OR BL, BL                   ; Test sign of Y
    JZ SIGN, CORDIC_Y_SHIFT_DONE ; If Y >= 0 (SIGN=0): no sign extension needed
    ; Sign extension for negative Y (SIGN=1):
    XOR AH, AH
    NOT AH                      ; AH <- 0xFFFFFFFF
    LSR AH, C
    NOT AH
    OR AL, AH                   ; Sign extend AL
CORDIC_Y_SHIFT_DONE:
    MOV FH, AL                  ; FH <- Y_shift

    ; Load elementary angle theta_C from TRIG ROM
    LDC AH, TRIG, C

    ; Rotate based on sign of Z (BH)
    OR BH, BH
    JNZ SIGN, CORDIC_DIR_NEG    ; If Z < 0 (SIGN=1): rotate negative

CORDIC_DIR_POS:
    ; Z >= 0: X <= X - Y_shift, Y <= Y + X_shift, Z <= Z - theta_C
    MOV AL, FL
    SUB AL, FH
    MOV FL, AL                  ; FL <- X - Y_shift
    ADD BL, DH                  ; BL <- Y + X_shift
    SUB BH, AH                  ; BH <- Z - theta_C
    JMP CORDIC_STAGE_NEXT

CORDIC_DIR_NEG:
    ; Z < 0: X <= X + Y_shift, Y <= Y - X_shift, Z <= Z + theta_C
    MOV AL, FL
    ADD AL, FH
    MOV FL, AL                  ; FL <- X + Y_shift
    SUB BL, DH                  ; BL <- Y - X_shift
    ADD BH, AH                  ; BH <- Z + theta_C

CORDIC_STAGE_NEXT:
    ADD C, 1
    CMP C, 24
    JNZ ZERO, CORDIC_STAGE_LOOP

    ; CORDIC rotation complete:
    ; FL = X24 = cos(r) in Q2.30 (always positive)
    ; BL = Y24 = sin(r) in Q2.30

    ; --------------------------------------------------------------------------
    ; Opcode Reconstruction & Normalization
    ; --------------------------------------------------------------------------
    LD AL, 1                    ; Load Opcode ID from SCR[1]
    CMP AL, 0
    JZ ZERO, RECONSTRUCT_SIN
    CMP AL, 1
    JZ ZERO, RECONSTRUCT_COS
    JMP RECONSTRUCT_TAN

    ; --- Sine Reconstruction ---
RECONSTRUCT_SIN:
    ; q = 0: +Y, q = 1: +X, q = 2: -Y, q = 3: -X
    LD AL, 2                    ; Load quadrant q from SCR[2]
    CMP AL, 0
    JZ ZERO, SIN_Q0
    CMP AL, 1
    JZ ZERO, SIN_Q1
    CMP AL, 2
    JZ ZERO, SIN_Q2
    ; q == 3: res = -X
    MOV AL, FL                  ; AL <- X (always positive)
    LDI BL, 1
    LSL BL, 31
    MOV AH, BL                  ; AH <- 0x80000000 (negative)
    JMP SIN_FINISH_SIGN

SIN_Q0:
    ; res = +Y
    MOV AL, BL                  ; AL <- Y (signed)
    XOR AH, AH                  ; Sign = 0 (positive)
    JMP SIN_HANDLE_Y_SIGN

SIN_Q1:
    ; res = +X
    MOV AL, FL                  ; AL <- X (always positive)
    XOR AH, AH                  ; Sign = 0 (positive)
    JMP SIN_FINISH_SIGN

SIN_Q2:
    ; res = -Y
    MOV AL, BL                  ; AL <- Y (signed)
    LDI BL, 1
    LSL BL, 31
    MOV AH, BL                  ; AH <- 0x80000000 (negative)

SIN_HANDLE_Y_SIGN:
    ; Y is in AL (signed 32-bit int), AH[31] holds target sign
    OR AL, AL
    JZ SIGN, SIN_Y_IS_POS       ; If bit 31 is 0 (AL >= 0, SIGN=0)
    ; AL is negative (< 0): AL <- -AL (two's complement absolute value)
    XOR BL, BL
    SUB BL, AL
    MOV AL, BL                  ; AL <- -AL
    ; Flip sign bit AH[31]:
    LDI BL, 1
    LSL BL, 31
    XOR AH, BL                  ; Flip sign
SIN_Y_IS_POS:
    ; AL is now positive magnitude, AH[31] is the correct sign!

SIN_FINISH_SIGN:
    ; Combine with original theta sign: sin(-theta) = -sin(theta)
    LD BL, 3                    ; Load original sign mask from SCR[3]
    XOR AH, BL                  ; Invert sign if theta was negative
    JMP TRIG_PACK_FLOAT

    ; --- Cosine Reconstruction ---
RECONSTRUCT_COS:
    ; q = 0: +X, q = 1: -Y, q = 2: -X, q = 3: +Y
    LD AL, 2                    ; Load quadrant q from SCR[2]
    CMP AL, 0
    JZ ZERO, COS_Q0
    CMP AL, 1
    JZ ZERO, COS_Q1
    CMP AL, 2
    JZ ZERO, COS_Q2
    ; q == 3:
    MOV AL, BL                  ; AL <- Y
    XOR AH, AH                  ; Sign = +1
    JMP COS_HANDLE_Y_SIGN
COS_Q0:
    MOV AL, FL                  ; AL <- +X
    XOR AH, AH                  ; Sign = +1
    JMP TRIG_PACK_FLOAT
COS_Q1:
    MOV AL, BL                  ; AL <- Y
    LDI AH, 0x80000000          ; Sign = -1
    JMP COS_HANDLE_Y_SIGN
COS_Q2:
    MOV AL, FL                  ; AL <- +X
    LDI AH, 0x80000000          ; Sign = -1
    JMP TRIG_PACK_FLOAT
COS_HANDLE_Y_SIGN:
    OR AL, AL
    JZ SIGN, TRIG_PACK_FLOAT
    FCHS AL                     ; AL <- -AL
    LDI EB, 0x80000000
    XOR AH, EB                  ; Flip sign
    JMP TRIG_PACK_FLOAT

    ; --- Tangent Reconstruction ---
RECONSTRUCT_TAN:
    ; Determine numerator (AL) and denominator (BL) based on quadrant q:
    ; q = 0: N = Y, D = X
    ; q = 1: N = -X, D = Y
    ; q = 2: N = Y, D = X
    ; q = 3: N = -X, D = Y
    LD AL, 2                    ; Load quadrant q
    AND AL, 1
    JZ ZERO, TAN_EVEN_Q
    ; Odd quadrant (q = 1, 3): N = X (FL), D = Y (BL), flip sign
    MOV AL, FL                  ; AL <- Numerator X
    ; BL already holds Denominator Y
    LDI AH, 0x80000000          ; Inverted sign
    JMP TAN_CHECK_ASYMPTOTE
TAN_EVEN_Q:
    ; Even quadrant (q = 0, 2): N = Y (BL), D = X (FL), positive sign
    MOV AL, BL                  ; AL <- Numerator Y
    MOV BL, FL                  ; BL <- Denominator X
    XOR AH, AH                  ; Positive sign
TAN_CHECK_ASYMPTOTE:
    ; Ensure numerator is positive:
    OR AL, AL
    JZ SIGN, TAN_NUM_POS
    FCHS AL
    LDI EB, 0x80000000
    XOR AH, EB
TAN_NUM_POS:
    ; Ensure denominator is positive:
    OR BL, BL
    JZ SIGN, TAN_DENOM_POS
    FCHS BL
    LDI EB, 0x80000000
    XOR AH, EB
TAN_DENOM_POS:
    ; Combine with original theta sign: tan(-theta) = -tan(theta)
    LD EB, 3
    XOR AH, EB                  ; AH[31] holds final sign

    ; Check for tangent asymptote: denominator BL == 0
    OR BL, BL
    JNZ ZERO, TAN_DO_DIV
    ; Denominator is zero: Assert ERR=1, VF=1 and return signed infinity
    LDC AL, CONST, 38           ; POS_INF_F32 (0x7F800000)
    OR AL, AH                   ; Attach computed sign
    PUSH AL
    LDI ERR, 1
    LDI VF, 1
    HALT

TAN_DO_DIV:
    ; Check for zero numerator: tan(0) = 0
    OR AL, AL
    JNZ ZERO, TAN_NON_ZERO
    XOR AL, AL
    OR AL, AH                   ; Attach sign to zero
    PUSH AL
    HALT

TAN_NON_ZERO:
    ; Perform fixed-point / mantissa division:
    ; Normalize numerator:
    LZC C, AL                   ; C <- leading zeros of AL
    SUB C, 8
    LSL AL, C
    LDI EA, 127
    EXP_SUB EA, C

    ; Normalize denominator:
    MOV DH, AL                  ; Stash normalized numerator mantissa in DH
    MOV AL, BL
    LZC C, AL                   ; C <- leading zeros of denominator
    SUB C, 8
    LSL AL, C
    MOV BL, AL                  ; BL <- normalized denominator mantissa
    LDI EB, 127
    EXP_SUB EB, C

    ; Divide numerator DH by denominator BL:
    MOV AL, DH                  ; AL <- dividend
    EXP_SUB EA, EB              ; EA <- exp_A - exp_B
    EXP_ADD EA, 126             ; EA <- exp_A - exp_B + 126 (re-bias for 24-bit quotient)
    LSL AL, 8                   ; Initial dividend shift: AL << 8
    DIVU AL, BL                 ; AL <- q0, DL <- r0
    MOV DH, AL                  ; DH <- q0
    LDI C, 2                    ; 2 more iterations of 8-bit quotient generation
TAN_DIV_LOOP:
    MOV AL, DL                  ; AL <- remainder from DIVU
    LSL AL, 8                   ; AL <- r << 8
    DIVU AL, BL                 ; AL <- q_i, DL <- r_i
    LSL DH, 8                   ; DH << 8
    OR DH, AL                   ; DH <- (q << 8) | q_i
    DJNZ TAN_DIV_LOOP

    MOV AL, DH                  ; AL <- 24-bit quotient mantissa
    ; Sign is in AH[31]
    CALL NORMALIZE_F32
    PUSH AL
    HALT

    ; --------------------------------------------------------------------------
    ; Pack Normalized Float for SIN / COS
    ; --------------------------------------------------------------------------
TRIG_PACK_FLOAT:
    ; Inputs:
    ;   AL : Magnitude in Q2.30 (positive)
    ;   AH : AH[31] holds result sign
    ; Alignment: Bit 30 has weight 2^0. Shift right by 7 puts bit 30 to bit 23.
    LSR AL, 7
    LDI EA, 127
    CALL NORMALIZE_F32
    PUSH AL
    HALT

    ; --------------------------------------------------------------------------
    ; Special Cases (Zero, NaN, Small Angle)
    ; --------------------------------------------------------------------------
TRIG_ZERO:
    ; theta == 0.0:
    ; SIN(0) = 0.0 with sign of theta
    ; COS(0) = 1.0 (positive)
    ; TAN(0) = 0.0 with sign of theta
    LD AL, 1                    ; Opcode ID
    CMP AL, 1
    JZ ZERO, TRIG_RET_ONE       ; COS(0) -> 1.0
    LD AL, 0                    ; Return original 0.0 (+0.0 or -0.0)
    PUSH AL
    HALT

TRIG_SMALL_ANGLE:
    ; |theta| < 2^-12:
    ; SIN(theta) ~ theta
    ; COS(theta) ~ 1.0
    ; TAN(theta) ~ theta
    LD AL, 1                    ; Opcode ID
    CMP AL, 1
    JZ ZERO, TRIG_RET_ONE       ; COS(theta) -> 1.0
    LD AL, 0                    ; Return original theta
    PUSH AL
    HALT

TRIG_RET_ONE:
    LDC AL, CONST, 32           ; ONE_F32 (0x3F800000 = 1.0)
    PUSH AL
    HALT

TRIG_NAN_ERR:
    LDC AL, CONST, 35           ; NAN_F32 (0x7FC00000)
    PUSH AL
    LDI ERR, 1
    HALT
