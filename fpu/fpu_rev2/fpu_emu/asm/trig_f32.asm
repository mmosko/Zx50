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
    MOV DH, FL
    LSR DH, C                   ; DH <- X_shift

    ; Compute Y_shift = Y >> C with sign extension in FH
    MOV FH, BL
    ASR FH, C                   ; FH <- Y_shift (arithmetic shift right preserves sign)

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
    ; q == 3: res = +Y
    MOV AL, BL                  ; AL <- Y (signed)
    XOR AH, AH                  ; Target sign = 0 (positive)
    JMP COS_HANDLE_Y_SIGN

COS_Q0:
    ; res = +X
    MOV AL, FL                  ; AL <- +X
    XOR AH, AH                  ; Sign = 0 (positive)
    JMP TRIG_PACK_FLOAT

COS_Q1:
    ; res = -Y
    MOV AL, BL                  ; AL <- Y (signed)
    LDI BL, 1
    LSL BL, 31
    MOV AH, BL                  ; Target sign = 0x80000000 (negative)
    JMP COS_HANDLE_Y_SIGN

COS_Q2:
    ; res = -X
    MOV AL, FL                  ; AL <- +X
    LDI BL, 1
    LSL BL, 31
    MOV AH, BL                  ; Sign = 0x80000000 (negative)
    JMP TRIG_PACK_FLOAT

COS_HANDLE_Y_SIGN:
    OR AL, AL
    JZ SIGN, COS_Y_IS_POS       ; If bit 31 is 0 (AL >= 0): already positive magnitude
    XOR BL, BL
    SUB BL, AL
    MOV AL, BL                  ; AL <- -AL (positive magnitude)
    LDI BL, 1
    LSL BL, 31
    XOR AH, BL                  ; Flip sign bit AH[31]
COS_Y_IS_POS:
    JMP TRIG_PACK_FLOAT

    ; --- Tangent Reconstruction ---
RECONSTRUCT_TAN:
    ; 1. Determine sign of Y and make Y positive:
    XOR AH, AH                  ; AH <- 0 (initial sign)
    OR BL, BL                   ; Test sign of Y
    JZ SIGN, TAN_Y_IS_POS       ; If Y >= 0: keep sign as 0
    ; Y is negative: BL <- -BL, AH <- 0x80000000
    XOR AL, AL
    SUB AL, BL
    MOV BL, AL                  ; BL <- |Y|
    LDI AL, 1
    LSL AL, 31
    MOV AH, AL                  ; AH <- 0x80000000
TAN_Y_IS_POS:

    ; 2. Determine numerator (AL) and denominator (BL) based on quadrant q:
    ; Even quadrant (q = 0, 2): N = |Y|, D = X, keep sign
    ; Odd quadrant  (q = 1, 3): N = X, D = |Y|, flip sign
    LD AL, 2                    ; Load quadrant q from SCR[2]
    AND AL, 1
    JZ ZERO, TAN_EVEN_Q
    ; Odd quadrant (q = 1, 3):
    MOV AL, FL                  ; AL <- Numerator X
    ; BL is already Denominator |Y|
    LDI BH, 1
    LSL BH, 31
    XOR AH, BH                  ; Flip sign
    JMP TAN_FINISH_SIGN

TAN_EVEN_Q:
    ; Even quadrant (q = 0, 2):
    MOV AL, BL                  ; AL <- Numerator |Y|
    MOV BL, FL                  ; BL <- Denominator X

TAN_FINISH_SIGN:
    ; Combine with original theta sign: tan(-theta) = -tan(theta)
    LD BH, 3                    ; Load theta sign mask from SCR[3]
    XOR AH, BH                  ; AH[31] holds final sign
    STO 6, AH                   ; Save final sign in SCR[6]

    ; 3. Check for zero denominator (asymptote at +/- pi/2):
    OR BL, BL
    JZ ZERO, TAN_DIV_ZERO

    ; 4. Check for zero numerator (tan(0) = 0, tan(pi) = 0):
    OR AL, AL
    JZ ZERO, TAN_ZERO

    ; 5. Convert numerator AL (in Q2.30) to float32:
    LSR AL, 7
    LDI EA, 127
    XOR AH, AH
    CALL NORMALIZE_F32          ; AL <- float32(Numerator)
    STO 7, AL                   ; Save float32(Numerator) in SCR[7]

    ; 6. Convert denominator BL (in Q2.30) to float32:
    MOV AL, BL
    LSR AL, 7
    LDI EA, 127
    XOR AH, AH
    CALL NORMALIZE_F32          ; AL <- float32(Denominator)
    MOV BL, AL                  ; BL <- float32(Denominator)
    LD AL, 7                    ; AL <- float32(Numerator)

    ; 7. Perform float division: AL / BL
    LD AH, 6                    ; AH[31] <- result sign from SCR[6]
    OR AL, AH                   ; Attach sign to numerator
    CALL DIV_F32_CORE           ; AL <- AL / BL
    PUSH AL                     ; Push result
    HALT

TAN_ZERO:
    XOR AL, AL                  ; Return zero mantissa
    LD AH, 6                    ; Preserve computed sign
    CALL NORMALIZE_F32
    PUSH AL
    HALT

TAN_DIV_ZERO:
    ; Force hardware divide-by-zero error
    XOR BL, BL
    DIVU AL, BL                 ; Asserts ERR=1, VF=1 in hardware
    LDC AL, CONST, 38           ; POS_INF_F32 (0x7F800000)
    LD BH, 6
    OR AL, BH                   ; Attach computed sign
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
